"""Tests for src/validation.py (input validation and normalization)."""

import copy

import pytest

from src.validation import ValidationError, validate_and_normalize_profile


def valid_prefs() -> dict:
    """A fresh, valid user preference dictionary for each test to modify."""
    return {
        "genre": "pop",
        "mood": "happy",
        "target_energy": 0.8,
        "likes_acoustic": False,
    }


def test_valid_profile_returns_normalized_copy():
    prefs = valid_prefs()
    result = validate_and_normalize_profile(prefs)

    assert result == {
        "genre": "pop",
        "mood": "happy",
        "target_energy": 0.8,
        "likes_acoustic": False,
    }
    # target_energy is always returned as a float.
    assert isinstance(result["target_energy"], float)


def test_normalizes_capitalization_and_whitespace():
    prefs = valid_prefs()
    prefs["genre"] = "  Pop  "
    prefs["mood"] = "HAPPY"

    result = validate_and_normalize_profile(prefs)

    assert result["genre"] == "pop"
    assert result["mood"] == "happy"


def test_integer_energy_is_coerced_to_float():
    prefs = valid_prefs()
    prefs["target_energy"] = 1  # valid int at the upper bound

    result = validate_and_normalize_profile(prefs)

    assert result["target_energy"] == 1.0
    assert isinstance(result["target_energy"], float)


def test_non_dict_input_is_rejected():
    with pytest.raises(ValidationError):
        validate_and_normalize_profile(["not", "a", "dict"])


def test_missing_required_field_is_rejected():
    prefs = valid_prefs()
    del prefs["target_energy"]

    with pytest.raises(ValidationError):
        validate_and_normalize_profile(prefs)


def test_empty_genre_is_rejected():
    prefs = valid_prefs()
    prefs["genre"] = "   "  # whitespace only -> empty after strip

    with pytest.raises(ValidationError):
        validate_and_normalize_profile(prefs)


def test_empty_mood_is_rejected():
    prefs = valid_prefs()
    prefs["mood"] = ""

    with pytest.raises(ValidationError):
        validate_and_normalize_profile(prefs)


def test_non_string_genre_is_rejected():
    prefs = valid_prefs()
    prefs["genre"] = 123

    with pytest.raises(ValidationError):
        validate_and_normalize_profile(prefs)


def test_non_string_mood_is_rejected():
    prefs = valid_prefs()
    prefs["mood"] = ["happy"]

    with pytest.raises(ValidationError):
        validate_and_normalize_profile(prefs)


def test_energy_below_zero_is_rejected():
    prefs = valid_prefs()
    prefs["target_energy"] = -0.1

    with pytest.raises(ValidationError):
        validate_and_normalize_profile(prefs)


def test_energy_above_one_is_rejected():
    prefs = valid_prefs()
    prefs["target_energy"] = 1.5

    with pytest.raises(ValidationError):
        validate_and_normalize_profile(prefs)


def test_energy_at_lower_boundary_is_accepted():
    prefs = valid_prefs()
    prefs["target_energy"] = 0  # inclusive lower bound

    result = validate_and_normalize_profile(prefs)

    assert result["target_energy"] == 0.0
    assert isinstance(result["target_energy"], float)


def test_nan_energy_is_rejected():
    prefs = valid_prefs()
    prefs["target_energy"] = float("nan")

    with pytest.raises(ValidationError):
        validate_and_normalize_profile(prefs)


def test_infinite_energy_is_rejected():
    prefs = valid_prefs()
    prefs["target_energy"] = float("inf")

    with pytest.raises(ValidationError):
        validate_and_normalize_profile(prefs)


def test_non_numeric_energy_is_rejected():
    prefs = valid_prefs()
    prefs["target_energy"] = "0.8"

    with pytest.raises(ValidationError):
        validate_and_normalize_profile(prefs)


def test_boolean_energy_is_rejected():
    prefs = valid_prefs()
    prefs["target_energy"] = True  # bool is a subclass of int, must still be rejected

    with pytest.raises(ValidationError):
        validate_and_normalize_profile(prefs)


def test_non_boolean_likes_acoustic_is_rejected():
    prefs = valid_prefs()
    prefs["likes_acoustic"] = "yes"

    with pytest.raises(ValidationError):
        validate_and_normalize_profile(prefs)


def test_original_dictionary_is_not_mutated():
    prefs = valid_prefs()
    prefs["genre"] = "  Pop  "
    prefs["mood"] = "HAPPY"
    original_snapshot = copy.deepcopy(prefs)

    result = validate_and_normalize_profile(prefs)

    # The input is untouched...
    assert prefs == original_snapshot
    # ...and the returned object is a different dictionary.
    assert result is not prefs
