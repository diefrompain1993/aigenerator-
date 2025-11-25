import re
from typing import Dict, List

from .yandex_client import get_client

MOOD_KEYWORDS = {
    "груст": ("sad", ["sad", "lofi", "calm"]),
    "ночн": ("night", ["night", "synthwave", "electronic"]),
    "осен": ("autumn", ["autumn", "indie", "acoustic"]),
    "драйв": ("drive", ["retro", "80s", "synthwave"]),
    "космос": ("space", ["space", "ambient", "soundtrack"]),
    "агрессив": ("aggressive", ["trap", "phonk", "drill"]),
    "синтвейв": ("neon", ["synthwave", "electronic", "retro"]),
    "лофай": ("chill", ["lofi", "chill", "study"]),
    "трэп": ("trap", ["trap"]),
    "грязн": ("dirty", ["trap", "grime"]),
}

VIBE_STOPWORDS = {"вайб", "музыка", "плейлист", "как", "для", "под", "сделай", "сделать", "нужен"}


def _extract_artists(user_text: str) -> List[str]:
    """Attempt to extract artist names from free-form text using search validation."""
    client = get_client()
    fragments = re.split(r",|&|\bи\b", user_text, flags=re.IGNORECASE)
    artists: List[str] = []
    for fragment in fragments:
        candidate = fragment.strip()
        if not candidate:
            continue
        lower_candidate = candidate.lower()
        if any(key in lower_candidate for key in MOOD_KEYWORDS) or lower_candidate in VIBE_STOPWORDS:
            continue
        search_result = client.search(candidate, type_="artist")
        if search_result.artists and search_result.artists.results:
            artists.append(search_result.artists.results[0].name)
    return list(dict.fromkeys(artists))


def analyze_text(user_text: str) -> Dict[str, List[str]]:
    """Analyze user text into moods, genres, artists, and keywords."""
    lowered = user_text.lower()
    moods: List[str] = []
    genres: List[str] = []
    keywords: List[str] = []

    for key, (mood_label, tags) in MOOD_KEYWORDS.items():
        if key in lowered:
            moods.append(mood_label)
            genres.extend(tags)
            keywords.extend(tags)

    if not keywords:
        keywords.extend([token for token in re.split(r"\s+", lowered) if token])

    artists = _extract_artists(user_text)

    return {
        "moods": list(dict.fromkeys(moods)),
        "genres": list(dict.fromkeys(genres)),
        "artists": artists,
        "keywords": list(dict.fromkeys(keywords)),
    }
