"""
Digest push delivery.

Formats the daily digest into a notification that the existing iLink
dispatch loop (or webhook) picks up and delivers to WeChat.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Optional

from cortex.domain.entities import Notification, NotificationStatus

logger = logging.getLogger(__name__)


def format_digest_text(digest: dict, target_date: Optional[date] = None) -> str:
    """Convert a digest dict into concise WeChat-friendly plain text.

    The result is designed for the iLink dispatch format:
    [!!!] title
    body

    We return just the body part; the caller wraps it into a Notification.
    """
    today = target_date or date.today()
    lines: list[str] = []

    # Narrative summary (if LLM produced one)
    if digest.get("narrative"):
        lines.append(digest["narrative"].strip())
        lines.append("")

    # Thesis trends
    trends = digest.get("thesis_trends", [])
    if trends:
        lines.append("-- Thesis 动向 --")
        for t in trends:
            name = t.thesis_name if hasattr(t, "thesis_name") else t.get("thesis", "")
            direction = t.trend_direction if hasattr(t, "trend_direction") else t.get("trend_direction", "")
            delta = t.confidence_delta if hasattr(t, "confidence_delta") else t.get("confidence_delta")
            arrow = "↑" if direction == "up" else "↓"
            delta_str = ""
            if delta is not None:
                delta_str = f" ({delta:+.0%})" if isinstance(delta, float) else f" ({delta})"
            lines.append(f"  {arrow} {name}{delta_str}")
        lines.append("")

    # High confidence insights
    hc = digest.get("high_confidence", [])
    if hc:
        lines.append("-- 高置信洞察 --")
        for item in hc[:5]:
            title = item.title if hasattr(item, "title") else item.get("title", "")
            conf = item.confidence if hasattr(item, "confidence") else item.get("confidence", 0)
            lines.append(f"  {title} ({conf:.0%})")
        lines.append("")

    # Entity momentum
    momentum = digest.get("entity_momentum", [])
    if momentum:
        lines.append("-- 热门实体 --")
        for ent in momentum[:5]:
            name = ent.get("name", "") if isinstance(ent, dict) else getattr(ent, "name", "")
            mentions = ent.get("mentions", 0) if isinstance(ent, dict) else getattr(ent, "mentions", 0)
            lines.append(f"  {name} ({mentions}次)")
        lines.append("")

    # Stale theses
    stale = digest.get("stale_theses", [])
    if stale:
        lines.append("-- 停滞 Thesis --")
        for t in stale:
            name = t.thesis_name if hasattr(t, "thesis_name") else t.get("thesis", "")
            days = t.days_since_update if hasattr(t, "days_since_update") else t.get("days_since_update", 0)
            lines.append(f"  {name} ({days}天未更新)")
        lines.append("")

    # If nothing at all, say so
    if not lines:
        lines.append(f"{today.isoformat()} 暂无新动态")

    return "\n".join(lines).strip()


def make_digest_notification(
    digest: dict,
    workspace_id: str = "default",
    target_date: Optional[date] = None,
) -> Notification:
    """Create a Notification from digest data, ready for insert.

    The notification goes into the standard pipeline:
    - iLink dispatchLoop picks it up as a pending notification
    - Webhook delivery fires if enabled
    - Console Inbox shows it
    """
    today = target_date or date.today()
    body = format_digest_text(digest, target_date=today)

    # Count items for title summary
    n_trends = len(digest.get("thesis_trends", []))
    n_hc = len(digest.get("high_confidence", []))
    parts = []
    if n_trends:
        parts.append(f"{n_trends}个thesis变动")
    if n_hc:
        parts.append(f"{n_hc}条高置信")
    subtitle = "、".join(parts) if parts else "暂无新动态"

    return Notification(
        title=f"研究日报 {today.isoformat()} | {subtitle}",
        body=body,
        source_kind="digest",
        source_id=f"digest:{today.isoformat()}",
        dedup_key=f"digest:{today.isoformat()}",
        workspace_id=workspace_id,
        priority="medium",
    )


async def push_digest(
    storage,
    analyze,
    workspace_id: str = "default",
    days: int = 1,
) -> Optional[Notification]:
    """Generate today's digest and push it as a notification.

    Returns the created Notification, or None if digest was empty or
    a digest for today was already sent (dedup).
    """
    # Check dedup — don't send twice for same day
    today = date.today()
    dedup_key = f"digest:{today.isoformat()}"
    already_sent = await storage.check_dedup(workspace_id, dedup_key)
    if already_sent:
        logger.info("Digest for %s already sent, skipping", today)
        return None

    # Generate digest
    digest = await analyze.daily_digest(days)

    # Skip if truly empty (no thesis activity, no high confidence, no trends)
    if (
        not digest.get("thesis_activity")
        and not digest.get("high_confidence")
        and not digest.get("thesis_trends")
        and not digest.get("entity_momentum")
    ):
        logger.info("Digest for %s is empty, skipping push", today)
        return None

    # Create and insert notification
    notif = make_digest_notification(digest, workspace_id, target_date=today)
    notif_id = await storage.insert_notification(notif)
    logger.info("Digest notification created: %s", notif_id)

    return notif
