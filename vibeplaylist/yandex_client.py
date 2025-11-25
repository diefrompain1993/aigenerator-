from typing import List

from yandex_music import Client, Track, TrackId

from .utils import get_logger

logger = get_logger(__name__)

_client: Client | None = None


def init_client(token: str) -> Client:
    global _client
    logger.info("Initializing Yandex Music client")
    _client = Client(token).init()
    return _client


def _require_client() -> Client:
    if _client is None:
        raise RuntimeError("Client is not initialized. Call init_client with a token first.")
    return _client


def search_tracks(genres: List[str], moods: List[str], keywords: List[str], limit: int = 30) -> List[Track]:
    client = _require_client()
    query_parts = list(dict.fromkeys(keywords + genres + moods))
    query = " ".join(query_parts) or "music"
    logger.info("Searching tracks with query: %s", query)
    search_result = client.search(query, type_="track", nocorrect=False, page=0)
    if not search_result.tracks:
        return []
    return search_result.tracks.results[:limit]


def create_playlist(title: str, tracks: List[Track]) -> dict:
    client = _require_client()
    logger.info("Creating playlist '%s' with %d tracks", title, len(tracks))
    playlist = client.users_playlists_create(title)
    track_ids = [TrackId(track.id, track.albums[0].id) for track in tracks if track.albums]
    if track_ids:
        client.users_playlists_insert_tracks(playlist.kind, track_ids, revision=playlist.revision)
    return {"title": title, "kind": playlist.kind, "tracks": len(track_ids)}
