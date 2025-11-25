from random import choice
from typing import Iterable, List

TEMPLATES = [
    "Неоновая ночь",
    "Осенняя грусть",
    "Космический вайб",
    "Ло-фай вечер",
    "Грязный трэп",
]

SUFFIXES = [
    "плейлист",
    "вайб",
    "ночь",
    "день",
    "история",
]


def _format_artists(artists: Iterable[str]) -> str:
    names = list(artists)
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return ", ".join(names)


def generate_playlist_name(moods: Iterable[str], genres: Iterable[str], keywords: Iterable[str], artists: Iterable[str] | None = None) -> str:
    """Generate a playlist title using moods, genres, and artists."""
    moods_list = list(moods)
    genres_list = list(genres)
    artists_list: List[str] = list(artists) if artists else []

    if artists_list and genres_list:
        artist_block = _format_artists(artists_list)
        genre = genres_list[0].title()
        mood_block = moods_list[0].title() if moods_list else ""
        return f"{mood_block + ' ' if mood_block else ''}{genre}: {artist_block} Vibes".strip()

    if moods_list and genres_list:
        return f"{moods_list[0].title()} — {genres_list[0]}"

    if artists_list:
        return f"Вайб {artists_list[0]}"

    base_name = choice(TEMPLATES)
    pieces = list({*moods_list, *genres_list, *keywords})
    if pieces:
        base_name = choice(pieces).capitalize()
    return f"{base_name} {choice(SUFFIXES)}".strip()
