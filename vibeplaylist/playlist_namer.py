"""Playlist naming utilities respecting vibes, genres, and artists."""
from __future__ import annotations

from typing import Iterable, List


def _format_artists(artists: Iterable[str]) -> str:
    names = list(artists)
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return ", ".join(names)


def generate_playlist_name(
    moods: Iterable[str],
    genres: Iterable[str],
    keywords: Iterable[str],
    artists: Iterable[str] | None = None,
) -> str:
    """Generate playlist title using dominant vibe, genre, and artists."""
    moods_list = list(moods)
    genres_list = list(genres)
    artists_list: List[str] = list(artists) if artists else []
    keywords_list = list(keywords)

    primary_vibe = moods_list[0].title() if moods_list else (keywords_list[0].title() if keywords_list else "AI")
    genre_block = genres_list[0].title() if genres_list else "Vibes"
    artist_block = _format_artists(artists_list)

    if artist_block:
        return f"{primary_vibe} {genre_block} — {artist_block} AI Mix"
    return f"{primary_vibe} {genre_block}"
