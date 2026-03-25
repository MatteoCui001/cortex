"""Tests for signal persistence and feedback in FakeStorage."""
from __future__ import annotations

import pytest

from cortex.domain.entities import ContradictionResult, SignalFeedback
from tests.conftest import FakeStorage


@pytest.fixture
def storage():
    return FakeStorage()


def _make_signal(**kwargs) -> ContradictionResult:
    defaults = dict(
        new_event_id="evt-new",
        existing_event_id="evt-old",
        signal_type="contradiction",
        topic="interest rates",
        summary="Conflicting data",
        confidence=0.8,
        priority_score=0.75,
        workspace_id="default",
        thesis_links=["macro-rates"],
    )
    defaults.update(kwargs)
    return ContradictionResult(**defaults)


class TestUpsertSignal:

    @pytest.mark.asyncio
    async def test_upsert_returns_id(self, storage):
        sig = _make_signal()
        sid = await storage.upsert_signal(sig)
        assert sid == sig.id

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self, storage):
        sig = _make_signal(priority_score=0.5)
        await storage.upsert_signal(sig)
        sig.priority_score = 0.9
        await storage.upsert_signal(sig)
        signals = await storage.get_signals("default")
        assert len(signals) == 1
        assert signals[0].priority_score == 0.9


class TestGetSignals:

    @pytest.mark.asyncio
    async def test_returns_empty_by_default(self, storage):
        signals = await storage.get_signals("default")
        assert signals == []

    @pytest.mark.asyncio
    async def test_filtered_by_event_id(self, storage):
        sig1 = _make_signal(new_event_id="evt-1")
        sig2 = _make_signal(new_event_id="evt-2")
        await storage.upsert_signal(sig1)
        await storage.upsert_signal(sig2)
        results = await storage.get_signals("default", event_id="evt-1")
        assert len(results) == 1
        assert results[0].new_event_id == "evt-1"


class TestSignalFeedback:

    @pytest.mark.asyncio
    async def test_create_feedback_returns_id(self, storage):
        sig = _make_signal()
        await storage.upsert_signal(sig)
        fb = SignalFeedback(signal_id=sig.id, verdict="useful")
        fid = await storage.create_signal_feedback(fb)
        assert fid == fb.id

    @pytest.mark.asyncio
    async def test_feedback_summary_counts(self, storage):
        sig = _make_signal()
        await storage.upsert_signal(sig)
        for verdict in ["useful", "useful", "wrong"]:
            fb = SignalFeedback(signal_id=sig.id, verdict=verdict)
            await storage.create_signal_feedback(fb)
        summary = await storage.get_feedback_summary("default")
        key = ("contradiction", "interest rates")
        assert summary[key]["useful"] == 2
        assert summary[key]["wrong"] == 1

    @pytest.mark.asyncio
    async def test_feedback_summary_empty(self, storage):
        summary = await storage.get_feedback_summary("default")
        assert summary == {}

    @pytest.mark.asyncio
    async def test_save_for_later_tracked_separately(self, storage):
        sig = _make_signal()
        await storage.upsert_signal(sig)
        fb = SignalFeedback(signal_id=sig.id, verdict="save_for_later")
        await storage.create_signal_feedback(fb)
        summary = await storage.get_feedback_summary("default")
        key = ("contradiction", "interest rates")
        assert summary[key]["save_for_later"] == 1
        assert summary[key]["useful"] == 0


class TestThesisFeedbackStats:

    @pytest.mark.asyncio
    async def test_groups_by_thesis(self, storage):
        sig = _make_signal(thesis_links=["macro-rates"])
        await storage.upsert_signal(sig)
        fb = SignalFeedback(signal_id=sig.id, verdict="useful")
        await storage.create_signal_feedback(fb)
        stats = await storage.get_thesis_feedback_stats("default")
        assert len(stats) == 1
        assert stats[0]["thesis_link"] == "macro-rates"
        assert stats[0]["useful"] == 1

    @pytest.mark.asyncio
    async def test_empty_when_no_thesis_links(self, storage):
        sig = _make_signal(thesis_links=[])
        await storage.upsert_signal(sig)
        fb = SignalFeedback(signal_id=sig.id, verdict="useful")
        await storage.create_signal_feedback(fb)
        stats = await storage.get_thesis_feedback_stats("default")
        assert stats == []
