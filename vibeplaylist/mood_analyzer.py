"""Analyze free-form text into musical search hints."""

from __future__ import annotations

import logging
import re
from typing import Dict, Iterable, List, Tuple

logger = logging.getLogger(__name__)

# Dictionaries with keyword stems mapped to tags
MOOD_KEYWORDS: Dict[str, List[str]] = {
    "груст": ["sad", "lofi", "melancholy"],
    "осен": ["autumn", "calm", "acoustic"],
    "ночн": ["night", "synthwave", "electronic"],
    "интерстеллар": ["space", "ambient", "soundtrack"],
    "космос": ["space", "ambient", "cosmic"],
    "драйв": ["synthwave", "retro", "80s"],
    "энер": ["energetic", "dance"],
    "споко": ["calm", "chill"],
}

GENRE_KEYWORDS: Dict[str, List[str]] = {
    "лоф": ["lofi", "lo-fi"],
    "синт": ["synthwave", "synth"],
    "ретро": ["retro", "80s"],
    "рок": ["rock"],
    "электро": ["electronic"],
    "джаз": ["jazz"],
    "эмбиент": ["ambient"],
}

VIBE_KEYWORDS: Dict[str, List[str]] = {
    "ретро": ["retro"],
    "космос": ["space"],
    "дожд": ["rain"],
    "ноч": ["night"],
    "вечер": ["evening"],
}

FALLBACK_GENRES = ["pop", "indie", "ambient"]


def _match_keywords(text: str, dictionary: Dict[str, List[str]]) -> List[str]:
    """Return values for each keyword stem found in text."""

    found: List[str] = []
    for stem, values in dictionary.items():
        if re.search(stem, text):
            found.extend(values)
    logger.debug("Matched stems %s -> %s", dictionary.keys(), found)
    return found


def _compute_intensity(moods: Iterable[str], keywords: Iterable[str]) -> float:
    """Compute a simple intensity score between 0 and 1."""

    score = 0.2 * len(set(moods)) + 0.1 * len(set(keywords))
    return min(1.0, round(score, 2))


def analyze_text(user_text: str) -> Dict[str, object]:
    """Analyze user text for musical cues.

    Parameters
    ----------
    user_text: str
        Free-form input describing the desired vibe.

    Returns
    -------
    dict
        Parsed attributes including moods, genres, keywords, intensity and bpm_range.
    """

    normalized = user_text.lower().strip()
    if not normalized:
        logger.warning("User text is empty; applying fallback genres")
        return {
            "moods": [],
            "genres": FALLBACK_GENRES,
            "keywords": [],
            "intensity": 0.1,
            "bpm_range": (60, 120),
        }

    moods = _match_keywords(normalized, MOOD_KEYWORDS)
    genres = _match_keywords(normalized, GENRE_KEYWORDS)
    keywords = _match_keywords(normalized, VIBE_KEYWORDS)

    if not genres:
        logger.info("No genres found, using fallback set")
        genres = FALLBACK_GENRES

    intensity = _compute_intensity(moods, keywords)
    bpm_low = 70 if "calm" in moods else 100
    bpm_high = 140 if "energetic" in moods or "dance" in moods else 120

    result = {
        "moods": list(dict.fromkeys(moods)),
        "genres": list(dict.fromkeys(genres)),
        "keywords": list(dict.fromkeys(keywords)),
        "intensity": intensity,
        "bpm_range": (bpm_low, bpm_high),
    }
    logger.debug("Analysis result: %s", result)
    return result


__all__ = ["analyze_text"]
