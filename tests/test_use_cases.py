"""
Integration tests for Cortex use cases.

Tests cover:
- IngestLinkUseCase (4 tests)
- IngestFileUseCase (4 tests)
- ContradictionDetector (3 tests)
- PushDetector (4 tests)
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from cortex.domain.entities import (
    ContradictionResult,
    EventType,
    KnowledgeEvent,
    PushNotification,
    SearchResult,
    ThesisCoverage,
)
from cortex.use_cases.contradiction import ContradictionDetector
from cortex.use_cases.ingest_file import IngestFileUseCase
from cortex.use_cases.ingest_link import IngestLinkUseCase
from cortex.use_cases.push_detector import PushDetector
from tests.conftest import FakeEmbedding, FakeLLM, FakeStorage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(**kwargs) -> KnowledgeEvent:
    defaults = dict(
        id=str(uuid.uuid4()),
        workspace_id="default",
        type=EventType.NOTE,
        title="Some Title",
        content="Some content text",
        summary="Some summary",
        tags=[],
        thesis_links=[],
        confidence=0.7,
        source="api",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return KnowledgeEvent(**defaults)


# ---------------------------------------------------------------------------
# IngestLinkUseCase tests
# ---------------------------------------------------------------------------

class TestIngestLinkUseCase:

    def _make_use_case(self, storage=None, embedding=None, llm=None):
        return IngestLinkUseCase(
            storage=storage or FakeStorage(),
            embedding=embedding or FakeEmbedding(),
            llm=llm or FakeLLM(),
            workspace_id="default",
        )

    @pytest.mark.asyncio
    async def test_successful_html_ingestion(self, monkeypatch):
        """Fetching a URL with title and body text creates a KnowledgeEvent."""
        html = (
            "<html><head><title>My Test Article</title></head>"
            "<body><p>This is a detailed article about testing Cortex ingestion.</p></body></html>"
        )

        fake_response = MagicMock()
        fake_response.raise_for_status = MagicMock()
        fake_response.text = html

        async def fake_get(self_client, url, **kwargs):
            return fake_response

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

        use_case = self._make_use_case()
        url = "https://example.com/article"
        event = await use_case.import_link(url)

        assert event is not None
        assert event.source == "web"
        assert event.raw_input_type == "link"
        assert url in event.raw_input_ref
        # Title should be extracted from the HTML <title> tag (or slug)
        assert event.title  # non-empty title

    @pytest.mark.asyncio
    async def test_empty_content_returns_none(self, monkeypatch):
        """HTML that yields no readable text causes import_link to return None."""
        # HTML with only empty structural tags, no visible text
        html = "<html><head></head><body><div></div><span></span></body></html>"

        fake_response = MagicMock()
        fake_response.raise_for_status = MagicMock()
        fake_response.text = html

        async def fake_get(self_client, url, **kwargs):
            return fake_response

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

        use_case = self._make_use_case()
        result = await use_case.import_link("https://example.com/empty")

        assert result is None

    @pytest.mark.asyncio
    async def test_http_error_raises(self, monkeypatch):
        """An HTTP error from the remote server propagates out of import_link."""
        request = httpx.Request("GET", "https://example.com/notfound")
        response = httpx.Response(404, request=request)

        async def fake_get(self_client, url, **kwargs):
            raise httpx.HTTPStatusError(
                "404 Not Found", request=request, response=response
            )

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

        use_case = self._make_use_case()
        with pytest.raises(httpx.HTTPStatusError):
            await use_case.import_link("https://example.com/notfound")

    @pytest.mark.asyncio
    async def test_source_path_dedup_second_call_still_works(self, monkeypatch):
        """Ingesting the same URL twice completes without error on the second call."""
        html = (
            "<html><head><title>Dedup Article</title></head>"
            "<body><p>Content for dedup test. Enough text to pass the empty check.</p></body></html>"
        )

        fake_response = MagicMock()
        fake_response.raise_for_status = MagicMock()
        fake_response.text = html

        async def fake_get(self_client, url, **kwargs):
            return fake_response

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

        storage = FakeStorage()
        use_case = self._make_use_case(storage=storage)
        url = "https://example.com/dedup"

        event1 = await use_case.import_link(url)
        # Second call with same URL should succeed (upsert / overwrite, not crash)
        event2 = await use_case.import_link(url)

        assert event1 is not None
        assert event2 is not None
        # Both should record the same URL as the raw_input_ref
        assert url in event1.raw_input_ref
        assert url in event2.raw_input_ref


# ---------------------------------------------------------------------------
# IngestFileUseCase tests
# ---------------------------------------------------------------------------

class TestIngestFileUseCase:

    def _make_use_case(self, storage=None, embedding=None, llm=None):
        return IngestFileUseCase(
            storage=storage or FakeStorage(),
            embedding=embedding or FakeEmbedding(),
            llm=llm or FakeLLM(),
            workspace_id="default",
        )

    @pytest.mark.asyncio
    async def test_txt_file_ingestion(self, tmp_path):
        """A .txt file is ingested with source='file' and raw_input_type='file'."""
        txt_file = tmp_path / "notes.txt"
        txt_file.write_text("This is a plain text document with interesting content.", encoding="utf-8")

        use_case = self._make_use_case()
        event = await use_case.import_file(str(txt_file))

        assert event is not None
        assert event.source == "file"
        assert event.raw_input_type == "file"

    @pytest.mark.asyncio
    async def test_missing_file_raises_file_not_found_error(self):
        """A path to a non-existent file raises FileNotFoundError."""
        use_case = self._make_use_case()
        with pytest.raises(FileNotFoundError):
            await use_case.import_file("/nonexistent/path/does_not_exist.txt")

    @pytest.mark.asyncio
    async def test_empty_file_returns_none(self, tmp_path):
        """An empty .txt file causes import_file to return None."""
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("", encoding="utf-8")

        use_case = self._make_use_case()
        result = await use_case.import_file(str(empty_file))

        assert result is None

    @pytest.mark.asyncio
    async def test_pdf_without_pymupdf_raises_import_error(self, tmp_path, monkeypatch):
        """Attempting to import a PDF without pymupdf or pdfplumber raises ImportError
        with 'pymupdf' in the message."""
        pdf_file = tmp_path / "test.pdf"
        # Write a minimal file — contents do not matter because we intercept imports
        pdf_file.write_bytes(b"%PDF-1.4 fake pdf content")

        # Patch the internal _extract_pdf function to simulate missing libraries
        import cortex.use_cases.ingest_file as ingest_file_module

        def fake_extract_pdf(path):
            raise ImportError("PDF extraction requires pymupdf or pdfplumber. Install: pip install pymupdf")

        monkeypatch.setattr(ingest_file_module, "_extract_pdf", fake_extract_pdf)

        use_case = self._make_use_case()
        with pytest.raises(ImportError, match="pymupdf"):
            await use_case.import_file(str(pdf_file))


# ---------------------------------------------------------------------------
# ContradictionDetector tests
# ---------------------------------------------------------------------------

class TestContradictionDetector:

    @pytest.mark.asyncio
    async def test_no_llm_returns_empty(self):
        """ContradictionDetector with llm=None always returns an empty list."""
        storage = FakeStorage()
        embedding = FakeEmbedding()
        detector = ContradictionDetector(storage=storage, embedding=embedding, llm=None)

        event = _make_event(content="Something interesting")
        results = await detector.analyze(event)

        assert results == []

    @pytest.mark.asyncio
    async def test_filters_out_self_match(self):
        """The detector skips an existing event that has the same ID as the new event."""
        storage = FakeStorage()
        embedding = FakeEmbedding()
        llm = FakeLLM()

        # Insert one event and analyse that same event as the "new" event
        event = _make_event(id="self-id-001", content="Some content to compare")
        await storage.insert_event(event)

        # FakeStorage.semantic_search returns all stored events; the detector must
        # exclude the event whose id matches new_event.id
        detector = ContradictionDetector(storage=storage, embedding=embedding, llm=llm)
        results = await detector.analyze(event)

        # All returned results must have existing_event_id != event.id
        for r in results:
            assert r.existing_event_id != event.id

    @pytest.mark.asyncio
    async def test_classifies_contradiction_via_llm(self, monkeypatch):
        """When the LLM returns a contradiction JSON, the result list contains a
        ContradictionResult with signal_type='contradiction'."""
        storage = FakeStorage()
        embedding = FakeEmbedding()
        llm = FakeLLM()

        # Two existing events with different IDs and content
        existing_a = _make_event(id="existing-a", title="Event A", content="Company X is growing fast")
        existing_b = _make_event(id="existing-b", title="Event B", content="Company X is shrinking")
        await storage.insert_event(existing_a)
        await storage.insert_event(existing_b)

        contradiction_json = json.dumps({
            "signal_type": "contradiction",
            "topic": "test",
            "summary": "conflict between A and B",
            "confidence": 0.9,
        })

        async def fake_chat(self_llm, prompt: str) -> str:
            return contradiction_json

        monkeypatch.setattr(FakeLLM, "chat", fake_chat)

        new_event = _make_event(id="new-event-001", content="Company X revenue is declining")
        detector = ContradictionDetector(storage=storage, embedding=embedding, llm=llm)
        results = await detector.analyze(new_event)

        assert len(results) >= 1
        signal_types = {r.signal_type for r in results}
        assert "contradiction" in signal_types

        contradiction_result = next(r for r in results if r.signal_type == "contradiction")
        assert isinstance(contradiction_result, ContradictionResult)
        assert contradiction_result.new_event_id == new_event.id


# ---------------------------------------------------------------------------
# PushDetector tests
# ---------------------------------------------------------------------------

class FakeStorageWithStaleCoverage(FakeStorage):
    """FakeStorage that returns a stale ThesisCoverage for thesis detection tests."""

    def __init__(self, days_since_update: int, event_count: int):
        super().__init__()
        self._days = days_since_update
        self._count = event_count

    async def thesis_coverage(self, workspace_id="default") -> list[ThesisCoverage]:
        return [
            ThesisCoverage(
                thesis_name="AI Dominance",
                event_count=self._count,
                avg_confidence=0.75,
                days_since_update=self._days,
            )
        ]


class FakeStorageWithMomentum(FakeStorage):
    """FakeStorage that returns entity momentum data."""

    def __init__(self, momentum_data: list[dict]):
        super().__init__()
        self._momentum_data = momentum_data

    async def entity_momentum(self, days=7, workspace_id="default", limit=10) -> list[dict]:
        return self._momentum_data


class TestPushDetector:

    @pytest.mark.asyncio
    async def test_stale_thesis_notification(self):
        """A thesis with days_since_update >= 30 and event_count > 0 triggers a notification."""
        storage = FakeStorageWithStaleCoverage(days_since_update=60, event_count=5)
        detector = PushDetector(storage=storage, workspace_id="default")

        notifications = await detector.check_stale_theses()

        assert len(notifications) == 1
        notif = notifications[0]
        assert isinstance(notif, PushNotification)
        assert notif.trigger_type == "thesis_stale"
        assert "AI Dominance" in notif.title

    @pytest.mark.asyncio
    async def test_no_stale_thesis_when_recent(self):
        """A thesis updated within the last 30 days produces no notification."""
        storage = FakeStorageWithStaleCoverage(days_since_update=5, event_count=10)
        detector = PushDetector(storage=storage, workspace_id="default")

        notifications = await detector.check_stale_theses()

        assert notifications == []

    @pytest.mark.asyncio
    async def test_entity_momentum_spike(self):
        """An entity with >= 5 mentions in the last 7 days triggers a momentum spike notification."""
        momentum_data = [
            {"name": "OpenAI", "type": "company", "mentions": 10},
        ]
        storage = FakeStorageWithMomentum(momentum_data)
        detector = PushDetector(storage=storage, workspace_id="default")

        notifications = await detector.check_entity_momentum()

        assert len(notifications) == 1
        notif = notifications[0]
        assert isinstance(notif, PushNotification)
        assert notif.trigger_type == "entity_momentum_spike"
        assert "OpenAI" in notif.title

    @pytest.mark.asyncio
    async def test_from_contradiction_helper(self):
        """from_contradiction builds a PushNotification with the expected fields."""
        storage = FakeStorage()
        detector = PushDetector(storage=storage, workspace_id="default")

        event_ids = ["event-aaa", "event-bbb"]
        notif = detector.from_contradiction(
            signal_type="contradiction",
            topic="Market outlook",
            summary="Two sources conflict on market direction.",
            event_ids=event_ids,
        )

        assert isinstance(notif, PushNotification)
        assert notif.trigger_type == "contradiction_detected"
        assert "contradiction" in notif.title.lower() or "Market outlook" in notif.title
        assert notif.related_event_ids == event_ids
        assert notif.priority == "high"
        assert notif.workspace_id == "default"