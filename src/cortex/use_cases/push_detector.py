"""
Proactive push detection engine.
Produces structured PushNotification objects. Delivery is handled elsewhere.
"""
from __future__ import annotations

from datetime import datetime

from cortex.domain.entities import PushNotification
from cortex.domain.ports import StoragePort


class PushDetector:

    def __init__(self, storage: StoragePort, workspace_id: str = "default"):
        self._storage = storage
        self._workspace_id = workspace_id

    async def check_all(self) -> list[PushNotification]:
        """Run all detection checks and return notifications."""
        notifications: list[PushNotification] = []
        notifications += await self.check_stale_theses()
        notifications += await self.check_entity_momentum()
        return notifications

    async def check_stale_theses(self, stale_days: int = 30) -> list[PushNotification]:
        """Detect theses that haven't received new evidence."""
        coverage = await self._storage.thesis_coverage(self._workspace_id)
        notifications = []
        for t in coverage:
            if t.days_since_update >= stale_days and t.event_count > 0:
                notifications.append(PushNotification(
                    trigger_type="thesis_stale",
                    title=f"Thesis needs attention: {t.thesis_name}",
                    body=f"No new evidence in {t.days_since_update} days. "
                         f"{t.event_count} total events, avg confidence {t.avg_confidence:.2f}.",
                    priority="medium",
                    workspace_id=self._workspace_id,
                ))
        return notifications

    async def check_entity_momentum(
        self,
        days: int = 7,
        threshold: int = 5,
    ) -> list[PushNotification]:
        """Detect entities with unusual mention frequency."""
        momentum = await self._storage.entity_momentum(
            days=days,
            workspace_id=self._workspace_id,
            limit=20,
        )
        notifications = []
        for ent in momentum:
            if ent["mentions"] >= threshold:
                notifications.append(PushNotification(
                    trigger_type="entity_momentum_spike",
                    title=f"High activity: {ent['name']}",
                    body=f"{ent['name']} ({ent['type']}) mentioned {ent['mentions']} times in {days} days.",
                    priority="low",
                    workspace_id=self._workspace_id,
                ))
        return notifications

    def from_contradiction(
        self,
        signal_type: str,
        topic: str,
        summary: str,
        event_ids: list[str],
    ) -> PushNotification:
        """Create a notification from a contradiction detection result."""
        type_titles = {
            "contradiction": "Contradiction detected",
            "answer": "Question answered",
            "bridge": "Knowledge bridge found",
        }
        return PushNotification(
            trigger_type=f"{signal_type}_detected",
            title=f"{type_titles.get(signal_type, 'Signal')}: {topic or 'unknown'}",
            body=summary or f"A {signal_type} signal was detected.",
            related_event_ids=event_ids,
            priority="high" if signal_type == "contradiction" else "medium",
            workspace_id=self._workspace_id,
        )
