"""Yandex Music client helpers for Spotify-like AI playlist generation."""
from __future__ import annotations

import random
from typing import Dict, Iterable, List, Optional

from yandex_music import Client, Track

from .utils import get_logger

logger = get_logger(__name__)

_client: Client | None = None


def init_client(token: str) -> Client:
    """Initialize and cache the Yandex Music client."""
    global _client
    logger.info("Initializing Yandex Music client")
    _client = Client(token).init()
    return _client


def get_client() -> Client:
    """Return the initialized client or raise if not set."""
    if _client is None:
        raise RuntimeError("Client is not initialized. Call init_client with a token first.")
    return _client


def _dedupe_tracks(tracks: Iterable[Track], limit: int) -> List[Track]:
    """Remove duplicate tracks by id preserving order up to limit."""
    seen: set[int] = set()
    unique: List[Track] = []
    for track in tracks:
        if not track or not track.id or track.id in seen:
            continue
        seen.add(track.id)
        unique.append(track)
        if len(unique) >= limit:
            break
    return unique


def _safe_track_dict(track: Track) -> Optional[Dict[str, str | int]]:
    """Convert Track into serializable dict if album info exists."""
    if not track or not track.albums:
        return None
    artist_name = ", ".join(artist.name for artist in track.artists) if track.artists else ""
    return {
        "track_id": track.id,
        "album_id": track.albums[0].id,
        "title": track.title,
        "artist": artist_name,
    }


def _search_artist(client: Client, artist_name: str):
    try:
        search_result = client.search(artist_name, type_="artist")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Artist search failed for '%s': %s", artist_name, exc)
        return None
    if search_result.artists and search_result.artists.results:
        return search_result.artists.results[0]
    return None


def _artist_top_tracks(client: Client, artist_id: int, limit: int) -> List[Track]:
    try:
        tracks_resp = client.artists_tracks(artist_id, page_size=limit)
        return tracks_resp.tracks if tracks_resp and tracks_resp.tracks else []
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to fetch top tracks for artist %s: %s", artist_id, exc)
        return []


