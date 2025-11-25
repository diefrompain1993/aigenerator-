"""Yandex Music client helpers powering AI playlist generation."""
from __future__ import annotations

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
    """Return initialized client or raise runtime error."""

    if _client is None:
        raise RuntimeError("Client is not initialized. Call init_client first.")
    return _client


def search_artist(artist_name: str):
    """Search an artist by name and return best match."""

    client = get_client()
    try:
        search_result = client.search(artist_name, type_="artist")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Artist search failed for '%s': %s", artist_name, exc)
        return None
    if search_result.artists and search_result.artists.results:
        return search_result.artists.results[0]
    return None


def track_to_dict(track: Track) -> Optional[Dict[str, str | int]]:
    """Convert Track object into a serializable dictionary."""

    if not track or not track.albums:
        return None
    artist_name = ", ".join(artist.name for artist in track.artists) if track.artists else ""
    return {
        "track_id": track.id,
        "album_id": track.albums[0].id,
        "title": track.title,
        "artist": artist_name,
    }


def _dedupe_tracks(tracks: Iterable[Track], limit: int) -> List[Track]:
    seen: set[int] = set()
    unique: List[Track] = []
    for track in tracks:
        if not track or track.id in seen:
            continue
        seen.add(track.id)
        unique.append(track)
        if len(unique) >= limit:
            break
    return unique


def fetch_artist_and_similars(artist_id: int, limit: int = 15) -> Dict[str, List[Track]]:
    """Return top tracks, similar artist tracks, and artist radio batch."""

    client = get_client()
    artist_top: List[Track] = []
    similar_artist_tracks: List[Track] = []
    artist_radio: List[Track] = []

    try:
        top_resp = client.artists_tracks(artist_id, page_size=limit)
        if top_resp and top_resp.tracks:
            artist_top = top_resp.tracks
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to fetch top tracks for artist %s: %s", artist_id, exc)

    try:
        similar_artists = client.artists_similar(artist_id)
        for artist in similar_artists or []:
            tracks = client.artists_tracks(artist.id, page_size=max(3, limit // 4))
            if tracks and tracks.tracks:
                similar_artist_tracks.extend(tracks.tracks)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to fetch similar artists for %s: %s", artist_id, exc)

    try:
        artist_radio = fetch_rotor_radio(f"artist:{artist_id}", mood=None, variety=0.3, limit=max(6, limit // 2))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to fetch artist radio %s: %s", artist_id, exc)

    return {
        "artist_top": _dedupe_tracks(artist_top, limit),
        "similar_artist_tracks": _dedupe_tracks(similar_artist_tracks, limit),
        "artist_radio": _dedupe_tracks(artist_radio, limit // 2),
    }


def fetch_similar_tracks_for_seed(seeds: List[Track], limit: int = 10) -> List[Track]:
    """Fetch tracks similar to given seeds using get_similar_tracks when available."""

    client = get_client()
    collected: List[Track] = []
    for seed in seeds:
        if hasattr(seed, "get_similar_tracks"):
            try:
                similar = seed.get_similar_tracks()
                collected.extend([item.track for item in similar if getattr(item, "track", None)])
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to fetch similar tracks for %s: %s", seed.id, exc)
        else:
            # fallback: search by title
            try:
                res = client.search(seed.title, type_="track")
                if res and res.tracks and res.tracks.results:
                    collected.extend(res.tracks.results[:3])
            except Exception as exc:  # noqa: BLE001
                logger.exception("Track search fallback failed for %s: %s", seed.id, exc)
        if len(collected) >= limit:
            break
    return _dedupe_tracks(collected, limit)


def fetch_rotor_radio(station_id: str, mood: Optional[str], variety: float, limit: int) -> List[Track]:
    """Generic rotor radio loader with safe parsing."""

    client = get_client()
    try:
        radio = client.rotor_radio(station_id=station_id, mood=mood, variety=variety)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to load rotor radio %s: %s", station_id, exc)
        return []

    sequence = getattr(radio, "sequence", None)
    if sequence is None and isinstance(radio, dict):
        sequence = radio.get("sequence", [])
    tracks: List[Track] = []
    for item in sequence or []:
        track = getattr(item, "track", None)
        if not track and hasattr(item, "id"):
            try:
                track = client.tracks(item.id)[0]
            except Exception:  # noqa: BLE001
                track = None
        if track:
            tracks.append(track)
        if len(tracks) >= limit:
            break
    return tracks


def _pick_station_id(moods: List[str], vibes: List[str], station_ids: List[str]) -> Optional[str]:
    """Select rotor station id based on moods and vibes."""

    mapping = {
        "dark": "mood_dark",
        "winter": "mood_winter",
        "chill": "mood_chill",
        "emotional": "mood_emotional",
        "neon": "mood_neon",
        "sad": "mood_sad",
        "hype": "mood_hype",
        "aggressive": "mood_aggressive",
        "autumn": "mood_autumn",
    }
    candidates = []
    for mood in moods + vibes:
        if mood in mapping:
            candidates.append(mapping[mood])
        else:
            station = next((sid for sid in station_ids if mood in sid), None)
            if station:
                candidates.append(station)
    return candidates[0] if candidates else None


def fetch_mood_station_tracks(moods: List[str], vibes: List[str], limit: int = 20) -> List[Track]:
    """Pick appropriate rotor station and return tracks."""

    client = get_client()
    try:
        station_list = client.rotor_stations_list()
        station_ids = [station.station_id for station in station_list] if station_list else []
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to load rotor stations list: %s", exc)
        station_ids = []

    station_id = _pick_station_id(moods, vibes, station_ids)
    if not station_id and station_ids:
        station_id = station_ids[0]
    if not station_id:
        return []

    variety = 0.35 if "aggressive" in moods else 0.25
    tracks = fetch_rotor_radio(station_id, mood=moods[0] if moods else None, variety=variety, limit=limit)
    return _dedupe_tracks(tracks, limit)


def create_playlist(title: str, tracks: List[Dict[str, str | int]]) -> dict:
    """Create a playlist in user account and insert tracks."""

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


def build_playlist_candidates(analysis: Dict[str, object], limit: int = 35) -> List[Dict[str, str | int]]:
    """Legacy helper kept for compatibility; delegates to recommender pipeline."""

    from .recommender import generate_playlist_for_analysis

    return generate_playlist_for_analysis(analysis, limit=limit)

