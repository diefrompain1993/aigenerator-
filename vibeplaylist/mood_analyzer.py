"""Advanced prompt analysis to build Spotify-like vibe profiles.

This module converts free-form text prompts into structured phase-based
representations that downstream recommenders can use to build smooth,
multi-phase playlists. It performs light-weight NLP using rule-based
segmenters, keyword lexicons, and on-demand artist validation via the
Yandex Music client.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .utils import get_logger
from .yandex_client import get_client

logger = get_logger(__name__)


# --- Data structures -------------------------------------------------------


@dataclass
class PhaseProfile:
    """Normalized description of a single vibe phase."""

    role: str
    raw_text: str
    artists: List[str] = field(default_factory=list)
    genres: List[str] = field(default_factory=list)
    moods: List[str] = field(default_factory=list)
    vibes: List[str] = field(default_factory=list)
    intensity: float = 0.5
    energy: float = 0.5
    valence: float = 0.5
    tempo_range: Tuple[int, int] = (80, 140)

    def to_dict(self) -> Dict[str, object]:
        return {
            "role": self.role,
            "raw_text": self.raw_text,
            "artists": self.artists,
            "genres": self.genres,
            "moods": self.moods,
            "vibes": self.vibes,
            "intensity": self.intensity,
            "energy": self.energy,
            "valence": self.valence,
            "tempo_range": self.tempo_range,
        }


# --- Keyword lexicons ------------------------------------------------------


MOOD_KEYWORDS = {
    "dark": ["dark", "тёмн", "noir", "black", "cold", "winter", "frost"],
    "bright": ["bright", "светл", "light", "warm", "солнеч"],
    "sad": ["sad", "груст", "печаль", "осен", "тоск"],
    "hype": ["hype", "party", "клуб", "энерг", "rave"],
    "chill": ["chill", "calm", "спокой", "lofi", "расслаб"],
    "dreamy": ["dream", "сонн", "dreamy", "эфирн"],
    "neon": ["неон", "neon", "night", "drive", "synth"],
    "winter": ["зим", "winter", "frost", "cold"],
    "cinematic": ["cinematic", "саундтрек", "кино", "film"],
    "emotional": ["эмо", "эмоцион", "emotional", "heart"],
    "nostalgic": ["ностальг", "nostalg", "retro", "old"],
    "aggressive": ["aggressive", "агресс", "rage", "жёстк", "жестк", "drill"],
    "trap vibe": ["trap", "трэп", "rage"],
    "lofi vibe": ["lofi", "лофай", "study"],
    "synthwave vibe": ["synth", "синтвейв", "ретро", "drive"],
    "romantic": ["романт", "romantic", "love"],
    "autumn": ["осень", "autumn", "желт", "листья"],
}

GENRE_HINTS = {
    "trap": ["trap", "трэп", "rage", "phonk"],
    "phonk": ["phonk", "фо"],
    "drill": ["drill", "дрилл"],
    "synthwave": ["синт", "synth", "retrowave", "drive"],
    "lofi": ["lofi", "лофай", "study"],
    "ambient": ["ambient", "космос", "space"],
    "cinematic": ["cinematic", "саундтрек", "кино", "film"],
    "indie": ["indie", "инди"],
    "dream pop": ["dream pop", "dream", "soft"],
    "club": ["club", "клуб", "house", "techno"],
}

INTENSITY_WEIGHTS = {
    "aggressive": 0.85,
    "dark": 0.75,
    "hype": 0.8,
    "trap vibe": 0.75,
    "drill": 0.85,
    "phonk": 0.8,
    "bright": 0.55,
    "dreamy": 0.45,
    "chill": 0.35,
    "romantic": 0.4,
    "lofi vibe": 0.3,
    "winter": 0.5,
    "sad": 0.35,
    "cinematic": 0.5,
}

VALENCE_HINTS = {
    "dark": 0.3,
    "aggressive": 0.35,
    "hype": 0.6,
    "bright": 0.7,
    "romantic": 0.6,
    "sad": 0.3,
    "chill": 0.5,
    "dreamy": 0.55,
    "winter": 0.4,
    "nostalgic": 0.45,
    "cinematic": 0.55,
}

TEMPO_HINTS = {
    "aggressive": (130, 170),
    "trap vibe": (120, 160),
    "drill": (130, 160),
    "hype": (120, 150),
    "dark": (100, 140),
    "romantic": (60, 110),
    "sad": (60, 110),
    "dreamy": (70, 120),
    "chill": (70, 110),
    "lofi vibe": (70, 100),
    "synthwave vibe": (100, 140),
}

TRANSITION_MARKERS = [
    r"в начале",
    r"сначала",
    r"потом",
    r"затем",
    r"далее",
    r"в конце",
    r"плавн",
    r"переход",
]

# Triggers that suggest “artist-like” fragments. We bias toward these instead of
# dropping the whole fragment when it also contains mood words (e.g. “агрессивное
# типо ken carson”).
ARTIST_HINT_WORDS = [
    "типо",
    "как",
    "в стиле",
    "стиле",
    "по типу",
    "style",
    "like",
    "similar",
]


# --- Helper utilities ------------------------------------------------------


def _split_phases(prompt: str) -> List[Tuple[str, str]]:
    """Heuristically split prompt into phases based on transition markers.

    Handles Russian constructs like "с плавным переходом в" and "потом" to produce
    start/end vibe phases for smoother playlists.
    """

    lowered = prompt.lower()
    if not any(marker in lowered for marker in TRANSITION_MARKERS):
        return [("single", prompt)]

    # Normalize frequent connective phrases to a unified splitter token
    normalized = re.sub(r"с\s+плавн[\w\s]*переход[\w\s]*в", "|transition|", prompt, flags=re.IGNORECASE)
    normalized = re.sub(r"плавн[\w\s]*переход", "|transition|", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\b(потом|затем|далее)\b", "|then|", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bв конце\b", "|end|", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bсначала\b", "|start|", normalized, flags=re.IGNORECASE)

    chunks = [c.strip() for c in normalized.split("|") if c.strip()]
    phases: List[Tuple[str, str]] = []
    role_order = ["start", "middle", "end"]
    role_idx = 0
    for chunk in chunks:
        token = chunk.lower()
        if token in {"transition", "then", "start"}:
            role_idx = min(role_idx + 1, len(role_order) - 1)
            continue
        if token == "end":
            role_idx = len(role_order) - 1
            continue
        phases.append((role_order[min(role_idx, len(role_order) - 1)], chunk))
        role_idx = min(role_idx + 1, len(role_order) - 1)

    return phases or [("single", prompt)]


def _validate_artists(candidates: List[str]) -> List[str]:
    """Validate candidate artist names via Yandex Music search."""

    try:
        client = get_client()
    except RuntimeError:
        logger.warning("Client not initialized; skipping artist validation")
        return []

    artists: List[str] = []
    for cand in candidates:
        try:
            search_result = client.search(cand, type_="artist")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Artist search failed for '%s': %s", cand, exc)
            continue
        if search_result.artists and search_result.artists.results:
            artists.append(search_result.artists.results[0].name)
    return list(dict.fromkeys(artists))


def _extract_artists(text: str) -> List[str]:
    """Extract artist-like fragments with bias toward connective phrases.

    This routine intentionally keeps fragments that mix vibe words with an artist
    name (e.g. "агрессивное типо ken carson") by searching for tokens following
    hint words. It falls back to comma/"и" splitting for simple lists.
    """

    lowered = text.lower()
    candidates: List[str] = []

    # Pull names after hint words such as "типо", "как", "в стиле".
    for hint in ARTIST_HINT_WORDS:
        pattern = rf"{hint}\s+([\w\s'.,-]{2,40})"
        for match in re.findall(pattern, lowered, flags=re.IGNORECASE):
            cleaned = match.replace(" ,", ",").strip().strip(",.")
            if cleaned:
                candidates.append(cleaned)

    # Also split by common delimiters to capture "nettspend, playboi carti" style.
    fragments = re.split(r",|&|\bи\b", text, flags=re.IGNORECASE)
    for frag in fragments:
        candidate = frag.strip()
        if not candidate:
            continue
        # Remove leading vibe adjectives but keep trailing names
        candidate = re.sub(r"^(агрессивн[\w\s]*|грустн[\w\s]*|тёмн[\w\s]*|мрачн[\w\s]*|холодн[\w\s]*|светл[\w\s]*|неоновый|неоновая)\s+",
                           "",
                           candidate,
                           flags=re.IGNORECASE)
        if candidate:
            candidates.append(candidate)

    # Validate against Yandex Music search to keep only real artists
    validated = _validate_artists([c for c in candidates if len(c.split()) <= 5])
    return validated


def _collect_moods_and_genres(text: str) -> Tuple[List[str], List[str], List[str]]:
    """Return moods, vibes, and genres detected in a text snippet."""

    lowered = text.lower()
    moods: List[str] = []
    vibes: List[str] = []
    for mood, keywords in MOOD_KEYWORDS.items():
        if any(key in lowered for key in keywords):
            moods.append(mood)
            vibes.extend([k for k in keywords if len(k) > 3])

    genres: List[str] = []
    for genre, hints in GENRE_HINTS.items():
        if any(h in lowered for h in hints):
            genres.append(genre)

    return list(dict.fromkeys(moods)), list(dict.fromkeys(vibes)), list(dict.fromkeys(genres))


def _estimate_energy_valence(moods: List[str]) -> Tuple[float, float]:
    """Approximate energy/valence from detected moods."""

    if not moods:
        return 0.5, 0.5
    energies = [INTENSITY_WEIGHTS.get(mood, 0.5) for mood in moods]
    valences = [VALENCE_HINTS.get(mood, 0.5) for mood in moods]
    return sum(energies) / len(energies), sum(valences) / len(valences)


def _tempo_from_moods(moods: List[str]) -> Tuple[int, int]:
    """Pick a tempo range informed by moods."""

    ranges = [TEMPO_HINTS[mood] for mood in moods if mood in TEMPO_HINTS]
    if not ranges:
        return (80, 140)
    low = sum(r[0] for r in ranges) // len(ranges)
    high = sum(r[1] for r in ranges) // len(ranges)
    return (low, high)


def _phase_from_text(role: str, text: str) -> PhaseProfile:
    moods, vibes, genres = _collect_moods_and_genres(text)
    artists = _extract_artists(text)
    energy, valence = _estimate_energy_valence(moods)
    tempo = _tempo_from_moods(moods)
    intensity = max(0.0, min(1.0, energy))

    return PhaseProfile(
        role=role,
        raw_text=text.strip(),
        artists=artists,
        genres=genres,
        moods=moods,
        vibes=vibes,
        intensity=intensity,
        energy=energy,
        valence=valence,
        tempo_range=tempo,
    )


# --- Public API ------------------------------------------------------------


def analyze_prompt(prompt: str) -> Dict[str, object]:
    """Parse user prompt into Spotify-like vibe phases.

    Returns a dictionary with:
    - phases: list of structured PhaseProfile dicts
    - aggregated fields (artists, genres, moods, vibes, intensity, search_terms)
    """

    prompt = prompt.strip()
    if not prompt:
        return {
            "phases": [],
            "artists": [],
            "genres": [],
            "moods": [],
            "vibes": [],
            "intensity": 0.5,
            "search_terms": [],
        }

    segments = _split_phases(prompt)
    phases: List[PhaseProfile] = [_phase_from_text(role, text) for role, text in segments]

    all_artists = list(dict.fromkeys([artist for phase in phases for artist in phase.artists]))
    all_genres = list(dict.fromkeys([genre for phase in phases for genre in phase.genres]))
    all_moods = list(dict.fromkeys([mood for phase in phases for mood in phase.moods]))
    all_vibes = list(dict.fromkeys([vibe for phase in phases for vibe in phase.vibes]))
    avg_intensity = sum(phase.intensity for phase in phases) / len(phases) if phases else 0.5
    search_terms = list(dict.fromkeys(re.split(r"\s+", prompt.lower())))

    analysis = {
        "prompt": prompt,
        "phases": [phase.to_dict() for phase in phases],
        "artists": all_artists,
        "genres": all_genres,
        "moods": all_moods,
        "vibes": all_vibes,
        "intensity": avg_intensity,
        "search_terms": search_terms,
    }
    logger.info("Prompt analysis complete: %s", analysis)
    return analysis

