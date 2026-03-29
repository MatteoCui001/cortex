"""
Proactive push detection engine.
Produces structured PushNotification objects. Delivery is handled elsewhere.
"""
from __future__ import annotations

from cortex.domain.entities import ContradictionResult, PushNotification
from cortex.domain.ports import StoragePort

# Minimum priority_score for a signal to become a notification
_SIGNAL_NOTIFY_THRESHOLD = 0.5


class PushDetector:

    def __init__(self, storage: StoragePort, workspace_id: str = "default"):
        self._storage = storage
        self._workspace_id = workspace_id

    async def check_all(
        self,
        signals: list[ContradictionResult] | None = None,
    ) -> list[PushNotification]:
        """Run all detection checks and return notifications."""
        notifications: list[PushNotification] = []
        if signals:
            notifications += self.check_signals(signals)
        notifications += await self.check_stale_theses()
        notifications += await self.check_entity_momentum()
        return notifications

    def check_signals(
        self,
        signals: list[ContradictionResult],
    ) -> list[PushNotification]:
        """Convert scored signals into notifications."""
        notifications = []
        for s in signals:
            if s.signal_type not in ("contradiction", "answer", "bridge"):
                continue
            if s.priority_score < _SIGNAL_NOTIFY_THRESHOLD:
                continue
            notif = self.from_contradiction(
                signal_type=s.signal_type,
                topic=s.topic or "unknown",
                summary=s.summary or "",
                event_ids=s.evidence_event_ids or [s.existing_event_id],
                rationale=s.rationale,
                signal_id=s.id,
            )
            notifications.append(notif)
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
        rationale: str | None = None,
        signal_id: str | None = None,
    ) -> PushNotification:
        """Create a notification from a contradiction detection result."""
        type_titles = {
            "contradiction": "Contradiction detected",
            "answer": "Question answered",
            "bridge": "Knowledge bridge found",
        }
        body = summary or f"A {signal_type} signal was detected."
        if rationale:
            body = f"{body} ({rationale})"
        return PushNotification(
            trigger_type=f"{signal_type}_detected",
            title=(
                f"{type_titles.get(signal_type, 'Signal')}: "
                f"{topic or 'unknown'}"
            ),
            body=body,
            related_event_ids=event_ids,
            signal_id=signal_id,
            priority="high" if signal_type == "contradiction" else "medium",
            workspace_id=self._workspace_id,
        )
