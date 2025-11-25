"""Playlist naming logic informed by vibe phases."""
from __future__ import annotations

from typing import Iterable, List


def _format_artists(artists: Iterable[str]) -> str:
    names = list(artists)
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return ", ".join(names)


def _main_vibe(phases: List[dict]) -> str:
    if not phases:
        return "AI Vibes"
    moods = phases[0].get("moods", [])
    vibes = phases[0].get("vibes", [])
    if moods:
        return moods[0].title()
    if vibes:
        return vibes[0].title()
    return "AI Vibes"


def generate_playlist_name(phases: List[dict]) -> str:
    """Generate a lively playlist title using phase transitions."""

    if not phases:
        return "AI Playlist"

    primary = _main_vibe(phases)
    genres = phases[0].get("genres", [])
    genre_part = genres[0].title() if genres else "Mix"
    artists = phases[0].get("artists", [])

    if len(phases) > 1:
        end_vibe = _main_vibe([phases[-1]])
        artists_end = phases[-1].get("artists", [])
        artist_block = _format_artists(artists or artists_end)
        if artist_block:
            return f"{primary} → {end_vibe} — {artist_block} Vibes"
        return f"{primary} → {end_vibe}"

    artist_block = _format_artists(artists)
    if artist_block:
        return f"{primary} {genre_part} — {artist_block} AI Mix"
    return f"{primary} {genre_part}"

