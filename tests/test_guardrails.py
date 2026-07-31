"""Tests for src/guardrails.py (lightweight deterministic explanation guardrail)."""

from src.guardrails import MAX_WORDS, validate_explanation


def song(title, artist="Some Artist") -> dict:
    return {"title": title, "artist": artist, "genre": "lofi", "mood": "chill"}


def recommendations() -> list:
    """(song, score, reasons) tuples; top recommendation is 'Library Rain'."""
    return [
        (song("Library Rain", "Paper Lanterns"), 4.50, "reasons"),
        (song("Midnight Coding", "LoRoom"), 4.43, "reasons"),
    ]


def test_valid_explanation_passes():
    text = (
        "Library Rain is a lovely, calm lofi pick that matches your relaxed mood, "
        "and Midnight Coding keeps that same easygoing feel."
    )
    is_valid, issues = validate_explanation(text, recommendations())
    assert is_valid is True
    assert issues == []


def test_empty_explanation_is_rejected():
    is_valid, issues = validate_explanation("   ", recommendations())
    assert is_valid is False
    assert issues  # at least one reason


def test_too_long_explanation_is_rejected():
    # Mention the top title so ONLY the length rule can fail.
    long_text = "Library Rain " + "word " * (MAX_WORDS + 5)
    is_valid, issues = validate_explanation(long_text, recommendations())
    assert is_valid is False
    assert any("word" in issue and str(MAX_WORDS) in issue for issue in issues)


def test_placeholder_text_is_rejected():
    text = "Library Rain is great, and so is Song A for your mood."
    is_valid, issues = validate_explanation(text, recommendations())
    assert is_valid is False
    assert any("placeholder" in issue for issue in issues)


def test_hallucinated_song_title_is_rejected():
    # A quoted title that was never retrieved.
    text = 'Library Rain is nice, but "Imaginary Anthem" is the real star here.'
    is_valid, issues = validate_explanation(text, recommendations())
    assert is_valid is False
    assert any("not in the recommendations" in issue for issue in issues)


def test_missing_top_recommendation_is_rejected():
    # Mentions a real (non-top) song but never the top one.
    text = "Midnight Coding is a mellow choice that suits your calm, chill evening."
    is_valid, issues = validate_explanation(text, recommendations())
    assert is_valid is False
    assert any("top recommendation" in issue for issue in issues)


def test_title_matching_is_case_insensitive():
    # Different casing of the top title must still count as mentioned.
    text = "LIBRARY RAIN is a wonderfully calm way to match your relaxed lofi mood."
    is_valid, issues = validate_explanation(text, recommendations())
    assert is_valid is True
    assert issues == []


def test_quoted_title_case_insensitive_is_not_hallucination():
    # A quoted title in different casing is still a real retrieved title.
    text = 'The standout here is "library rain", perfect for a calm evening.'
    is_valid, issues = validate_explanation(text, recommendations())
    assert is_valid is True
    assert issues == []

def test_quoted_title_with_trailing_comma_is_valid():
    text = (
        'The top choice is "Library Rain," because it matches your calm lofi mood.'
    )

    is_valid, issues = validate_explanation(text, recommendations())

    assert is_valid is True
    assert issues == []
