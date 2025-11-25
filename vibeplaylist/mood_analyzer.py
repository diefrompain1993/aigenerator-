"""Mood and vibe analysis for user prompts (Spotify AI-like).

This module parses free-form text into structured signals: artists, genres,
moods, vibes, intensity, and search terms. It also validates potential artist
names against Yandex Music search results.
"""
from __future__ import annotations

import re
from typing import Dict, List

from .utils import get_logger
from .yandex_client import get_client

logger = get_logger(__name__)

# Keyword buckets for moods and vibes inspired by Spotify-style labels
MOOD_KEYWORDS = {
    "dark": ["dark", "тёмн", "noir", "blackout", "gloom"],
    "bright": ["ярк", "bright", "light", "sunny"],
    "sad": ["sad", "груст", "melanch", "печал", "осен"],
    "hype": ["hype", "hyped", "party", "энерг"],
    "chill": ["chill", "calm", "relax", "спокой", "lofi"],
    "dreamy": ["dream", "сонн", "aerial", "float"],
    "neon": ["неон", "neon", "night", "nightdrive", "drive"],
    "winter": ["winter", "зима", "snow", "frost", "cold"],
    "cinematic": ["film", "кино", "cinema", "саундтрек", "эпич"],
    "emotional": ["эмо", "эмоцион", "emotional", "heart"],
    "nostalgic": ["ностальг", "nostalg", "retro", "old", "80s"],
    "aggressive": ["агресс", "ярост", "rage", "грим", "drill", "phonk"],
    "trap vibe": ["trap", "трэп", "trap vibe", "rage"],
    "lofi vibe": ["lofi", "лофай", "study", "rain"],
    "synthwave vibe": ["synth", "синтвейв", "retrowave", "неонов"],
}

GENRE_HINTS = {
    "trap": ["trap", "трэп", "rage"],
    "phonk": ["phonk", "фо"],
    "drill": ["drill", "дрилл"],
    "synthwave": ["синт", "synth", "retrowave", "drive"],
    "lofi": ["lofi", "лофай", "study"],
    "chillout": ["chill", "calm", "relax"],
    "ambient": ["ambient", "космос"],
    "cinematic": ["cinematic", "саундтрек", "кино"],
}

STOPWORDS = {"вайб", "музыка", "плейлист", "как", "для", "под", "сделай", "сделать", "нужен"}


def _normalize_tokens(text: str) -> List[str]:
    return [token for token in re.split(r"\s+", text.lower()) if token]


def _extract_artists(prompt: str) -> List[str]:
    """Split prompt and validate fragments as artist names using Yandex Music search."""
    try:
        client = get_client()
    except RuntimeError:
        logger.warning("Client not initialized; skipping artist validation")
        return []

    fragments = re.split(r",|&|\bи\b", prompt, flags=re.IGNORECASE)
    artists: List[str] = []
    for fragment in fragments:
        candidate = fragment.strip()
        if not candidate:
            continue
        lower_candidate = candidate.lower()
        if any(lower_candidate.startswith(key) for key in STOPWORDS):
            continue
        if any(key in lower_candidate for values in MOOD_KEYWORDS.values() for key in values):
            # looks like mood word
            continue
        try:
            search_result = client.search(candidate, type_="artist")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Artist search failed for '%s': %s", candidate, exc)
            continue
        if search_result.artists and search_result.artists.results:
            artists.append(search_result.artists.results[0].name)
    return list(dict.fromkeys(artists))


def _score_intensity(tokens: List[str]) -> float:
    """Estimate intensity between 0 and 1 based on aggressive or calm cues."""
    aggressive = {"агресс", "rage", "drill", "trap", "gym", "хайп", "жест"}
    calm = {"chill", "calm", "lofi", "спокой", "sleep", "dream"}
    score = 0.5
    for token in tokens:
        if any(k in token for k in aggressive):
            score += 0.1
        if any(k in token for k in calm):
            score -= 0.1
    return max(0.0, min(1.0, score))


def analyze_text(prompt: str) -> Dict[str, object]:
    """Analyze a user prompt into artists, genres, moods, vibes, intensity, and search terms."""
    lowered = prompt.lower()
    tokens = _normalize_tokens(prompt)

    # moods/vibes detection
    moods: List[str] = []
    vibes: List[str] = []
    for label, keywords in MOOD_KEYWORDS.items():
        if any(word in lowered for word in keywords):
            moods.append(label)
            vibes.extend([kw for kw in keywords if len(kw) > 3])

    # genres
    genres: List[str] = []
    for genre, hints in GENRE_HINTS.items():
        if any(hint in lowered for hint in hints):
            genres.append(genre)

    artists = _extract_artists(prompt)

    search_terms = list(dict.fromkeys(tokens + moods + genres))
    intensity = _score_intensity(tokens)

    analysis = {
        "artists": list(dict.fromkeys(artists)),
        "genres": list(dict.fromkeys(genres)),
        "moods": list(dict.fromkeys(moods)),
        "vibes": list(dict.fromkeys(vibes)),
        "intensity": intensity,
        "search_terms": search_terms,
    }
    logger.info("Prompt analysis: %s", analysis)
    return analysis
