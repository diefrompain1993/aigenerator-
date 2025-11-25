from random import choice
from typing import Iterable


TEMPLATES = [
    "Неоновая ночь",
    "Осенняя грусть",
    "Космический вайб",
    "Ло-фай вечер",
]


SUFFIXES = [
    "плейлист",
    "вайб",
    "ночь",
    "день",
    "история",
]


def generate_playlist_name(moods: Iterable[str], genres: Iterable[str], keywords: Iterable[str]) -> str:
    base_name = choice(TEMPLATES)
    pieces = list({*moods, *genres, *keywords})
    if pieces:
        base_name = choice(pieces).capitalize()
    return f"{base_name} {choice(SUFFIXES)}".strip()
