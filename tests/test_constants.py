"""Tests for domain constants."""
from cortex.domain.constants import (
    EVENT_TYPES,
    KEY_POINT_TYPES,
    NATURE_TAGS,
    NOTIFICATION_CHANNELS,
    NOTIFICATION_STATUSES,
    PRIORITY_ORDER,
    RAW_INPUT_TYPES,
    SIGNAL_FEEDBACK_VERDICTS,
    SIGNAL_TYPE_BASE_PRIORITY,
    SIGNAL_TYPES,
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


def test_key_point_types_expected_members():
    for kpt in ("data", "claim", "prediction", "question"):
        assert kpt in KEY_POINT_TYPES


def test_signal_types_expected_members():
    for st in ("new_signal", "redundant", "contradiction", "answer", "bridge"):
        assert st in SIGNAL_TYPES


def test_signal_type_base_priority_keys_match_signal_types():
    assert set(SIGNAL_TYPE_BASE_PRIORITY.keys()) == SIGNAL_TYPES


def test_signal_type_base_priority_values_in_range():
    for key, val in SIGNAL_TYPE_BASE_PRIORITY.items():
        assert 0.0 <= val <= 1.0, f"{key} priority {val} out of range"


def test_signal_type_priority_ordering():
    assert SIGNAL_TYPE_BASE_PRIORITY["contradiction"] > SIGNAL_TYPE_BASE_PRIORITY["answer"]
    assert SIGNAL_TYPE_BASE_PRIORITY["answer"] > SIGNAL_TYPE_BASE_PRIORITY["bridge"]
    assert SIGNAL_TYPE_BASE_PRIORITY["bridge"] > SIGNAL_TYPE_BASE_PRIORITY["new_signal"]
    assert SIGNAL_TYPE_BASE_PRIORITY["new_signal"] > SIGNAL_TYPE_BASE_PRIORITY["redundant"]


def test_signal_feedback_verdicts_expected_members():
    for v in ("useful", "not_useful", "wrong", "save_for_later"):
        assert v in SIGNAL_FEEDBACK_VERDICTS


# ---------------------------------------------------------------------------
# Phase 4: Notification constants
# ---------------------------------------------------------------------------

def test_notification_statuses_expected_members():
    for s in ("pending", "delivered", "read", "acked", "dismissed", "failed"):
        assert s in NOTIFICATION_STATUSES


def test_notification_channels_expected_members():
    for c in ("inbox", "webhook"):
        assert c in NOTIFICATION_CHANNELS


def test_priority_order_low_lt_medium_lt_high():
    assert PRIORITY_ORDER["low"] < PRIORITY_ORDER["medium"] < PRIORITY_ORDER["high"]
