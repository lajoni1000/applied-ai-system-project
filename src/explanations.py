"""
Explanation layer for the music recommender (deterministic half).

This module is the "Build LLM Context" and "Deterministic Fallback" stages of
the Applied AI architecture (see diagrams/architecture.mmd). It has NO LLM code,
NO API keys, and makes NO network calls - everything here is computed only from
the validated user profile and the songs the recommender actually retrieved.

    build_recommendation_context  -> the grounded, plain-text context an LLM
                                      would later be given (facts only).
    build_fallback_explanation    -> the deterministic explanation used when the
                                      LLM is unavailable or its output is rejected.
"""

import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

# A single recommendation in the recommender's existing output format.
Recommendation = Tuple[Dict[str, Any], float, str]

# Matches the recommender's acoustic threshold in score_song: a song counts as
# "acoustic" when its acousticness is above this value.
ACOUSTIC_THRESHOLD = 0.6


def build_recommendation_context(profile: Dict[str, Any], recommendations: List[Recommendation]) -> str:
    """Build a grounded, plain-text context from the profile and retrieved songs.

    The returned text contains only facts that are present in the profile and in
    the retrieved recommendations - no invented song attributes. This is what a
    later LLM stage would be asked to explain, so it must stay strictly factual.
    """
    lines: List[str] = ["User Preferences:"]
    lines.append(f"- Favorite Genre: {_pref(profile, 'genre')}")
    lines.append(f"- Favorite Mood: {_pref(profile, 'mood')}")
    lines.append(f"- Target Energy: {float(profile['target_energy']):.2f}")
    lines.append(f"- Likes Acoustic: {'yes' if profile['likes_acoustic'] else 'no'}")
    lines.append("")

    if not recommendations:
        lines.append("Retrieved Songs: (none)")
        logger.info("built recommendation context for 0 retrieved songs")
        return "\n".join(lines)

    lines.append("Retrieved Songs:")
    for rank, (song, score, reasons) in enumerate(recommendations, start=1):
        lines.append(f'{rank}. "{song["title"]}" by {song["artist"]}')
        lines.append(f"   - Genre: {song['genre']}")
        lines.append(f"   - Mood: {song['mood']}")
        lines.append(f"   - Energy: {float(song['energy']):.2f}")
        lines.append(
            f"   - Acoustic: {_acoustic_status(song['acousticness'])} "
            f"(acousticness {float(song['acousticness']):.2f})"
        )
        lines.append(f"   - Score: {float(score):.2f}")
        lines.append(f"   - Scoring reasons: {reasons}")

    logger.info("built recommendation context for %d retrieved song(s)", len(recommendations))
    return "\n".join(lines)


def build_fallback_explanation(profile: Dict[str, Any], recommendations: List[Recommendation]) -> str:
    """Build a deterministic explanation of the top recommendations.

    Uses only the retrieved recommendation data and the user's profile. Returns a
    non-empty string when recommendations exist, and a safe message otherwise.
    This is the guaranteed fallback when no LLM is available.
    """
    if not recommendations:
        logger.info("fallback explanation requested with no recommendations")
        return "No songs matched this profile, so there are no recommendations to explain."

    top_song, top_score, _reasons = recommendations[0]

    match_phrases = _match_phrases(profile, top_song)
    explanation = (
        f'Top recommendation: "{top_song["title"]}" by {top_song["artist"]} '
        f"(score {float(top_score):.2f}). It fits because "
        f"{', '.join(match_phrases)}."
    )

    # Name up to two runner-up songs, if the recommender returned more than one.
    others = recommendations[1:3]
    if others:
        other_titles = ", ".join(f'"{song["title"]}" by {song["artist"]}' for song, _, _ in others)
        explanation += f" Other strong matches include {other_titles}."

    logger.info("built fallback explanation for top song %r", top_song["title"])
    return explanation


def _match_phrases(profile: Dict[str, Any], song: Dict[str, Any]) -> List[str]:
    """Describe, in grounded terms, why a single song fits the profile."""
    phrases: List[str] = []

    if song["genre"] == _pref(profile, "genre"):
        phrases.append(f"its genre ({song['genre']}) matches your favorite genre")

    if song["mood"] == _pref(profile, "mood"):
        phrases.append(f"its mood ({song['mood']}) matches your preferred mood")

    # Energy always contributes to the score, so it is always worth mentioning.
    phrases.append(
        f"its energy ({float(song['energy']):.2f}) is close to your target energy "
        f"({float(profile['target_energy']):.2f})"
    )

    if profile["likes_acoustic"] and float(song["acousticness"]) > ACOUSTIC_THRESHOLD:
        phrases.append("and it is acoustic, which you prefer")

    return phrases


def _acoustic_status(acousticness: Any) -> str:
    """Return 'yes'/'no' for whether a song counts as acoustic."""
    return "yes" if float(acousticness) > ACOUSTIC_THRESHOLD else "no"


def _pref(profile: Dict[str, Any], key: str) -> Any:
    """Read a preference, tolerating both the validator schema (genre/mood) and
    the recommender schema (favorite_genre/favorite_mood)."""
    if key in profile:
        return profile[key]
    return profile.get(f"favorite_{key}")
