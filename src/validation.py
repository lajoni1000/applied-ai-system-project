"""
Input validation and normalization for user preference profiles.

This module is the "Input Validation" and "User Profile Normalization"
stage of the Applied AI architecture (see diagrams/architecture.mmd).
It runs *before* the recommender so that malformed or out-of-range
preferences (for example, target_energy = 1.5) are rejected with a clear
error instead of silently producing unreliable recommendations.

No LLM code and no API keys live here on purpose - this stage is purely
deterministic validation and normalization.
"""

import logging
import math
from typing import Any, Dict

logger = logging.getLogger(__name__)

# The fields every user preference dictionary must provide.
REQUIRED_FIELDS = ("genre", "mood", "target_energy", "likes_acoustic")

# Inclusive bounds for the normalized energy value.
ENERGY_MIN = 0.0
ENERGY_MAX = 1.0


class ValidationError(ValueError):
    """Raised when a user preference dictionary is missing fields or invalid."""


def validate_and_normalize_profile(user_prefs: Any) -> Dict[str, Any]:
    """Validate a user preference dictionary and return a normalized copy.

    Expected fields:
        genre          non-empty string
        mood           non-empty string
        target_energy  number in [0.0, 1.0] (bool is rejected)
        likes_acoustic boolean

    Normalization:
        genre and mood are stripped of surrounding whitespace and lowercased,
        and target_energy is coerced to float.

    The input dictionary is never mutated; a new dictionary is returned.

    Raises:
        ValidationError: if any field is missing, wrongly typed, or out of range.
    """
    # Must be a dictionary before we can look anything up.
    if not isinstance(user_prefs, dict):
        _fail(f"user_prefs must be a dict, got {type(user_prefs).__name__}")

    # All required fields must be present.
    missing = [field for field in REQUIRED_FIELDS if field not in user_prefs]
    if missing:
        _fail(f"missing required field(s): {', '.join(missing)}")

    genre = _validate_text_field("genre", user_prefs["genre"])
    mood = _validate_text_field("mood", user_prefs["mood"])
    target_energy = _validate_energy(user_prefs["target_energy"])
    likes_acoustic = _validate_likes_acoustic(user_prefs["likes_acoustic"])

    # Build a brand-new dict so the caller's original is left untouched.
    normalized: Dict[str, Any] = {
        "genre": genre,
        "mood": mood,
        "target_energy": target_energy,
        "likes_acoustic": likes_acoustic,
    }

    logger.info(
        "validation succeeded: genre=%s, mood=%s, target_energy=%.2f, likes_acoustic=%s",
        genre,
        mood,
        target_energy,
        likes_acoustic,
    )
    return normalized


def _validate_text_field(field: str, value: Any) -> str:
    """Ensure a text field is a non-empty string; return it trimmed and lowercased."""
    if not isinstance(value, str):
        _fail(f"{field} must be a string, got {type(value).__name__}")

    normalized = value.strip().lower()
    if not normalized:
        _fail(f"{field} must not be empty")

    return normalized


def _validate_energy(value: Any) -> float:
    """Ensure target_energy is a real number within [0.0, 1.0]; return it as float."""
    # bool is a subclass of int, so reject it explicitly before the numeric check.
    if isinstance(value, bool):
        _fail("target_energy must be a number, got bool")

    if not isinstance(value, (int, float)):
        _fail(f"target_energy must be a number, got {type(value).__name__}")

    energy = float(value)
    # Reject NaN and +/- infinity before the range check (NaN comparisons are
    # always False, so it would otherwise slip past the bounds test).
    if not math.isfinite(energy):
        _fail(f"target_energy must be a finite number, got {energy}")

    if energy < ENERGY_MIN or energy > ENERGY_MAX:
        _fail(f"target_energy must be between {ENERGY_MIN} and {ENERGY_MAX}, got {energy}")

    return energy


def _validate_likes_acoustic(value: Any) -> bool:
    """Ensure likes_acoustic is a genuine boolean."""
    if not isinstance(value, bool):
        _fail(f"likes_acoustic must be a bool, got {type(value).__name__}")
    return value


def _fail(message: str) -> None:
    """Log a validation failure and raise ValidationError with the same message."""
    logger.warning("validation failed: %s", message)
    raise ValidationError(message)
