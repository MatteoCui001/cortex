"""Tests for NotificationManager use case."""
import pytest

from cortex.domain.entities import (
    ContradictionResult,
    Notification,
    NotificationStatus,
)
from cortex.use_cases.notification_manager import NotificationManager
from cortex.use_cases.push_detector import PushDetector


@pytest.fixture()
def manager(fake_storage):
    detector = PushDetector(fake_storage, workspace_id="default")
    return NotificationManager(fake_storage, detector, workspace_id="default")


@pytest.fixture()
def webhook_manager(fake_storage):
    detector = PushDetector(fake_storage, workspace_id="default")
    cfg = {"enabled": True, "url": "http://localhost:9999/hook", "min_priority": "medium"}
    return NotificationManager(fake_storage, detector, webhook_cfg=cfg, workspace_id="default")


def _make_signal(priority=0.8, signal_type="contradiction", topic="AI"):
    return ContradictionResult(
        new_event_id="ev-new",
        existing_event_id="ev-old",
        signal_type=signal_type,
        topic=topic,
        summary="Test summary",
        priority_score=priority,
        evidence_event_ids=["ev-old"],
    )


# ------------------------------------------------------------------
# process: basic
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_creates_notification(fake_storage, manager):
    signals = [_make_signal()]
    result = await manager.process(signals=signals)
    assert len(result) == 1
    assert result[0].title.startswith("Contradiction detected")
    # Should be persisted
    stored = await fake_storage.get_notifications("default")
    assert len(stored) == 1


@pytest.mark.asyncio
async def test_process_skips_on_dedup(fake_storage, manager):
    signals = [_make_signal()]
    first = await manager.process(signals=signals)
    assert len(first) == 1
    second = await manager.process(signals=signals)
    assert len(second) == 0


@pytest.mark.asyncio
async def test_process_skips_low_priority_signals(fake_storage, manager):
    signals = [_make_signal(priority=0.1)]
    result = await manager.process(signals=signals)
    assert len(result) == 0


@pytest.mark.asyncio
async def test_process_skips_redundant_signal_type(fake_storage, manager):
    signals = [_make_signal(signal_type="redundant", priority=0.9)]
    result = await manager.process(signals=signals)
    assert len(result) == 0


# ------------------------------------------------------------------
# process: webhook
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_webhook_marks_failed_on_error(fake_storage, webhook_manager):
    """Webhook URL is unreachable -> notification marked FAILED."""
    signals = [_make_signal()]
    result = await webhook_manager.process(signals=signals)
    assert len(result) == 1
    assert result[0].status == NotificationStatus.FAILED


@pytest.mark.asyncio
async def test_process_no_webhook_when_disabled(fake_storage, manager):
    """No webhook config -> notification stays PENDING."""
    signals = [_make_signal()]
    result = await manager.process(signals=signals)
    assert len(result) == 1
    assert result[0].status == NotificationStatus.PENDING


@pytest.mark.asyncio
async def test_webhook_skips_low_priority(fake_storage):
    """Webhook min_priority=high skips medium priority."""
    detector = PushDetector(fake_storage, workspace_id="default")
    cfg = {"enabled": True, "url": "http://localhost:9999/hook", "min_priority": "high"}
    mgr = NotificationManager(fake_storage, detector, webhook_cfg=cfg, workspace_id="default")
    # bridge signal -> medium priority
    signals = [_make_signal(signal_type="bridge", priority=0.8)]
    result = await mgr.process(signals=signals)
    assert len(result) == 1
    assert result[0].status == NotificationStatus.PENDING  # webhook skipped


# ------------------------------------------------------------------
# transition
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transition_read_from_delivered(fake_storage, manager):
    notif = Notification(title="T", body="B", source_kind="signal",
                         status=NotificationStatus.DELIVERED)
    await fake_storage.insert_notification(notif)
    result = await manager.transition(notif.id, NotificationStatus.READ)
    assert result.status == NotificationStatus.READ


@pytest.mark.asyncio
async def test_transition_invalid_raises(fake_storage, manager):
    notif = Notification(title="T", body="B", source_kind="signal",
                         status=NotificationStatus.ACKED)
    await fake_storage.insert_notification(notif)
    with pytest.raises(ValueError, match="Cannot transition"):
        await manager.transition(notif.id, NotificationStatus.PENDING)


@pytest.mark.asyncio
async def test_transition_unknown_id_raises(manager):
    with pytest.raises(ValueError, match="not found"):
        await manager.transition("nonexistent", NotificationStatus.READ)
