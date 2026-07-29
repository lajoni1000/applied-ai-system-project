"""Tests for the CLI runner's validation integration (src/main.py)."""

from src import main


def test_main_runs_without_crashing_on_invalid_profile(capsys):
    # The full PROFILES list includes an out-of-range energy (1.5) profile.
    # main() must handle it gracefully and still process the valid profiles.
    main.main()
    out = capsys.readouterr().out

    # A valid profile produced real recommendations...
    assert "Voltage Rising" in out
    assert "Score:" in out
    # ...and the invalid profile (4b, energy = 1.5) was skipped, not crashed.
    assert "[SKIPPED] Invalid profile" in out
    assert "target_energy must be between 0.0 and 1.0" in out


def test_valid_profiles_are_not_skipped(capsys):
    # Only the single out-of-range profile should be skipped; the other four run.
    main.main()
    out = capsys.readouterr().out
    assert out.count("[SKIPPED]") == 1


def test_schema_adapters_round_trip():
    prefs = {
        "favorite_genre": "pop",
        "favorite_mood": "happy",
        "target_energy": 0.8,
        "likes_acoustic": False,
    }
    validator_view = main.to_validator_schema(prefs)
    assert validator_view == {
        "genre": "pop",
        "mood": "happy",
        "target_energy": 0.8,
        "likes_acoustic": False,
    }

    back = main.to_recommender_schema(validator_view)
    assert back == prefs


def test_to_validator_schema_omits_missing_keys():
    # A missing favorite_genre must stay absent so the validator reports it missing.
    partial = {"favorite_mood": "happy", "target_energy": 0.5, "likes_acoustic": True}
    validator_view = main.to_validator_schema(partial)
    assert "genre" not in validator_view
    assert validator_view["mood"] == "happy"
