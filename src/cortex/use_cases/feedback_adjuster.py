"""
Rule-based priority adjustment using historical signal feedback.
"""
from __future__ import annotations

# Minimum total verdicts (useful + not_useful + wrong) before applying adjustment
_MIN_VERDICTS = 3
_MULTIPLIER_FLOOR = 0.6
_MULTIPLIER_CEIL = 1.4


def build_feedback_multipliers(
    summary: dict[tuple[str, str], dict],
) -> dict[tuple[str, str], float]:
    """
    Convert raw feedback summary into priority multipliers.

    Args:
        summary: {(signal_type, topic_normalized): {useful, not_useful, wrong, save_for_later}}
    Returns:
        {(signal_type, topic_normalized): float multiplier in [0.6, 1.4]}
    """
    multipliers = {}
    for key, counts in summary.items():
        useful = counts.get("useful", 0)
        negative = counts.get("not_useful", 0) + counts.get("wrong", 0)
        total = useful + negative
        if total < _MIN_VERDICTS:
            multipliers[key] = 1.0
        else:
            ratio = useful / total  # 0.0 to 1.0
            # Map: ratio=0 -> floor, ratio=1 -> ceil, ratio=0.5 -> 1.0
            raw = _MULTIPLIER_FLOOR + ratio * (_MULTIPLIER_CEIL - _MULTIPLIER_FLOOR)
            multipliers[key] = round(raw, 4)
    return multipliers


def apply_feedback_multipliers(
    results: list,
    multipliers: dict[tuple[str, str], float],
) -> list:
    """Apply multipliers to priority_score in-place. Returns same list."""
    for r in results:
        key = (r.signal_type, (r.topic or "").lower().strip())
        mult = multipliers.get(key, 1.0)
        r.priority_score = round(min(1.0, max(0.0, r.priority_score * mult)), 4)
    return results
