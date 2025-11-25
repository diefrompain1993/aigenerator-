"""Recommendation pipeline orchestrating Spotify-like AI playlist logic.

This module consumes analyzed prompt phases and builds multi-stage playlists
that blend artist seeds, similar artists/tracks, rotor mood stations, and
smooth transitions between vibe phases.
"""
from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Sequence

from yandex_music import Track

from .utils import get_logger
from .yandex_client import (
    fetch_artist_and_similars,
    fetch_mood_station_tracks,
    fetch_similar_tracks_for_seed,
    search_tracks_by_terms,
    search_artist,
    track_to_dict,
)

logger = get_logger(__name__)


@dataclass
class ScoredTrack:
    track: Track
    score: float
    source: str


def score_track_for_phase(track: Track, phase: Dict[str, object]) -> float:
    """Compute similarity score between a track and vibe phase profile."""

    if not track:
        return 0.0

    score = 0.0
    track_artists = {artist.name.lower() for artist in getattr(track, "artists", []) or []}
    phase_artists = {name.lower() for name in phase.get("artists", [])}
    if track_artists & phase_artists:
        score += 0.25

    title = getattr(track, "title", "").lower()
    album = (track.albums or [None])[0]
    genre_id = getattr(album, "genre", None) or getattr(album, "genre_id", None) or ""
    for genre in phase.get("genres", []):
        if genre.lower() in title or genre.lower() in str(genre_id).lower():
            score += 0.25
            break

    for mood in phase.get("moods", []):
        if mood in title:
            score += 0.15
            break

    # Approximate tempo/energy fit using provided tempo range
    low, high = phase.get("tempo_range", (80, 140))
    tempo_hint = getattr(track, "bpm", None)
    if tempo_hint and low <= tempo_hint <= high:
        score += 0.2
    else:
        score += 0.05  # slight default

    score += 0.1 if phase.get("energy", 0.5) > 0.6 else 0.05
    return min(score, 1.0)


def _limit_per_artist(tracks: Sequence[ScoredTrack], per_artist: int = 3) -> List[ScoredTrack]:
    """Limit occurrences of the same artist to diversify playlist."""

    counts: Counter[str] = Counter()
    diversified: List[ScoredTrack] = []
    for item in tracks:
        artist_name = ", ".join(a.name for a in getattr(item.track, "artists", []) or [])
        if counts[artist_name] >= per_artist:
            continue
        counts[artist_name] += 1
        diversified.append(item)
    return diversified


