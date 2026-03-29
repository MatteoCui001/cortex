"""
Dynamic value calculation MVP.

Core formula from product design doc:
  信息 = 来源 × 性质 × 时效   (inherent, set at ingest)
  价值 = f(信息, 用户知识状态)  (dynamic, per-signal)

This module implements the value layer as a rule-based scorer
over ContradictionResult signals. It turns implicit signal_type
semantics into an explicit value_score that drives:
  - notification priority ordering
  - inbox triage ranking
  - daily digest "what's most worth your attention"
"""
from __future__ import annotations

from cortex.domain.constants import SOURCE_WEIGHTS
from cortex.domain.entities import ContradictionResult, KnowledgeEvent

# Base value by signal type — what this signal means for the user's knowledge state
_SIGNAL_VALUE: dict[str, float] = {
    "contradiction": 1.0,   # Conflicts with existing belief — highest value
    "answer": 0.85,         # Resolves an open question
    "bridge": 0.75,         # Connects previously unrelated areas
    "new_signal": 0.50,     # Extends beyond existing knowledge
    "redundant": 0.05,      # Repeats what's already known
}

# User stance amplifies value (disagreement makes contradictions more salient)
_STANCE_MULTIPLIER: dict[str, float] = {
    "disagree": 1.3,
    "uncertain": 1.1,
    "agree": 1.0,
    "skip": 0.9,
}


def compute_value_score(
    signal: ContradictionResult,
    new_event: KnowledgeEvent,
) -> float:
    """
    Compute a value score in [0.0, 1.0] for a signal.

    Factors:
      - signal_type base value (what kind of knowledge update)
      - source_weight as multiplier (信息不平等: first-hand > ambient)
      - user_stance amplification
      - confidence from LLM classification
      - thesis relevance boost
    """
    base = _SIGNAL_VALUE.get(signal.signal_type, 0.3)

    # Source credibility as a multiplier, not an additive term
    src_weight = new_event.source_weight or SOURCE_WEIGHTS.get("published", 0.5)

    # User stance
    stance = new_event.user_stance or "agree"
    stance_mult = _STANCE_MULTIPLIER.get(stance, 1.0)

    # Thesis relevance
    thesis_boost = 1.1 if new_event.thesis_links else 1.0

    # Confidence from LLM classification
    conf = signal.confidence

    # Formula: base value × source credibility × stance × thesis × confidence weight
    raw = base * src_weight * stance_mult * thesis_boost * (0.5 + 0.5 * conf)

    return min(1.0, max(0.0, round(raw, 4)))


def score_signals(
    signals: list[ContradictionResult],
    new_event: KnowledgeEvent,
) -> list[ContradictionResult]:
    """Score and sort signals by value. Mutates in place."""
    for s in signals:
        s.priority_score = compute_value_score(s, new_event)
    signals.sort(key=lambda s: s.priority_score, reverse=True)
    return signals
