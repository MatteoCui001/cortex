"""
User stance detection — pure domain logic, no adapter dependencies.
"""
from __future__ import annotations

from typing import Optional


# Pattern-based stance detection (fast path, no LLM needed)
_AGREE_PATTERNS = [
    "有道理", "认同", "同意", "对的", "是的", "没错", "赞同",
    "agree", "yes", "right", "makes sense", "correct", "good point",
]
_DISAGREE_PATTERNS = [
    "不对", "扯淡", "不认同", "不同意", "错", "胡说", "瞎说",
    "disagree", "no", "wrong", "bs", "nonsense", "incorrect",
]
_UNCERTAIN_PATTERNS = [
    "存疑", "不确定", "留着看看", "待验证", "有待观察", "再看看",
    "uncertain", "maybe", "perhaps", "not sure", "questionable",
]
_SKIP_PATTERNS = [
    "跳过", "不关注", "无所谓", "略过",
    "skip", "pass", "ignore", "not relevant",
]


def parse_user_stance(annotation: str) -> Optional[str]:
    """Fast pattern-based stance detection. Returns None if ambiguous.

    Uses longest-match-first to avoid substring collisions
    (e.g. "disagree" vs "agree", "not sure" vs "no", "不认同" vs "认同").
    """
    text = annotation.lower().strip()
    if not text:
        return None
    # Build (pattern, stance) pairs sorted longest-first so "not sure"
    # beats "no", "disagree" beats "agree", "不认同" beats "认同", etc.
    _all = (
        [(_p, "agree") for _p in _AGREE_PATTERNS]
        + [(_p, "disagree") for _p in _DISAGREE_PATTERNS]
        + [(_p, "uncertain") for _p in _UNCERTAIN_PATTERNS]
        + [(_p, "skip") for _p in _SKIP_PATTERNS]
    )
    _all.sort(key=lambda x: len(x[0]), reverse=True)
    for pattern, stance in _all:
        if pattern in text:
            return stance
    return None
