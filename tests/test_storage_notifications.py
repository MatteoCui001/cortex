"""Tests for notification storage operations (FakeStorage)."""
import pytest

from cortex.domain.entities import Notification, NotificationStatus


@pytest.fixture()
def notif():
    return Notification(
        title="Test Signal",
        body="A contradiction was detected",
        source_kind="signal",
        source_id="sig-1",
    )


# ------------------------------------------------------------------
# insert + get
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_insert_and_get_notification(fake_storage, notif):
    nid = await fake_storage.insert_notification(notif)
    assert nid == notif.id
    fetched = await fake_storage.get_notification(notif.id)
    assert fetched is not None
    assert fetched.title == "Test Signal"


@pytest.mark.asyncio
async def test_get_notification_wrong_workspace(fake_storage, notif):
    await fake_storage.insert_notification(notif)
    fetched = await fake_storage.get_notification(notif.id, workspace_id="other")
    assert fetched is None


@pytest.mark.asyncio
async def test_get_notifications_returns_list(fake_storage, notif):
    await fake_storage.insert_notification(notif)
    results = await fake_storage.get_notifications("default")
    assert len(results) == 1
    assert results[0].id == notif.id


# ------------------------------------------------------------------
# filter by status
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_notifications_filter_by_status(fake_storage):
    n1 = Notification(title="A", body="a", source_kind="signal")
    n2 = Notification(title="B", body="b", source_kind="signal",
                      status=NotificationStatus.DELIVERED)
    await fake_storage.insert_notification(n1)
    await fake_storage.insert_notification(n2)
    pending = await fake_storage.get_notifications("default", status="pending")
    assert len(pending) == 1
    assert pending[0].id == n1.id


# ------------------------------------------------------------------
# update status
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_notification_status(fake_storage, notif):
    await fake_storage.insert_notification(notif)
    ok = await fake_storage.update_notification_status(
        notif.id, NotificationStatus.DELIVERED,
    )
    assert ok is True
    fetched = await fake_storage.get_notification(notif.id)
    assert fetched.status == NotificationStatus.DELIVERED


@pytest.mark.asyncio
async def test_update_notification_status_unknown_id(fake_storage):
    ok = await fake_storage.update_notification_status(
        "nonexistent", NotificationStatus.DELIVERED,
    )
    assert ok is False


# ------------------------------------------------------------------
# dedup
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_check_dedup_active(fake_storage, notif):
    await fake_storage.insert_notification(notif)
    assert await fake_storage.check_dedup("default", notif.dedup_key) is True


@pytest.mark.asyncio
async def test_check_dedup_terminal_not_active(fake_storage, notif):
    notif.status = NotificationStatus.ACKED
    await fake_storage.insert_notification(notif)
    assert await fake_storage.check_dedup("default", notif.dedup_key) is False
