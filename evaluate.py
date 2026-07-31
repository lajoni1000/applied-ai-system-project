"""
Deterministic evaluation harness for the Applied AI music recommender.

This is the "Evaluation Script" stage of the architecture (see
diagrams/architecture.mmd). It runs a fixed set of cases against the real
project functions - validation, recommendation, explanation context, the
deterministic fallback, and the guardrail - and prints a pass/fail summary.

It NEVER calls the real Gemini API: LLM behavior is simulated deterministically
(a crafted explanation string, or a simulated outage), so the evaluation is
reproducible and free. Exit code is 0 when everything passes, 1 otherwise.

Run it from the project root:

    python evaluate.py
"""

import sys
from dataclasses import dataclass
from typing import Callable, List, Tuple

from src.explanations import build_fallback_explanation, build_recommendation_context
from src.guardrails import validate_explanation
from src.llm_service import LLMServiceError
from src.main import to_recommender_schema, to_validator_schema
from src.recommender import load_songs, recommend_songs
from src.validation import ValidationError, validate_and_normalize_profile

SONGS_PATH = "data/songs.csv"

# Test profiles in the recommender's schema (favorite_genre / favorite_mood).
ALIGNED = {"favorite_genre": "edm", "favorite_mood": "uplifting", "target_energy": 0.95, "likes_acoustic": False}
CHILL = {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 0.35, "likes_acoustic": True}
CONFLICT = {"favorite_genre": "metal", "favorite_mood": "happy", "target_energy": 0.90, "likes_acoustic": False}
INVALID_ENERGY = {"favorite_genre": "pop", "favorite_mood": "happy", "target_energy": 1.5, "likes_acoustic": False}


@dataclass
class CaseResult:
    """The outcome of one evaluation case."""
    name: str
    expected: str
    actual: str
    passed: bool


def _recommend(prefs: dict, songs: list, k: int = 5) -> Tuple[dict, list]:
    """Validate a raw profile and return (recommender_prefs, recommendations)."""
    normalized = validate_and_normalize_profile(to_validator_schema(prefs))
    rec_prefs = to_recommender_schema(normalized)
    return rec_prefs, recommend_songs(rec_prefs, songs, k=k)


# --- individual evaluation cases -------------------------------------------

def case_valid_aligned(songs: list) -> CaseResult:
    expected = 'top recommendation is "Voltage Rising"'
    _, recs = _recommend(ALIGNED, songs)
    top = recs[0][0]["title"]
    return CaseResult("Valid aligned profile (edm / uplifting)", expected, f'top = "{top}"', top == "Voltage Rising")


def case_valid_chill(songs: list) -> CaseResult:
    expected = 'top recommendation is "Library Rain"'
    _, recs = _recommend(CHILL, songs)
    top = recs[0][0]["title"]
    return CaseResult("Valid low-energy / acoustic profile (lofi / chill)", expected, f'top = "{top}"', top == "Library Rain")


def case_conflicting_genre_mood(songs: list) -> CaseResult:
    expected = 'genre wins the tie -> top is "Iron Verdict"'
    _, recs = _recommend(CONFLICT, songs)
    top = recs[0][0]["title"]
    return CaseResult("Conflicting genre vs mood (metal / happy)", expected, f'top = "{top}"', top == "Iron Verdict")


def case_invalid_energy_rejected(songs: list) -> CaseResult:
    expected = "validation rejects out-of-range energy (1.5)"
    try:
        validate_and_normalize_profile(to_validator_schema(INVALID_ENERGY))
        return CaseResult("Invalid out-of-range energy (1.5)", expected, "accepted (no error raised)", False)
    except ValidationError as error:
        return CaseResult("Invalid out-of-range energy (1.5)", expected, f"rejected: {error}", True)


