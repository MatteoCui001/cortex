"""
Analysis use case: thesis coverage, stale judgments, stats, daily digest.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Optional

from cortex.domain.entities import KnowledgeEvent, ThesisCoverage
from cortex.domain.ports import LLMPort, StoragePort

logger = logging.getLogger(__name__)


class AnalyzeUseCase:

    def __init__(
        self,
        storage: StoragePort,
        workspace_id: str = "default",
        llm: Optional[LLMPort] = None,
    ):
        self._storage = storage
        self._workspace_id = workspace_id
        self._llm = llm

    async def thesis_coverage(self, trend_window_days: int = 14) -> list[ThesisCoverage]:
        """Get thesis coverage with confidence trend."""
        coverage = await self._storage.thesis_coverage(self._workspace_id)
        trends = await self._storage.thesis_trend(
            self._workspace_id, window_days=trend_window_days,
        )

        for tc in coverage:
            t = trends.get(tc.thesis_name)
            if not t:
                tc.trend_direction = "insufficient_data"
                continue

            tc.recent_avg_confidence = t["recent_avg"]
            tc.previous_avg_confidence = t["previous_avg"]
            tc.recent_event_count = t["recent_count"]

            if t["recent_avg"] is not None and t["previous_avg"] is not None:
                # Need minimum samples in both windows to judge trend
                if t["recent_count"] < 1 or t["previous_count"] < 1:
                    tc.trend_direction = "insufficient_data"
                    tc.confidence_delta = None
                else:
                    delta = t["recent_avg"] - t["previous_avg"]
                    tc.confidence_delta = round(delta, 4)
                    if delta > 0.05:
                        tc.trend_direction = "up"
                    elif delta < -0.05:
                        tc.trend_direction = "down"
                    else:
                        tc.trend_direction = "flat"
            else:
                tc.trend_direction = "insufficient_data"

        return coverage

    async def stale_events(self, days: int = 30) -> list[KnowledgeEvent]:
        """Find thesis/note events not updated in N days."""
        return await self._storage.stale_events(days, self._workspace_id)

    async def stats(self) -> dict:
        """Get workspace statistics."""
        return await self._storage.stats(self._workspace_id)

    async def entity_graph(self, object_id: str) -> list[dict]:
        """Get all relations for an entity or event."""
        return await self._storage.get_relations_for(
            object_id, self._workspace_id
        )

    async def thesis_evidence(self, thesis_name: str) -> list[KnowledgeEvent]:
        """Get all events linked to a specific thesis."""
        return await self._storage.get_by_thesis(
            thesis_name, self._workspace_id
        )

    async def daily_digest(self, days: int = 1) -> dict:
        """Generate a structured daily research digest with optional LLM narrative."""
        result = {}

        # 1. Recent events by thesis
        thesis_rows = await self._storage.recent_events_by_thesis(
            days, self._workspace_id
        )
        thesis_activity: dict[str, dict[str, int]] = defaultdict(dict)
        for row in thesis_rows:
            thesis_activity[row["thesis"]][row["type"]] = row["cnt"]
        result["thesis_activity"] = dict(thesis_activity)

        # 2. High confidence recent insights (use the requested day range)
        result["high_confidence"] = await self._storage.high_confidence_recent(
            days=max(days, 1), min_confidence=0.8,
            workspace_id=self._workspace_id, limit=10,
        )

        # 3. Thesis trends + stale theses
        all_coverage = await self.thesis_coverage(trend_window_days=14)
        result["stale_theses"] = [
            t for t in all_coverage if t.days_since_update >= 30
        ]
        result["thesis_trends"] = [
            t for t in all_coverage
            if t.trend_direction in ("up", "down", "flat")
        ]

        # 4. Entity momentum (match the requested day range)
        result["entity_momentum"] = await self._storage.entity_momentum(
            days=max(days, 1), workspace_id=self._workspace_id, limit=10,
        )

        # 5. LLM narrative summary
        if self._llm:
            try:
                result["narrative"] = await self._generate_narrative(result, days)
            except Exception:
                logger.warning("Digest narrative generation failed", exc_info=True)

        return result

    async def _generate_narrative(self, digest: dict, days: int) -> str:
        """Generate a natural language summary of the digest."""
        # Build a concise context for the LLM
        sections = []
        if digest.get("thesis_activity"):
            lines = []
            for thesis, types in digest["thesis_activity"].items():
                total = sum(types.values())
                lines.append(f"  - {thesis}: {total} new events ({types})")
            sections.append("Thesis activity:\n" + "\n".join(lines))

        if digest.get("high_confidence"):
            items = digest["high_confidence"][:5]
            lines = [f"  - {e.title} (confidence={e.confidence:.2f})" for e in items]
            sections.append("High confidence insights:\n" + "\n".join(lines))

        if digest.get("thesis_trends"):
            lines = []
            for t in digest["thesis_trends"]:
                arrow = "↑" if t.trend_direction == "up" else "↓"
                delta = f"{t.confidence_delta:+.2f}" if t.confidence_delta is not None else "?"
                lines.append(f"  - {t.thesis_name} {arrow} (delta={delta}, recent_events={t.recent_event_count})")
            sections.append("Thesis confidence trends:\n" + "\n".join(lines))

        if digest.get("stale_theses"):
            lines = [f"  - {t.thesis_name} ({t.days_since_update}d stale)" for t in digest["stale_theses"]]
            sections.append("Stale theses:\n" + "\n".join(lines))

        if digest.get("entity_momentum"):
            lines = [f"  - {e['name']} ({e['mentions']} mentions)" for e in digest["entity_momentum"][:5]]
            sections.append("Hot entities:\n" + "\n".join(lines))

        if not sections:
            return "No notable activity in this period."

        prompt = (
            f"You are a research intelligence briefing assistant. "
            f"Summarize the following {days}-day research digest in 3-5 sentences, "
            f"in Chinese. Focus on what deserves attention and why. "
            f"Be direct and specific — no filler.\n\n"
            + "\n\n".join(sections)
        )
        return await self._llm.chat(prompt)