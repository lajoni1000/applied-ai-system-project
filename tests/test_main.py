"""Tests for the CLI runner (src/main.py): validation + AI-explanation integration.

The Gemini call is always mocked here (via main.generate_explanation), so these
tests never make a real API request.
"""

import re
from unittest.mock import MagicMock

import pytest

from src import main
from src.llm_service import LLMServiceError


def flatten(text: str) -> str:
    """Collapse all whitespace so assertions survive textwrap line wrapping."""
    return " ".join(text.split())


@pytest.fixture
def mock_ai_success(monkeypatch):
    """Patch the LLM to return a guardrail-valid explanation for each profile.

    It names the top recommendation (read from the context) so the guardrail
    accepts it, and embeds a sentinel token we can assert on.
    """
    def fake(context):
        match = re.search(r'"([^"]+)"', context)  # first quoted title = top pick
        top_title = match.group(1) if match else "your top pick"
        return f"AITEXT_SENTINEL_ok {top_title} is a wonderful match for your mood and energy."

    monkeypatch.setattr(main, "generate_explanation", fake)
    return "AITEXT_SENTINEL_ok"


@pytest.fixture
def mock_ai_failure(monkeypatch):
    """Patch the LLM so every call raises LLMServiceError."""
    def boom(context):
        raise LLMServiceError("api unavailable")

    monkeypatch.setattr(main, "generate_explanation", boom)


# --- existing behavior (now with the LLM mocked) ---------------------------

def test_main_runs_without_crashing_on_invalid_profile(capsys, mock_ai_success):
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


def test_valid_profiles_are_not_skipped(capsys, mock_ai_success):
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


# --- AI explanation integration --------------------------------------------

def test_valid_ai_output_is_displayed(capsys, mock_ai_success):
    main.main()
    out = capsys.readouterr().out

    assert "AI EXPLANATION" in out
    assert mock_ai_success in out
    # On success, no fallback notice of either kind must appear.
    assert "showing deterministic fallback" not in out
    assert "guardrail" not in out


def test_rejected_ai_output_triggers_fallback(monkeypatch, capsys):
    # This text has placeholders and never names any real top title -> rejected
    # by the guardrail for every profile, so all four fall back deterministically.
    monkeypatch.setattr(
        main, "generate_explanation", lambda context: "This pick is Song A and Track 1 for you."
    )
    main.main()
    out = flatten(capsys.readouterr().out)

    # Guardrail notice shown once per valid profile, and deterministic text used.
    assert out.count("failed the grounding guardrail") == 4
    assert "Top recommendation:" in out
    # The rejected AI text must not be displayed.
    assert "Song A" not in out
    assert out.count("[SKIPPED]") == 1


def test_llm_error_causes_fallback_explanation(capsys, mock_ai_failure):
    main.main()
    out = flatten(capsys.readouterr().out)

    # The controlled fallback notice and deterministic text should appear...
    assert "showing deterministic fallback" in out
    assert "Top recommendation:" in out
    # ...and the AI sentinel must be absent because generation failed.
    assert "AITEXT_SENTINEL_ok" not in out


def test_processing_continues_after_llm_failure(capsys, mock_ai_failure):
    # Even though every LLM call fails, all four valid profiles must still run.
    main.main()
    out = flatten(capsys.readouterr().out)

    # Songs from different profiles both appear -> the loop kept going.
    assert "Voltage Rising" in out          # profile 1
    assert "Velvet Hours" in out            # profile 3
    # One fallback notice per valid profile (4 valid, 1 invalid).
    assert out.count("showing deterministic fallback") == 4
    assert out.count("[SKIPPED]") == 1


def test_invalid_profile_skipped_before_any_gemini_call(monkeypatch, capsys):
    # Run with ONLY the invalid profile; the LLM must never be called.
    llm = MagicMock()
    monkeypatch.setattr(main, "generate_explanation", llm)
    monkeypatch.setattr(main, "PROFILES", [main.PROFILES[4]])  # 4b: energy = 1.5

    main.main()

    llm.assert_not_called()
    out = capsys.readouterr().out
    assert "[SKIPPED]" in out
    assert "AI EXPLANATION" not in out
