"""
Contradiction and change detection engine.
Compares new events against existing knowledge to detect signals.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from cortex.adapters.llm.classifier import is_weak_key_points
from cortex.domain.constants import SIGNAL_TYPE_BASE_PRIORITY
from cortex.domain.entities import (
    ContradictionResult,
    KnowledgeEvent,
    SearchResult,
)
from cortex.domain.ports import EmbeddingPort, LLMPort, StoragePort


COMPARE_PROMPT = """Compare these two pieces of information and classify their relationship.

NEW information:
Title: {new_title}
Key points: {new_points}

EXISTING information:
Title: {existing_title}
Key points: {existing_points}

Classify as ONE of:
- new_signal: the new info extends beyond existing knowledge
- redundant: the new info repeats existing knowledge
- contradiction: the new info directly conflicts with existing claims
- answer: the new info answers an open question in existing knowledge
- bridge: the new info connects two previously unrelated areas

Return ONLY valid JSON:
{{"signal_type": "...", "topic": "what topic this is about",\
 "summary": "one sentence explanation", "confidence": 0.0-1.0,\
 "rationale": "why this is not just redundant",\
 "evidence_strength": "strong|moderate|weak"}}"""


# Score threshold for candidate filtering (broad search uses 0.3)
_CANDIDATE_MIN_SCORE = 0.5
_CANDIDATE_MAX = 6
_STALE_TIME_SENSITIVE_DAYS = 14


class ContradictionDetector:

    def __init__(
        self,
        storage: StoragePort,
        embedding: EmbeddingPort,
        llm: Optional[LLMPort] = None,
    ):
        self._storage = storage
        self._embedding = embedding
        self._llm = llm

    async def analyze(
        self,
        new_event: KnowledgeEvent,
        workspace_id: str = "default",
    ) -> list[ContradictionResult]:
        """Compare new event against existing knowledge. Returns signal list."""
        if not self._llm:
            return []
        if not new_event.key_points and not new_event.content:
            return []

        # Use event embedding to find similar existing events
        if not new_event.embedding:
            embed_text = (
                f"{new_event.title}\n{new_event.summary}"
                f"\n{new_event.content[:1000]}"
            )
            embedding = await self._embedding.embed(embed_text)
        else:
            embedding = new_event.embedding

        similar = await self._storage.semantic_search(
            embedding,
            workspace_id=workspace_id,
            limit=10,
            min_score=0.3,
        )

        # Two-stage filtering
        candidates = _filter_candidates(similar, new_event)

        results = []
        for sr in candidates:
            result = await self._classify_signal(new_event, sr.event)
            if result and result.signal_type != "redundant":
                results.append(result)

        # Dedup and score
        results = _dedup_signals(results)
        results = _score_signals(results, new_event)

        return results

    async def _classify_signal(
        self,
        new_event: KnowledgeEvent,
        existing_event: KnowledgeEvent,
    ) -> Optional[ContradictionResult]:
        """Use LLM to classify signal type between two events."""
        new_points = _format_key_points(new_event)
        existing_points = _format_key_points(existing_event)

        prompt = COMPARE_PROMPT.format(
            new_title=new_event.title,
            new_points=new_points,
            existing_title=existing_event.title,
            existing_points=existing_points,
        )

        try:
            response = await self._llm.chat(prompt)
            data = _parse_json(response)
            return ContradictionResult(
                new_event_id=new_event.id,
                existing_event_id=existing_event.id,
                signal_type=data.get("signal_type", "new_signal"),
                topic=data.get("topic"),
                summary=data.get("summary"),
                confidence=data.get("confidence", 0.5),
                rationale=data.get("rationale"),
                evidence_strength=data.get("evidence_strength"),
            )
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Candidate filtering (Step 3)
# ---------------------------------------------------------------------------

def _filter_candidates(
    similar: list[SearchResult],
    new_event: KnowledgeEvent,
) -> list[SearchResult]:
    """Two-stage filter: score gate + content gate."""
    now = datetime.now(timezone.utc)
    stale_cutoff = now - timedelta(days=_STALE_TIME_SENSITIVE_DAYS)
    filtered = []

    for sr in similar:
        existing = sr.event
        # Skip self-match
        if existing.id == new_event.id:
            continue
        # Score gate
        if sr.score < _CANDIDATE_MIN_SCORE:
            continue
        # Content gate: must have key_points or content
        if not existing.key_points and not existing.content:
            continue
        # Weak key_points + no summary + very short content
        if (
            is_weak_key_points(existing.key_points)
            and not existing.summary
            and len(existing.content or "") < 100
        ):
            continue
        # Stale time-sensitive events
        if (
            existing.temporality == "time_sensitive"
            and existing.created_at
            and existing.created_at < stale_cutoff
        ):
            continue

        filtered.append(sr)
        if len(filtered) >= _CANDIDATE_MAX:
            break

    return filtered


# ---------------------------------------------------------------------------
# Signal dedup and scoring (Step 4)
# ---------------------------------------------------------------------------

def _dedup_signals(
    results: list[ContradictionResult],
) -> list[ContradictionResult]:
    """Group by (topic, signal_type), keep highest confidence per group."""
    groups: dict[tuple[str, str], ContradictionResult] = {}

    for r in results:
        key = ((r.topic or "").lower().strip(), r.signal_type)
        if key not in groups:
            r.evidence_event_ids = [r.existing_event_id]
            groups[key] = r
        else:
            existing = groups[key]
            if r.existing_event_id not in existing.evidence_event_ids:
                existing.evidence_event_ids.append(r.existing_event_id)
            if r.confidence > existing.confidence:
                r.evidence_event_ids = existing.evidence_event_ids
                groups[key] = r

    return list(groups.values())


def _stance_boost(event: KnowledgeEvent) -> float:
    """User stance amplifies signal priority."""
    stance = event.user_stance
    if stance == "disagree":
        return 0.15
    if stance == "uncertain":
        return 0.05
    return 0.0


def _score_signals(
    results: list[ContradictionResult],
    new_event: KnowledgeEvent,
) -> list[ContradictionResult]:
    """Compute priority_score and sort descending."""
    thesis_boost = 0.1 if new_event.thesis_links else 0.0
    sb = _stance_boost(new_event)
    src_weight = new_event.source_weight or 0.5

    for r in results:
        base = SIGNAL_TYPE_BASE_PRIORITY.get(r.signal_type, 0.4)
        r.priority_score = (
            base * 0.45
            + r.confidence * 0.30
            + src_weight * 0.15
            + thesis_boost
            + sb
        )

    results.sort(key=lambda r: r.priority_score, reverse=True)
    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_key_points(event: KnowledgeEvent) -> str:
    """Format key_points for LLM prompt, falling back to content."""
    if event.key_points:
        return "\n".join(
            f"- [{kp.get('type', 'claim')}] {kp.get('text', '')}"
            for kp in event.key_points
        )
    # Fall back to summary or content
    text = event.summary or event.content[:500]
    return text


def _parse_json(text: str) -> dict:
    """Parse JSON from LLM response."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(
            r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL
        )
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
    return {"signal_type": "new_signal", "confidence": 0.3}
