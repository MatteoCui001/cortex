"""
NotificationManager: Orchestrates detection -> dedup -> persist -> webhook delivery.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

from cortex.domain.entities import (
    ContradictionResult,
    Notification,
    NotificationStatus,
    PushNotification,
)
from cortex.domain.ports import StoragePort
from cortex.use_cases.push_detector import PushDetector


class NotificationManager:

    def __init__(
        self,
        storage: StoragePort,
        detector: PushDetector,
        *,
        webhook_cfg: Optional[dict] = None,
        cooldown_hours: int = 24,
        workspace_id: str = "default",
    ):
        self._storage = storage
        self._detector = detector
        self._webhook_cfg = webhook_cfg or {}
        self._cooldown_hours = cooldown_hours
        self._workspace_id = workspace_id

    async def process(
        self,
        signals: list[ContradictionResult] | None = None,
    ) -> list[Notification]:
        """Run detector -> dedup -> persist -> deliver webhook."""
        candidates = await self._detector.check_all(signals=signals)
        created: list[Notification] = []
        for push in candidates:
            dedup_key = self._compute_dedup_key(push)
            if await self._storage.check_dedup(self._workspace_id, dedup_key):
                continue
            notif = self._push_to_notification(push, dedup_key)
            await self._storage.insert_notification(notif)
            if self._should_webhook(notif):
                ok = await self._deliver_webhook(notif)
                new_status = (
                    NotificationStatus.DELIVERED if ok
                    else NotificationStatus.FAILED
                )
                notif.transition(new_status)
                await self._storage.update_notification_status(
                    notif.id,
                    new_status,
                    delivered_at=datetime.now(timezone.utc) if ok else None,
                )
            created.append(notif)
        return created

    async def transition(
        self,
        notification_id: str,
        new_status: NotificationStatus,
    ) -> Notification:
        """Validate + persist status transition."""
        notif = await self._storage.get_notification(
            notification_id, self._workspace_id,
        )
        if not notif:
            raise ValueError(f"Notification {notification_id} not found")
        notif.transition(new_status)  # raises ValueError if invalid
        now = datetime.now(timezone.utc)
        await self._storage.update_notification_status(
            notification_id,
            new_status,
            delivered_at=(
                now if new_status == NotificationStatus.DELIVERED else None
            ),
            acted_at=(
                now
                if new_status
                in (
                    NotificationStatus.READ,
                    NotificationStatus.ACKED,
                    NotificationStatus.DISMISSED,
                )
                else None
            ),
        )
        return notif

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _deliver_webhook(self, notif: Notification) -> bool:
        """HTTP POST with retry. Returns True on 2xx."""
        url = self._webhook_cfg.get("url", "")
        if not url:
            return False
        timeout = self._webhook_cfg.get("timeout_seconds", 5)
        secret = self._webhook_cfg.get("secret", "")
        headers = {"Content-Type": "application/json"}
        payload = {
            "id": notif.id,
            "title": notif.title,
            "body": notif.body,
            "priority": notif.priority,
            "source_kind": notif.source_kind,
        }
        if secret:
            import hashlib, hmac, json
            body_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
            sig = hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
            headers["X-Webhook-Signature"] = f"sha256={sig}"

        import asyncio
        last_exc = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    return 200 <= resp.status_code < 300
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_exc = e
                if attempt < 2:
                    await asyncio.sleep(1 * (2 ** attempt))
            except Exception:
                logger.warning("Webhook delivery failed for notification %s", notif.id, exc_info=True)
                return False
        logger.warning("Webhook delivery failed after retries for %s: %s", notif.id, last_exc)
        return False

    def _should_webhook(self, notif: Notification) -> bool:
        """Check webhook enabled + priority meets min_priority."""
        if not self._webhook_cfg.get("enabled", False):
            return False
        from cortex.domain.constants import PRIORITY_ORDER
        min_priority = self._webhook_cfg.get("min_priority", "medium")
        return PRIORITY_ORDER.get(notif.priority, 1) >= PRIORITY_ORDER.get(
            min_priority, 1
        )

    def _compute_dedup_key(self, push: PushNotification) -> str:
        """From PushNotification trigger_type + related_event_ids."""
        event_part = (
            ":".join(sorted(push.related_event_ids))
            if push.related_event_ids
            else push.title
        )
        return f"{push.trigger_type}:{event_part}"

    def _push_to_notification(
        self,
        push: PushNotification,
        dedup_key: str,
    ) -> Notification:
        """Convert PushNotification -> Notification."""
        return Notification(
            title=push.title,
            body=push.body,
            source_kind=push.trigger_type,
            dedup_key=dedup_key,
            priority=push.priority,
            related_event_ids=push.related_event_ids,
            signal_id=push.signal_id,
            workspace_id=self._workspace_id,
        )
