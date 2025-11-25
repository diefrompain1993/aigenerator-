"""Generate human-friendly playlist names based on extracted moods and genres."""

from __future__ import annotations

import logging
import random
from typing import Iterable, List

logger = logging.getLogger(__name__)

NAME_TEMPLATES = {
    "ночн": ["Неоновая ночь", "Ночной синтвейв", "Сумеречный драйв"],
    "груст": ["Осенняя грусть", "Дождливый вечер", "Мягкая тоска"],
    "космос": ["Космическая тишина", "Звездный туман", "Галактический чилл"],
    "лоф": ["Ло-фай расслабление", "Тетрадь ло-фая", "Кофейный ло-фай"],
}

DEFAULT_NAMES = [
    "Вайб дня",
    "Музыкальное настроение",
    "Вечерние огни",
    "Неоновый ритм",
]


def _pick_from_templates(tokens: Iterable[str]) -> List[str]:
    candidates: List[str] = []
    joined = " ".join(tokens)
    for stem, names in NAME_TEMPLATES.items():
        if stem in joined:
            candidates.extend(names)
    logger.debug("Name candidates from tokens %s: %s", tokens, candidates)
    return candidates


def generate_playlist_name(moods: Iterable[str], genres: Iterable[str], keywords: Iterable[str]) -> str:
    """Create a playlist name using provided tags."""

    all_tokens = list(moods) + list(genres) + list(keywords)
    candidates = _pick_from_templates(all_tokens)
    pool = candidates if candidates else DEFAULT_NAMES
    choice = random.choice(pool)
    logger.info("Generated playlist name: %s", choice)
    return choice


__all__ = ["generate_playlist_name"]
