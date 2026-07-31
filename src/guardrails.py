"""
Explanation guardrail (lightweight, deterministic).

This module is the "Explanation Guardrail" stage of the Applied AI architecture
(see diagrams/architecture.mmd). It decides whether an LLM-generated explanation
is safe to show, based only on cheap, deterministic checks - NOT semantic
fact-checking. If the explanation fails, the caller falls back to the
deterministic explanation from src/explanations.py.

An explanation is rejected when it:
  - is empty or whitespace-only
  - exceeds MAX_WORDS words
  - contains obvious placeholder text ("Song A", "Track 1", "unknown artist")
  - names a quoted song title that was not retrieved (hallucination)
  - fails to mention the top recommendation's title

Song-title matching is case-insensitive. Not every recommended song has to be
mentioned - only the top one.
"""

import logging
import re
from typing import Any, Dict, List, NamedTuple, Tuple

logger = logging.getLogger(__name__)

# An explanation longer than this many words is rejected as too verbose.
MAX_WORDS = 180

# Obvious placeholder patterns that a grounded explanation should never contain.
# Matched against the original text so the capital-letter forms stay precise and
# do not trip on ordinary prose (e.g. "each song a listener enjoys").
PLACEHOLDER_PATTERNS = [
    (re.compile(r"\bSong [A-Z]\b"), "Song A"),
    (re.compile(r"\bTrack \d+\b"), "Track 1"),
    (re.compile(r"\bunknown artist\b", re.IGNORECASE), "unknown artist"),
]

# Phrases wrapped in straight or curly double quotes are treated as claimed
# song titles and checked against the retrieved recommendations.
_QUOTED_TITLE = re.compile(r'["“”]([^"“”]+)["“”]')


class GuardrailResult(NamedTuple):
    """Result of a guardrail check. Unpacks as (is_valid, issues)."""
    is_valid: bool
    issues: List[str]


def validate_explanation(explanation: str, recommendations: List[Any]) -> Tuple[bool, List[str]]:
    """Validate a generated explanation against the retrieved recommendations.

    Returns a (is_valid, issues) tuple. `issues` is empty when valid and lists
    every reason for rejection otherwise. Accepts recommendations either as song
    dicts or as the recommender's (song, score, reasons) tuples.
    """
    if not isinstance(explanation, str) or not explanation.strip():
        return GuardrailResult(False, ["explanation is empty"])

    issues: List[str] = []

    word_count = len(explanation.split())
    if word_count > MAX_WORDS:
        issues.append(f"explanation exceeds {MAX_WORDS} words ({word_count})")

    for pattern, label in PLACEHOLDER_PATTERNS:
        if pattern.search(explanation):
            issues.append(f"contains placeholder text ({label!r})")

    titles = [_title_of(item) for item in recommendations]
    if not titles:
        issues.append("no recommendations to validate against")
        return GuardrailResult(False, issues)

    valid_titles = {title.lower() for title in titles}
    lowered = explanation.lower()

    # Any quoted phrase that is not a retrieved title is treated as hallucinated.
    for quoted in _QUOTED_TITLE.findall(explanation):
        normalized_quoted = quoted.strip().strip(".,!?;:")
        if normalized_quoted.lower() not in valid_titles:
            issues.append(
                f"mentions a song not in the recommendations: {normalized_quoted!r}"
        )

    # The top recommendation must be named (case-insensitive, anywhere in text).
    top_title = titles[0]
    if top_title.lower() not in lowered:
        issues.append(f"does not mention the top recommendation: {top_title!r}")

    is_valid = not issues
    if not is_valid:
        logger.info("guardrail rejected explanation: %s", "; ".join(issues))
    return GuardrailResult(is_valid, issues)


def _title_of(item: Any) -> str:
    """Get a song title from either a song dict or a (song, score, reasons) tuple."""
    song: Dict[str, Any] = item if isinstance(item, dict) else item[0]
    return str(song["title"])
