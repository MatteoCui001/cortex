"""Tests for feedback-based priority adjustment."""
from __future__ import annotations

from cortex.domain.entities import ContradictionResult
from cortex.use_cases.feedback_adjuster import (
    _MIN_VERDICTS,
    _MULTIPLIER_CEIL,
    _MULTIPLIER_FLOOR,
    apply_feedback_multipliers,
    build_feedback_multipliers,
)


def _make_summary(useful=0, not_useful=0, wrong=0, save_for_later=0):
    return {
        ("contradiction", "rates"): {
            "useful": useful,
            "not_useful": not_useful,
            "wrong": wrong,
            "save_for_later": save_for_later,
        }
    }


def _make_signal(topic="rates", priority_score=0.5):
    return ContradictionResult(
        new_event_id="a", existing_event_id="b",
        signal_type="contradiction", topic=topic,
        priority_score=priority_score,
    )


class TestBuildFeedbackMultipliers:

    def test_below_min_verdicts_returns_1(self):
        summary = _make_summary(useful=1, wrong=1)
        mults = build_feedback_multipliers(summary)
        assert mults[("contradiction", "rates")] == 1.0

    def test_at_min_verdicts_all_useful(self):
        summary = _make_summary(useful=_MIN_VERDICTS)
        mults = build_feedback_multipliers(summary)
        assert mults[("contradiction", "rates")] == _MULTIPLIER_CEIL

    def test_all_negative_gives_floor(self):
        summary = _make_summary(wrong=_MIN_VERDICTS)
        mults = build_feedback_multipliers(summary)
        assert mults[("contradiction", "rates")] == _MULTIPLIER_FLOOR

    def test_fifty_fifty_gives_midpoint(self):
        summary = _make_summary(useful=3, wrong=3)
        mults = build_feedback_multipliers(summary)
        assert mults[("contradiction", "rates")] == 1.0

    def test_save_for_later_not_counted(self):
        summary = _make_summary(useful=1, save_for_later=10)
        mults = build_feedback_multipliers(summary)
        # total = useful(1) + negative(0) = 1, below threshold
        assert mults[("contradiction", "rates")] == 1.0

    def test_empty_summary(self):
        mults = build_feedback_multipliers({})
        assert mults == {}


class TestApplyFeedbackMultipliers:

    def test_missing_key_uses_1(self):
        sig = _make_signal(priority_score=0.5)
        apply_feedback_multipliers([sig], {})
        assert sig.priority_score == 0.5

    def test_clamps_to_one_ceil(self):
        sig = _make_signal(priority_score=0.9)
        mults = {("contradiction", "rates"): _MULTIPLIER_CEIL}
        apply_feedback_multipliers([sig], mults)
        assert sig.priority_score <= 1.0

    def test_clamps_to_zero_floor(self):
        sig = _make_signal(priority_score=0.01)
        mults = {("contradiction", "rates"): _MULTIPLIER_FLOOR}
        apply_feedback_multipliers([sig], mults)
        assert sig.priority_score >= 0.0
