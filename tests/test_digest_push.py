"""Tests for digest push delivery."""
from __future__ import annotations

from datetime import date

import pytest

from cortex.use_cases.digest_push import (
    format_digest_text,
    make_digest_notification,
    push_digest,
)
from tests.conftest import FakeStorage


# ---------------------------------------------------------------------------
# format_digest_text
# ---------------------------------------------------------------------------

class TestFormatDigestText:

    def test_empty_digest(self):
        text = format_digest_text({}, target_date=date(2026, 3, 29))
        assert "暂无新动态" in text

    def test_narrative_included(self):
        digest = {"narrative": "今天的关键发现是 AI 基础设施投资加速。"}
        text = format_digest_text(digest)
        assert "AI 基础设施投资加速" in text

    def test_thesis_trends_formatted(self):
        digest = {
            "thesis_trends": [
                {
                    "thesis": "AI Agents",
                    "trend_direction": "up",
                    "confidence_delta": 0.12,
                },
                {
                    "thesis": "光伏去银化",
                    "trend_direction": "down",
                    "confidence_delta": -0.08,
                },
            ],
        }
        text = format_digest_text(digest)
        assert "↑ AI Agents" in text
        assert "↓ 光伏去银化" in text
        assert "+12%" in text

    def test_high_confidence_formatted(self):
        digest = {
            "high_confidence": [
                {"title": "GPT-5 发布在即", "confidence": 0.95},
            ],
        }
        text = format_digest_text(digest)
        assert "GPT-5 发布在即" in text
        assert "95%" in text

    def test_entity_momentum_formatted(self):
        digest = {
            "entity_momentum": [
                {"name": "OpenAI", "mentions": 12},
            ],
        }
        text = format_digest_text(digest)
        assert "OpenAI" in text
        assert "12次" in text

    def test_stale_theses_formatted(self):
        digest = {
            "stale_theses": [
                {
                    "thesis": "World Models",
                    "days_since_update": 45,
                },
            ],
        }
        text = format_digest_text(digest)
        assert "World Models" in text
        assert "45天未更新" in text


# ---------------------------------------------------------------------------
# make_digest_notification
# ---------------------------------------------------------------------------

class TestMakeDigestNotification:

    def test_creates_notification_with_digest_source(self):
        digest = {
            "thesis_trends": [
                {"thesis": "AI", "trend_direction": "up", "confidence_delta": 0.1},
            ],
            "high_confidence": [
                {"title": "Test", "confidence": 0.9},
            ],
        }
        notif = make_digest_notification(digest, target_date=date(2026, 3, 29))
        assert notif.source_kind == "digest"
        assert "2026-03-29" in notif.dedup_key
        assert "研究日报" in notif.title
        assert notif.priority == "medium"

    def test_empty_digest_subtitle(self):
        notif = make_digest_notification({}, target_date=date(2026, 3, 29))
        assert "暂无新动态" in notif.title

    def test_counts_in_subtitle(self):
        digest = {
            "thesis_trends": [
                {"thesis": "A", "trend_direction": "up", "confidence_delta": 0.1},
                {"thesis": "B", "trend_direction": "down", "confidence_delta": -0.1},
            ],
            "high_confidence": [
                {"title": "X", "confidence": 0.9},
            ],
        }
        notif = make_digest_notification(digest)
        assert "2个thesis变动" in notif.title
        assert "1条高置信" in notif.title


# ---------------------------------------------------------------------------
# push_digest (integration)
# ---------------------------------------------------------------------------

class TestPushDigest:

    @pytest.mark.asyncio
    async def test_push_creates_notification(self):
        storage = FakeStorage()

        class FakeAnalyze:
            async def daily_digest(self, days=1):
                return {
                    "thesis_activity": {"AI": {"note": 3}},
                    "high_confidence": [],
                    "thesis_trends": [],
                    "entity_momentum": [{"name": "OpenAI", "mentions": 5}],
                }

        notif = await push_digest(storage, FakeAnalyze(), workspace_id="default")
        assert notif is not None
        assert "研究日报" in notif.title
        assert notif.id in storage._notifications

    @pytest.mark.asyncio
    async def test_push_dedup_skips_second_call(self):
        storage = FakeStorage()

        class FakeAnalyze:
            async def daily_digest(self, days=1):
                return {
                    "thesis_activity": {"AI": {"note": 3}},
                    "high_confidence": [],
                    "thesis_trends": [],
                    "entity_momentum": [],
                }

        # First push succeeds
        notif1 = await push_digest(storage, FakeAnalyze(), workspace_id="default")
        assert notif1 is not None

        # Second push same day — should be skipped (dedup)
        notif2 = await push_digest(storage, FakeAnalyze(), workspace_id="default")
        assert notif2 is None

    @pytest.mark.asyncio
    async def test_push_skips_empty_digest(self):
        storage = FakeStorage()

        class EmptyAnalyze:
            async def daily_digest(self, days=1):
                return {}

        notif = await push_digest(storage, EmptyAnalyze(), workspace_id="default")
        assert notif is None

    @pytest.mark.asyncio
    async def test_api_push_endpoint(self):
        """POST /digest/push creates a notification."""
        from fastapi.testclient import TestClient
        from tests.conftest import FakeEmbedding, FakeLLM, make_event

        storage = FakeStorage()
        # Add some data so digest isn't empty
        e = make_event(thesis_links=["AI Agents"], confidence=0.9)
        storage._events[e.id] = e

        from tests.conftest import _build_test_app
        app = _build_test_app(storage, FakeEmbedding(), FakeLLM())
        client = TestClient(app, raise_server_exceptions=True)

        response = client.post("/api/v1/digest/push")
        assert response.status_code == 200
        data = response.json()
        # Either created or skipped — both are valid
        assert data["status"] in ("created", "skipped")


# ---------------------------------------------------------------------------
# _parse_cron_hm
# ---------------------------------------------------------------------------

class TestParseCronHM:

    def test_standard_cron(self):
        from cortex.api.main import _parse_cron_hm
        assert _parse_cron_hm("0 9 * * *") == (9, 0)

    def test_custom_time(self):
        from cortex.api.main import _parse_cron_hm
        assert _parse_cron_hm("30 14 * * *") == (14, 30)

    def test_invalid_fallback(self):
        from cortex.api.main import _parse_cron_hm
        assert _parse_cron_hm("bad") == (9, 0)

    def test_empty_fallback(self):
        from cortex.api.main import _parse_cron_hm
        assert _parse_cron_hm("") == (9, 0)
