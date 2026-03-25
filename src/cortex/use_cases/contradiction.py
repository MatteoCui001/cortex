"""
Contradiction and change detection engine.
Compares new events against existing knowledge to detect signals.
"""
from __future__ import annotations

import json
from typing import Optional

from cortex.domain.entities import ContradictionResult, KnowledgeEvent
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
{{"signal_type": "...", "topic": "what topic this is about", "summary": "one sentence explanation", "confidence": 0.0-1.0}}"""


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
            embed_text = f"{new_event.title}\n{new_event.summary}\n{new_event.content[:1000]}"
            embedding = await self._embedding.embed(embed_text)
        else:
            embedding = new_event.embedding

        similar = await self._storage.semantic_search(
            embedding,
            workspace_id=workspace_id,
            limit=10,
            min_score=0.3,
        )

        results = []
        for sr in similar:
            existing = sr.event
            if existing.id == new_event.id:
                continue

            # Only compare if existing event has key_points or content
            if not existing.key_points and not existing.content:
                continue

            result = await self._classify_signal(new_event, existing)
            if result and result.signal_type != "redundant":
                results.append(result)

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
            )
        except Exception:
            return None


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
    import re
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
    return {"signal_type": "new_signal", "confidence": 0.3}
