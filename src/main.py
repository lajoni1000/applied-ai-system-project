"""
Command line runner for the Music Recommender Simulation.

This file helps you quickly run and test your recommender.

Each profile is now validated and normalized (see src/validation.py) before
recommendations are generated. Invalid profiles are reported and skipped so a
single bad profile never stops the rest of the run.
"""

import logging
import textwrap

from src.explanations import build_fallback_explanation, build_recommendation_context
from src.guardrails import validate_explanation
from src.llm_service import LLMServiceError, generate_explanation
from src.recommender import load_songs, recommend_songs
from src.validation import ValidationError, validate_and_normalize_profile

logger = logging.getLogger(__name__)


# Phase 4 evaluation profiles. Each entry pairs a display "name" with the
# "prefs" dict that score_song expects (favorite_genre, favorite_mood,
# target_energy, likes_acoustic). Genre/mood values all exist in songs.csv.
PROFILES = [
    {
        "name": "1. High-energy (aligned preferences)",
        "prefs": {"favorite_genre": "edm", "favorite_mood": "uplifting", "target_energy": 0.95, "likes_acoustic": False},
    },
    {
        "name": "2. Low-energy / chill (with acoustic bonus)",
        "prefs": {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 0.35, "likes_acoustic": True},
    },
    {
        "name": "3. Different genre and mood (r&b / romantic)",
        "prefs": {"favorite_genre": "r&b", "favorite_mood": "romantic", "target_energy": 0.48, "likes_acoustic": False},
    },
    {
        "name": "4a. ADVERSARIAL: conflicting genre vs mood (metal / happy)",
        "prefs": {"favorite_genre": "metal", "favorite_mood": "happy", "target_energy": 0.90, "likes_acoustic": False},
    },
    {
        "name": "4b. EDGE CASE: out-of-range target_energy (1.5)",
        "prefs": {"favorite_genre": "pop", "favorite_mood": "happy", "target_energy": 1.5, "likes_acoustic": False},
    },
]


# The validator uses the field names genre/mood, while the recommender and the
# PROFILES above use favorite_genre/favorite_mood. These two helpers translate
# between the two schemas so neither recommender.py nor validation.py has to
# change. Only keys that are present are copied, so a genuinely missing field
# is still reported as "missing" by the validator.
_TO_VALIDATOR = {
    "favorite_genre": "genre",
    "favorite_mood": "mood",
    "target_energy": "target_energy",
    "likes_acoustic": "likes_acoustic",
}


def to_validator_schema(prefs: dict) -> dict:
    """Rename recommender-style keys to the ones validate_and_normalize_profile expects."""
    return {dst: prefs[src] for src, dst in _TO_VALIDATOR.items() if src in prefs}


def to_recommender_schema(normalized: dict) -> dict:
    """Rename validated keys back to the ones score_song expects."""
    return {
        "favorite_genre": normalized["genre"],
        "favorite_mood": normalized["mood"],
        "target_energy": normalized["target_energy"],
        "likes_acoustic": normalized["likes_acoustic"],
    }


def print_heading(name: str) -> None:
    """Print the profile heading and flush it, so it appears before any
    validation log messages (which are written to stderr during validation)."""
    print()
    print("=" * 60)
    print(f"PROFILE: {name}")
    print("=" * 60, flush=True)


def print_recommendations(prefs: dict, recommendations: list) -> None:
    """Print one profile's preferences and its top recommendations.

    The heading is printed separately by print_heading before validation runs.
    """
    print("Profile:")
    print(f"  Favorite Genre: {prefs['favorite_genre']}")
    print(f"  Favorite Mood: {prefs['favorite_mood']}")
    print(f"  Target Energy: {prefs['target_energy']}")
    print(f"  Likes Acoustic: {'YES' if prefs['likes_acoustic'] else 'NO'}")

    # One numbered block per recommendation: title/artist, score, reasons
    for rank, (song, score, explanation) in enumerate(recommendations, start=1):
        print(f"\n  {rank}. {song['title']} - {song['artist']}")
        print(f"     Score: {score:.2f}")
        for reason in explanation.split("; "):
            print(f"       - {reason}")

    print()


def print_validation_error(error: ValidationError) -> None:
    """Report that the current profile was skipped because it failed validation."""
    print(f"  [SKIPPED] Invalid profile: {error}")
    print()


# Short controlled notices explaining why a deterministic fallback is shown.
_FALLBACK_NOTICES = {
    "fallback_error": "  (AI explanation unavailable - showing deterministic fallback)",
    "fallback_rejected": "  (AI explanation failed the grounding guardrail - showing deterministic fallback)",
}


def generate_or_fallback_explanation(prefs: dict, recommendations: list) -> tuple:
    """Build the grounded context, generate an explanation, and guard it.

    Returns (explanation_text, source) where source is one of:
        "ai"                - Gemini produced text that passed the guardrail
        "fallback_error"    - the LLM was unavailable / failed
        "fallback_rejected" - the LLM text was rejected by the guardrail
    Never raises: any problem is turned into a deterministic fallback.
    """
    context = build_recommendation_context(prefs, recommendations)

    try:
        candidate = generate_explanation(context)
    except LLMServiceError as error:
        logger.warning("LLM explanation failed, using deterministic fallback: %s", error)
        return build_fallback_explanation(prefs, recommendations), "fallback_error"

    is_valid, issues = validate_explanation(candidate, recommendations)
    if not is_valid:
        logger.warning("LLM explanation rejected by guardrail: %s", "; ".join(issues))
        return build_fallback_explanation(prefs, recommendations), "fallback_rejected"

    return candidate, "ai"


def print_ai_explanation(explanation: str, source: str) -> None:
    """Print the explanation under an AI EXPLANATION heading, wrapped for the CLI."""
    print("AI EXPLANATION")
    print("-" * 60)
    notice = _FALLBACK_NOTICES.get(source)
    if notice:
        print(notice)
    print(textwrap.fill(explanation, width=76, initial_indent="  ", subsequent_indent="  "))
    print()


def main() -> None:
    songs = load_songs("data/songs.csv")  # load the catalog once, reused for every profile

    # Evaluate each profile with the same k and output format. Validation runs
    # first; if it fails we report the problem and continue with the next profile.
    for profile in PROFILES:
        # Print the heading first so the user always sees which profile is being
        # processed before any validation (log) output appears.
        print_heading(profile["name"])

        try:
            normalized = validate_and_normalize_profile(to_validator_schema(profile["prefs"]))
        except ValidationError as error:
            print_validation_error(error)
            continue

        prefs = to_recommender_schema(normalized)
        recommendations = recommend_songs(prefs, songs, k=5)
        print_recommendations(prefs, recommendations)

        # Generate a friendly AI explanation, falling back to the deterministic
        # one if the LLM is unavailable. Either way, the run continues.
        explanation, source = generate_or_fallback_explanation(prefs, recommendations)
        print_ai_explanation(explanation, source)


if __name__ == "__main__":
    main()
