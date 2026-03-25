"""
Analysis use case: thesis coverage, stale judgments, stats, daily digest.
"""

from __future__ import annotations

from collections import defaultdict

from cortex.domain.entities import KnowledgeEvent, ThesisCoverage
from cortex.domain.ports import StoragePort


class AnalyzeUseCase:
    def __init__(
        self,
        storage: StoragePort,
        workspace_id: str = "default",
    ):
        self._storage = storage
        self._workspace_id = workspace_id

    async def thesis_coverage(self) -> list[ThesisCoverage]:
        """Get thesis coverage report across all events."""
        return await self._storage.thesis_coverage(self._workspace_id)

    async def stale_events(self, days: int = 30) -> list[KnowledgeEvent]:
        """Find thesis/note events not updated in N days."""
        return await self._storage.stale_events(days, self._workspace_id)

    async def stats(self) -> dict:
        """Get workspace statistics."""
        return await self._storage.stats(self._workspace_id)

    async def entity_graph(self, object_id: str) -> list[dict]:
        """Get all relations for an entity or event."""
        return await self._storage.get_relations_for(object_id, self._workspace_id)

    async def thesis_evidence(self, thesis_name: str) -> list[KnowledgeEvent]:
        """Get all events linked to a specific thesis."""
        return await self._storage.get_by_thesis(thesis_name, self._workspace_id)

    async def daily_digest(self, days: int = 1) -> dict:
        """Generate a structured daily research digest."""
        result = {}

        # 1. Recent events by thesis
        thesis_rows = await self._storage.recent_events_by_thesis(days, self._workspace_id)
        thesis_activity: dict[str, dict[str, int]] = defaultdict(dict)
        for row in thesis_rows:
            thesis_activity[row["thesis"]][row["type"]] = row["cnt"]
        result["thesis_activity"] = dict(thesis_activity)

        # 2. High confidence recent insights
        result["high_confidence"] = await self._storage.high_confidence_recent(
            days=days * 7,
            min_confidence=0.8,
            workspace_id=self._workspace_id,
            limit=10,
        )

        # 3. Stale theses (30+ days without update)
        all_coverage = await self._storage.thesis_coverage(self._workspace_id)
        result["stale_theses"] = [t for t in all_coverage if t.days_since_update >= 30]

        # 4. Entity momentum (most mentioned this week)
        result["entity_momentum"] = await self._storage.entity_momentum(
            days=7,
            workspace_id=self._workspace_id,
            limit=10,
        )

        return result