def _similar_artists_tracks(client: Client, artist_id: int, limit: int) -> List[Track]:
    try:
        similar = client.artists_similar(artist_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to fetch similar artists for %s: %s", artist_id, exc)
        return []
    tracks: List[Track] = []
    if not similar:
        return tracks
    for artist in similar:
        tracks.extend(_artist_top_tracks(client, artist.id, max(3, limit // 4)))
        if len(tracks) >= limit:
            break
    return tracks


def _similar_tracks(client: Client, seeds: List[Track], limit: int) -> List[Track]:
    collected: List[Track] = []
    for track in seeds:
        if not hasattr(track, "get_similar_tracks"):
            continue
        try:
            similar = track.get_similar_tracks()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to fetch similar tracks for %s: %s", track.id, exc)
            continue
        if similar:
            collected.extend([item.track for item in similar if getattr(item, "track", None)])
        if len(collected) >= limit:
            break
    return collected


def _rotor_station_tracks(client: Client, station_id: str, mood: Optional[str], variety: float, limit: int) -> List[Track]:
    """Fetch tracks from rotor radio for mood/artist stations."""
    try:
        radio = client.rotor_radio(station_id=station_id, mood=mood, variety=variety)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to load rotor radio %s: %s", station_id, exc)
        return []

    sequence = getattr(radio, "sequence", None) or radio.get("sequence", []) if isinstance(radio, dict) else []
    tracks: List[Track] = []
    for item in sequence:
        track = getattr(item, "track", None)
        if not track and hasattr(item, "id"):
            try:
                fetched = client.tracks(item.id)
                track = fetched[0] if fetched else None
            except Exception:  # noqa: BLE001
                track = None
        if track:
            tracks.append(track)
        if len(tracks) >= limit:
            break
    return tracks


def _pick_station_id(moods: List[str], vibes: List[str], station_ids: List[str]) -> Optional[str]:
    """Select rotor station id based on mood keywords."""
    candidates = []
    mapping = {
        "dark": "mood_dark",
        "winter": "mood_winter",
        "chill": "mood_chill",
        "emotional": "mood_emotional",
        "neon": "mood_neon",
        "sad": "mood_sad",
        "hype": "mood_hype",
        "aggressive": "mood_aggressive",
    }
    for mood in moods + vibes:
        station = mapping.get(mood) or next((sid for sid in station_ids if mood in sid), None)
        if station:
            candidates.append(station)
    return candidates[0] if candidates else None


def build_playlist_candidates(analysis: Dict[str, object], limit: int = 35) -> List[Dict[str, str | int]]:
    """Build playlist candidates mixing artist tops, similar material, and mood stations."""
    client = get_client()
    artists: List[str] = analysis.get("artists", [])  # type: ignore[assignment]
    moods: List[str] = analysis.get("moods", [])  # type: ignore[assignment]
    vibes: List[str] = analysis.get("vibes", [])  # type: ignore[assignment]
    intensity: float = float(analysis.get("intensity", 0.5))

    artist_tracks: List[Track] = []
    similar_artist_tracks: List[Track] = []
    similar_tracks: List[Track] = []
    mood_tracks: List[Track] = []

    artist_objects = []
    for artist_name in artists:
        artist_obj = _search_artist(client, artist_name)
        if artist_obj:
            artist_objects.append(artist_obj)
            artist_tracks.extend(_artist_top_tracks(client, artist_obj.id, max(5, limit // 3)))
            similar_artist_tracks.extend(_similar_artists_tracks(client, artist_obj.id, max(6, limit // 3)))
    if artist_tracks:
        similar_tracks.extend(_similar_tracks(client, artist_tracks[:5], max(5, limit // 4)))

    # rotor stations list for mood selection
    try:
        station_list = client.rotor_stations_list()
        station_ids = [station.station_id for station in station_list] if station_list else []
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to load rotor stations list: %s", exc)
        station_ids = []

    station_id = _pick_station_id(moods, vibes, station_ids)
    if station_id:
        mood_tracks.extend(
            _rotor_station_tracks(
                client,
                station_id=station_id,
                mood=moods[0] if moods else None,
                variety=max(0.1, min(0.9, intensity)),
                limit=max(10, limit // 2),
            )
        )
    elif not artist_objects and station_ids:
        # fallback to first available mood station
        mood_tracks.extend(_rotor_station_tracks(client, station_ids[0], mood=None, variety=0.3, limit=max(10, limit // 2)))

    # artist radio when artists exist
    for artist_obj in artist_objects:
        mood_tracks.extend(
            _rotor_station_tracks(
                client,
                station_id=f"artist:{artist_obj.id}",
                mood=moods[0] if moods else None,
                variety=0.3,
                limit=max(5, limit // 4),
            )
        )

    # Assemble with proportions
    artist_share = max(3, int(limit * 0.3))
    similar_share = max(3, int(limit * 0.3))
    mood_share = limit

    combined: List[Track] = []
    combined.extend(_dedupe_tracks(artist_tracks, artist_share))
    combined.extend(_dedupe_tracks(similar_artist_tracks + similar_tracks, similar_share))
    combined.extend(_dedupe_tracks(mood_tracks, mood_share))

    combined = _dedupe_tracks(combined, limit)
    random.shuffle(combined)

    results: List[Dict[str, str | int]] = []
    for track in combined:
        info = _safe_track_dict(track)
        if info:
            results.append(info)
    logger.info("Built candidate playlist of %d tracks", len(results))
    return results


def create_playlist(title: str, tracks: List[Dict[str, str | int]]) -> dict:
    """Create a playlist and insert provided tracks using playlist helper."""
    client = get_client()
    logger.info("Creating playlist '%s' with %d tracks", title, len(tracks))
    playlist = client.users_playlists_create(title)
    full_playlist = client.users_playlists(playlist.kind, playlist.owner.uid)
    inserted = 0
    for track in tracks:
        try:
            full_playlist = full_playlist.insert_track(
                track_id=track["track_id"],
                album_id=track["album_id"],
            )
            inserted += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to insert track %s: %s", track, exc)
            raise
    return {"title": title, "kind": playlist.kind, "tracks": inserted}
