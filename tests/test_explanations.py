"""Tests for src/explanations.py (deterministic context + fallback)."""

import copy

from src.explanations import (
    build_fallback_explanation,
    build_recommendation_context,
)


def sample_profile() -> dict:
    """A normalized user profile (validator schema)."""
    return {
        "genre": "lofi",
        "mood": "chill",
        "target_energy": 0.35,
        "likes_acoustic": True,
    }


def song(title, artist, genre, mood, energy, acousticness) -> dict:
    """Build a song dict in the recommender's load_songs format."""
    return {
        "id": "0",
        "title": title,
        "artist": artist,
        "genre": genre,
        "mood": mood,
        "energy": energy,
        "tempo_bpm": 72,
        "valence": 0.6,
        "danceability": 0.58,
        "acousticness": acousticness,
    }


def sample_recommendations() -> list:
    """Two recommendations in the recommender's (song, score, reasons) format."""
    return [
        (
            song("Library Rain", "Paper Lanterns", "lofi", "chill", 0.35, 0.86),
            4.50,
            "+2.0 genre match (lofi); +1.0 mood match (chill); +1.00 energy match; +0.5 acoustic bonus",
        ),
        (
            song("Midnight Coding", "LoRoom", "lofi", "chill", 0.42, 0.71),
            4.43,
            "+2.0 genre match (lofi); +1.0 mood match (chill); +0.93 energy match; +0.5 acoustic bonus",
        ),
    ]


# --- context ---------------------------------------------------------------

def test_context_includes_profile_preferences():
    context = build_recommendation_context(sample_profile(), sample_recommendations())
    assert "Favorite Genre: lofi" in context
    assert "Favorite Mood: chill" in context
    assert "Target Energy: 0.35" in context
    assert "Likes Acoustic: yes" in context


def test_context_includes_titles_and_artists():
    context = build_recommendation_context(sample_profile(), sample_recommendations())
    assert "Library Rain" in context
    assert "Paper Lanterns" in context
    assert "Midnight Coding" in context
    assert "LoRoom" in context


def test_context_includes_scores_and_reasons():
    context = build_recommendation_context(sample_profile(), sample_recommendations())
    assert "4.50" in context
    assert "+2.0 genre match (lofi)" in context
    assert "+0.5 acoustic bonus" in context


def test_context_excludes_song_that_was_not_retrieved():
    context = build_recommendation_context(sample_profile(), sample_recommendations())
    # A song that was never retrieved must not appear in the grounded context.
    assert "Ghost Track" not in context
    assert "Phantom Artist" not in context


# --- fallback --------------------------------------------------------------

def test_fallback_mentions_top_song():
    fallback = build_fallback_explanation(sample_profile(), sample_recommendations())
    assert "Library Rain" in fallback


def test_fallback_uses_grounded_recommendation_facts():
    fallback = build_fallback_explanation(sample_profile(), sample_recommendations())
    # Genre and artist come straight from the retrieved data.
    assert "lofi" in fallback
    assert "Paper Lanterns" in fallback
    # It should be a real, non-empty sentence.
    assert fallback.strip().endswith(".")
    assert len(fallback) > 0


def test_fallback_handles_empty_recommendations():
    fallback = build_fallback_explanation(sample_profile(), [])
    assert isinstance(fallback, str)
    assert fallback.strip() != ""


def test_context_handles_empty_recommendations():
    context = build_recommendation_context(sample_profile(), [])
    assert "Retrieved Songs: (none)" in context
    # Preferences are still present even with no songs.
    assert "Favorite Genre: lofi" in context


# --- purity ----------------------------------------------------------------

def test_functions_do_not_mutate_inputs():
    profile = sample_profile()
    recommendations = sample_recommendations()
    profile_snapshot = copy.deepcopy(profile)
    recommendations_snapshot = copy.deepcopy(recommendations)

    build_recommendation_context(profile, recommendations)
    build_fallback_explanation(profile, recommendations)

    assert profile == profile_snapshot
    assert recommendations == recommendations_snapshot
