"""Tests for domain constants."""
from cortex.domain.constants import (
    EVENT_TYPES,
    NATURE_TAGS,
    RAW_INPUT_TYPES,
    SOURCE_TYPES,
    SOURCE_WEIGHTS,
    TEMPORALITIES,
    USER_STANCES,
)


def test_source_weights_non_empty():
    assert len(SOURCE_WEIGHTS) > 0


def test_source_weights_expected_keys():
    assert "first_hand" in SOURCE_WEIGHTS
    assert "expert" in SOURCE_WEIGHTS
    assert "curated" in SOURCE_WEIGHTS
    assert "published" in SOURCE_WEIGHTS
    assert "ambient" in SOURCE_WEIGHTS


def test_source_weights_values_in_range():
    for key, val in SOURCE_WEIGHTS.items():
        assert 0.0 <= val <= 1.0, f"{key} weight {val} out of range"


def test_raw_input_types_non_empty():
    assert len(RAW_INPUT_TYPES) > 0


def test_raw_input_types_expected_members():
    assert "text" in RAW_INPUT_TYPES
    assert "link" in RAW_INPUT_TYPES
    assert "audio" in RAW_INPUT_TYPES
    assert "image" in RAW_INPUT_TYPES
    assert "file" in RAW_INPUT_TYPES
    assert "video" in RAW_INPUT_TYPES


def test_source_types_matches_weights():
    assert SOURCE_TYPES == frozenset(SOURCE_WEIGHTS.keys())


def test_nature_tags_non_empty():
    assert len(NATURE_TAGS) > 0


def test_nature_tags_expected_members():
    for tag in ("claim", "fact", "method", "question", "intuition", "synthesis"):
        assert tag in NATURE_TAGS


def test_temporalities_non_empty():
    assert len(TEMPORALITIES) > 0


def test_temporalities_expected_members():
    for t in ("permanent", "trend", "time_sensitive", "prediction"):
        assert t in TEMPORALITIES


def test_user_stances_non_empty():
    assert len(USER_STANCES) > 0


def test_user_stances_expected_members():
    for s in ("agree", "disagree", "uncertain", "skip"):
        assert s in USER_STANCES


def test_event_types_non_empty():
    assert len(EVENT_TYPES) > 0


def test_event_types_expected_members():
    for et in ("article", "meeting", "note", "thesis", "chat"):
        assert et in EVENT_TYPES