def case_guardrail_rejects_hallucination(songs: list) -> CaseResult:
    expected = "guardrail rejects a hallucinated quoted title"
    _, recs = _recommend(CHILL, songs)
    top = recs[0][0]["title"]
    # Mentions the real top title, but also a quoted song that was never retrieved.
    text = f'{top} is a lovely calm pick, but "Imaginary Anthem" is the real star here.'
    is_valid, issues = validate_explanation(text, recs)
    return CaseResult(
        "Guardrail rejects hallucinated title",
        expected,
        f"is_valid={is_valid}; issues={issues}",
        is_valid is False,
    )


def case_guardrail_accepts_grounded(songs: list) -> CaseResult:
    expected = "guardrail accepts a grounded explanation"
    _, recs = _recommend(CHILL, songs)
    top = recs[0][0]["title"]
    text = f"{top} is a calm, cozy lofi choice that matches your relaxed, chill mood perfectly."
    is_valid, issues = validate_explanation(text, recs)
    return CaseResult(
        "Guardrail accepts grounded explanation",
        expected,
        f"is_valid={is_valid}; issues={issues}",
        is_valid is True,
    )


def case_llm_failure_falls_back(songs: list) -> CaseResult:
    expected = "LLM outage -> valid deterministic fallback is used"
    rec_prefs, recs = _recommend(ALIGNED, songs)

    # Simulate the generator being unavailable, exactly like main.py handles it.
    context = build_recommendation_context(rec_prefs, recs)

    def failing_llm(_context: str) -> str:
        raise LLMServiceError("simulated outage")

    try:
        text = failing_llm(context)
        source = "ai"
    except LLMServiceError:
        text = build_fallback_explanation(rec_prefs, recs)
        source = "fallback"

    is_valid, _issues = validate_explanation(text, recs)
    passed = source == "fallback" and bool(text.strip()) and is_valid
    return CaseResult(
        "Simulated LLM failure -> fallback",
        expected,
        f"source={source}; fallback_non_empty={bool(text.strip())}; guardrail_valid={is_valid}",
        passed,
    )


def default_cases() -> List[Callable[[list], CaseResult]]:
    """The list of evaluation cases run by default."""
    return [
        case_valid_aligned,
        case_valid_chill,
        case_conflicting_genre_mood,
        case_invalid_energy_rejected,
        case_guardrail_rejects_hallucination,
        case_guardrail_accepts_grounded,
        case_llm_failure_falls_back,
    ]


# --- runner / reporting ----------------------------------------------------

def run_evaluation(songs: list = None, cases: List[Callable[[list], CaseResult]] = None) -> List[CaseResult]:
    """Run every case and return a list of CaseResult. Never raises."""
    if songs is None:
        songs = load_songs(SONGS_PATH)
    if cases is None:
        cases = default_cases()

    results: List[CaseResult] = []
    for case in cases:
        try:
            results.append(case(songs))
        except Exception as error:  # a crashing case is a failed case, not a crashed run
            results.append(CaseResult(case.__name__, "case runs without error", f"error: {error}", False))
    return results


def summarize(results: List[CaseResult]) -> Tuple[int, int]:
    """Return (passed, failed) counts."""
    passed = sum(1 for result in results if result.passed)
    return passed, len(results) - passed


def exit_code(results: List[CaseResult]) -> int:
    """0 if all cases passed, 1 if any failed."""
    _, failed = summarize(results)
    return 0 if failed == 0 else 1


def print_report(results: List[CaseResult]) -> None:
    """Print each case's outcome and a final summary."""
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"[{status}] {result.name}")
        print(f"       expected: {result.expected}")
        print(f"       actual:   {result.actual}")

    passed, failed = summarize(results)
    total = len(results)
    percent = (passed / total * 100) if total else 0.0

    print()
    print("Evaluation Summary")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Score: {passed}/{total} ({percent:.1f}%)")


def main() -> int:
    """Run the evaluation, print the report, and return the process exit code."""
    results = run_evaluation()
    print_report(results)
    return exit_code(results)


if __name__ == "__main__":
    sys.exit(main())
