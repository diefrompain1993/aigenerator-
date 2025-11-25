"""Client helpers for working with the Yandex Music API."""

from __future__ import annotations

import logging
from typing import Dict, Iterable, List, Optional

from yandex_music import Client

logger = logging.getLogger(__name__)

client: Optional[Client] = None


def init_client(token: str) -> None:
    """Initialize the global Yandex Music client with the provided token."""

    global client
    logger.info("Initializing Yandex Music client")
    client = Client(token).init()


def _ensure_client() -> Client:
    if client is None:
        raise RuntimeError("Yandex Music client is not initialized")
    return client


def search_tracks(genres: Iterable[str], moods: Iterable[str], keywords: Iterable[str], limit: int = 30) -> List[Dict[str, str]]:
    """Search for tracks using keywords, genres and mood hints.

    The function combines search results from multiple sources and removes duplicates.
    """

    music_client = _ensure_client()
    collected: Dict[str, Dict[str, str]] = {}

    def _add_tracks(results: List) -> None:
        for track in results:
            track_id = getattr(track, "id", None)
            if track_id is None:
                continue
            if track_id in collected:
                continue
            title = getattr(track, "title", "")
            artists = getattr(track, "artists", [])
            artist_name = ", ".join([getattr(a, "name", "") for a in artists])
            collected[track_id] = {"title": title, "artist": artist_name, "id": str(track_id)}

    queries = list(set(keywords)) + list(set(genres)) + list(set(moods))
    logger.info("Searching tracks for queries: %s", queries)

    for query in queries:
        try:
            response = music_client.search(query, type_="track", nocorrect=False)
            tracks = response.tracks.results if response and response.tracks else []
            _add_tracks(tracks)
        except Exception as error:  # pragma: no cover - network
            logger.error("Failed to search tracks for '%s': %s", query, error)

    # Additional genre filtering
    for genre in genres:
        try:
            response = music_client.search(genre, type_="track", nocorrect=True)
            tracks = response.tracks.results if response and response.tracks else []
            _add_tracks(tracks)
        except Exception as error:  # pragma: no cover - network
            logger.error("Genre search failed for '%s': %s", genre, error)

    results_list = list(collected.values())[:limit]
    logger.info("Found %d unique tracks", len(results_list))
    return results_list


def create_playlist(title: str, tracks: List[Dict[str, str]]) -> Dict[str, object]:
    """Create a playlist with the provided title and track list."""

    music_client = _ensure_client()
    try:
        playlist = music_client.users_playlists_create(title)
        track_ids = [track["id"] for track in tracks]
        kind = playlist.kind if hasattr(playlist, "kind") else None
        if kind is None:
            raise RuntimeError("Invalid playlist response")
        music_client.playlist_add_tracks(kind=kind, track_ids=track_ids)
        logger.info("Playlist '%s' created with %d tracks", title, len(track_ids))
        return {"title": title, "track_count": len(track_ids), "kind": kind}
    except Exception as error:  # pragma: no cover - network
        logger.exception("Failed to create playlist: %s", error)
        raise


__all__ = ["init_client", "search_tracks", "create_playlist"]
