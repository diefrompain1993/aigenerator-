from typing import Dict, List

MOOD_KEYWORDS = {
    "груст": ["sad", "lofi", "calm"],
    "ночн": ["night", "synthwave", "electronic"],
    "осен": ["autumn", "indie", "acoustic"],
    "драйв": ["retro", "80s", "synthwave"],
    "космос": ["space", "ambient", "soundtrack"],
}


def analyze_text(text: str) -> Dict[str, List[str]]:
    lowered = text.lower()
    moods = []
    genres = []
    keywords = []

    for key, tags in MOOD_KEYWORDS.items():
        if key in lowered:
            moods.append(key)
            genres.extend(tags)
            keywords.extend(tags)

    if not keywords:
        keywords.extend(lowered.split())

    return {
        "moods": list(dict.fromkeys(moods)),
        "genres": list(dict.fromkeys(genres)),
        "keywords": list(dict.fromkeys(keywords)),
    }