def _collect_phase_candidates(phase: Dict[str, object], limit: int) -> List[ScoredTrack]:
    """Collect and score candidates for a single phase."""

    artists: List[str] = phase.get("artists", [])
    moods: List[str] = phase.get("moods", [])
    vibes: List[str] = phase.get("vibes", [])

    seeds: List[Track] = []
    scored: List[ScoredTrack] = []

    # Artist seeds + similar artists + top tracks
    for artist_name in artists:
        artist_obj = search_artist(artist_name)
        if not artist_obj:
            continue
        bundles = fetch_artist_and_similars(artist_obj.id, limit=max(6, limit // 2))
        for track in bundles["artist_top"]:
            scored.append(ScoredTrack(track, score_track_for_phase(track, phase) + 0.2, "artist_top"))
            seeds.append(track)
        for track in bundles["similar_artist_tracks"]:
            scored.append(ScoredTrack(track, score_track_for_phase(track, phase), "similar_artist"))
        for track in bundles["artist_radio"]:
            scored.append(ScoredTrack(track, score_track_for_phase(track, phase) + 0.1, "artist_radio"))

    if seeds:
        similar_tracks = fetch_similar_tracks_for_seed(seeds[:5], limit=max(4, limit // 3))
        for track in similar_tracks:
            scored.append(ScoredTrack(track, score_track_for_phase(track, phase), "similar_tracks"))

    # Mood/genre stations give body of the phase
    station_tracks = fetch_mood_station_tracks(moods, vibes, limit=max(10, limit // 2))
    for track in station_tracks:
        scored.append(ScoredTrack(track, score_track_for_phase(track, phase) + 0.05, "mood_station"))

    # If no seeds were found, try free-form search by the raw phase text or moods
    if not scored:
        raw_text = phase.get("raw_text", "")
        search_terms = []
        if raw_text:
            search_terms.append(str(raw_text))
        search_terms.extend(phase.get("moods", []))
        search_terms.extend(phase.get("genres", []))
        for track in search_tracks_by_terms(search_terms, limit=max(8, limit // 2)):
            scored.append(ScoredTrack(track, score_track_for_phase(track, phase) + 0.05, "fallback_search"))

    # Deduplicate and sort by score
    deduped: List[ScoredTrack] = []
    seen_ids = set()
    for item in scored:
        if not item.track or item.track.id in seen_ids:
            continue
        seen_ids.add(item.track.id)
        deduped.append(item)

    deduped.sort(key=lambda x: x.score, reverse=True)
    diversified = _limit_per_artist(deduped, per_artist=3)
    return diversified[: limit * 2]


def _phase_slice_sizes(phase_count: int, total_limit: int) -> List[int]:
    """Determine slice sizes for phases (rough 40/20/40 for 2 phases)."""

    if phase_count <= 1:
        return [total_limit]
    if phase_count == 2:
        return [int(total_limit * 0.45), total_limit - int(total_limit * 0.45)]
    # start, middle, end split
    first = int(total_limit * 0.4)
    middle = int(total_limit * 0.2)
    last = total_limit - first - middle
    return [first, middle, last]


def _smooth_transition(phases: List[Dict[str, object]], buckets: List[List[ScoredTrack]]) -> List[ScoredTrack]:
    """Assemble phases into a single playlist with gentle transitions."""

    if len(phases) == 1:
        return buckets[0]

    assembled: List[ScoredTrack] = []
    for idx, phase_tracks in enumerate(buckets):
        if idx == 0:
            assembled.extend(sorted(phase_tracks, key=lambda x: phase_tracks.index(x)))
            continue
        prev_valence = phases[idx - 1].get("valence", 0.5)
        curr_valence = phases[idx].get("valence", 0.5)
        midpoint = (prev_valence + curr_valence) / 2
        transition_window = [t for t in phase_tracks if abs(t.score - midpoint) < 0.3]
        remainder = [t for t in phase_tracks if t not in transition_window]
        assembled.extend(transition_window)
        assembled.extend(remainder)
    return assembled


def generate_playlist_for_analysis(analysis: Dict[str, object], limit: int = 35) -> List[Dict[str, object]]:
    """Main entry: build a rich playlist using analyzed prompt phases."""

    phases: List[Dict[str, object]] = analysis.get("phases", [])  # type: ignore[assignment]
    if not phases:
        logger.warning("No phases detected; falling back to a single generic phase")
        fallback_phase = {
            "role": "single",
            "raw_text": analysis.get("prompt", ""),
            "artists": analysis.get("artists", []),
            "genres": analysis.get("genres", []),
            "moods": analysis.get("moods", []),
            "vibes": analysis.get("vibes", []),
            "tempo_range": (80, 140),
            "energy": analysis.get("intensity", 0.5),
            "valence": 0.5,
        }
        phases = [fallback_phase]

    slice_sizes = _phase_slice_sizes(len(phases), limit)
    per_phase_tracks: List[List[ScoredTrack]] = []
    for phase, slice_size in zip(phases, slice_sizes):
        candidates = _collect_phase_candidates(phase, limit=max(slice_size * 2, 10))
        per_phase_tracks.append(candidates[: slice_size * 2])
        logger.info(
            "Phase '%s' collected %d candidates", phase.get("role", "unknown"), len(candidates)
        )

    ordered = _smooth_transition(phases, per_phase_tracks)
    # shuffle lightly inside small windows to avoid predictability
    random.shuffle(ordered)

    final_tracks: List[Dict[str, object]] = []
    seen = set()
    for item in ordered:
        info = track_to_dict(item.track)
        if not info or info["track_id"] in seen:
            continue
        seen.add(info["track_id"])
        final_tracks.append(info)
        if len(final_tracks) >= limit:
            break

    # If still empty, try a broad rotor/mood search as a last resort
    if not final_tracks:
        logger.warning("Primary generation empty; using mood station fallback")
        fallback_tracks = fetch_mood_station_tracks(analysis.get("moods", []), analysis.get("vibes", []), limit=limit)
        for track in fallback_tracks:
            info = track_to_dict(track)
            if info and info["track_id"] not in seen:
                final_tracks.append(info)
                if len(final_tracks) >= limit:
                    break

    logger.info("Generated %d final playlist tracks", len(final_tracks))
    return final_tracks

