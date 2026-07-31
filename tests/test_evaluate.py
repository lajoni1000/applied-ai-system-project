"""Tests for evaluate.py (the deterministic evaluation harness)."""

from unittest.mock import MagicMock

import evaluate
from src import llm_service


def test_all_default_cases_pass():
    results = evaluate.run_evaluation()
    assert len(results) >= 6
    failures = [(r.name, r.actual) for r in results if not r.passed]
    assert failures == [], f"unexpected failing cases: {failures}"


def test_summary_counts_are_correct():
    results = evaluate.run_evaluation()
    passed, failed = evaluate.summarize(results)
    assert passed + failed == len(results)
    assert passed == len(results)
    assert failed == 0


def test_exit_code_zero_when_all_pass():
    results = evaluate.run_evaluation()
    assert evaluate.exit_code(results) == 0


def test_exit_code_one_when_any_case_fails():
    results = [
        evaluate.CaseResult("ok", "expected", "actual", True),
        evaluate.CaseResult("bad", "expected", "actual", False),
    ]
    passed, failed = evaluate.summarize(results)
    assert (passed, failed) == (1, 1)
    assert evaluate.exit_code(results) == 1


def test_no_gemini_call_is_made(monkeypatch):
    # Fail loudly if anything tries to generate text or build a real client.
    fake_generate = MagicMock()
    monkeypatch.setattr(llm_service, "generate_explanation", fake_generate)

    def explode(*args, **kwargs):
        raise AssertionError("a real Gemini client must not be constructed")

    monkeypatch.setattr(llm_service.genai, "Client", explode)

    results = evaluate.run_evaluation()

    fake_generate.assert_not_called()
    assert all(r.passed for r in results)


def test_main_prints_summary_and_returns_zero(capsys):
    code = evaluate.main()
    out = capsys.readouterr().out

    assert code == 0
    assert "Evaluation Summary" in out
    assert "Score:" in out
    assert "Passed:" in out
