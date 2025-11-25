from typing import Dict, Iterable, List

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
        if track.id in seen:
            continue
        seen.add(track.id)
        unique.append(track)
        if len(unique) >= limit:
            break
    return unique


def _search_artist_top_tracks(client: Client, artist_name: str, limit: int) -> List[Track]:
    """Return top tracks for a given artist name."""
    search_result = client.search(artist_name, type_="artist")
    if not search_result.artists or not search_result.artists.results:
        return []
    artist = search_result.artists.results[0]
    tracks_resp = client.artists_tracks(artist.id, page_size=limit)
    return tracks_resp.tracks if tracks_resp and tracks_resp.tracks else []


def _search_by_queries(client: Client, queries: List[str], limit: int) -> List[Track]:
    """Search tracks by a list of queries and aggregate results."""
    aggregated: List[Track] = []
    for query in queries:
        if not query:
            continue
        search_result = client.search(query, type_="track", nocorrect=False)
        if search_result.tracks and search_result.tracks.results:
            aggregated.extend(search_result.tracks.results)
        if len(aggregated) >= limit:
            break
    return aggregated


def build_playlist_candidates(analysis: Dict[str, List[str]], limit: int = 40) -> List[Dict[str, str | int]]:
    """Build playlist candidates based on artists, moods, genres, and keywords."""
    client = get_client()
    candidates: List[Track] = []

    artists = analysis.get("artists", [])
    if artists:
        logger.info("Searching top tracks for artists: %s", artists)
        for artist_name in artists:
            candidates.extend(_search_artist_top_tracks(client, artist_name, limit))

    query_parts: List[str] = []
    moods = analysis.get("moods", [])
    genres = analysis.get("genres", [])
    keywords = analysis.get("keywords", [])

    if genres or moods:
        combo = " ".join(genres + moods)
        if combo:
            query_parts.append(combo)
        for mood in moods:
            for genre in genres:
                query_parts.append(f"{mood} {genre}")
    if keywords:
        query_parts.append(" ".join(keywords))

    logger.info("Searching tracks by queries: %s", query_parts)
    candidates.extend(_search_by_queries(client, query_parts, limit))

    unique_candidates = _dedupe_tracks(candidates, limit)
    results: List[Dict[str, str | int]] = []
    for track in unique_candidates:
        if not track.albums:
            continue
        artist_name = ", ".join(artist.name for artist in track.artists) if track.artists else ""
        results.append(
            {
                "track_id": track.id,
                "album_id": track.albums[0].id,
                "title": track.title,
                "artist": artist_name,
            }
        )
    logger.info("Built %d candidate tracks", len(results))
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
