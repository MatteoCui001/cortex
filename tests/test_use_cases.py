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
from datetime import datetime, timedelta, timezone
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
from cortex.use_cases.contradiction import (
    _dedup_signals,
    _filter_candidates,
)
from cortex.use_cases.value_scorer import score_signals as _score_signals
from cortex.use_cases.contradiction import ContradictionDetector
from cortex.use_cases.ingest import IngestUseCase
from cortex.use_cases.ingest_file import IngestFileUseCase
from cortex.use_cases.ingest_link import IngestLinkUseCase
from cortex.use_cases.push_detector import PushDetector
from tests.conftest import FakeEmbedding, FakeLLM, FakeStorage, make_event as _make_event


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

    def test_thesis_evidence_notification(self):
        """Non-neutral thesis evidence with high delta creates a notification."""
        from cortex.domain.entities import ThesisEvidence, EvidenceImpact
        storage = FakeStorage()
        detector = PushDetector(storage=storage, workspace_id="default")

        evidence = [ThesisEvidence(
            thesis_id="t1",
            event_id="ev1",
            impact=EvidenceImpact.SUPPORTS,
            confidence_delta=0.5,
            rationale="Strong data point",
        )]
        notifications = detector.check_thesis_evidence(
            evidence, thesis_texts={"t1": "AI Agent Infrastructure"},
        )

        assert len(notifications) == 1
        notif = notifications[0]
        assert isinstance(notif, PushNotification)
        assert notif.trigger_type == "thesis_evidence_recorded"
        assert "AI Agent Infrastructure" in notif.title

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


# ---------------------------------------------------------------------------
# Candidate filtering tests (Step 3)
# ---------------------------------------------------------------------------

class TestCandidateFiltering:

    def test_low_score_candidate_filtered_out(self):
        """Candidates below 0.5 score are filtered out."""
        new = _make_event(id="new-1", content="New content here")
        existing = _make_event(id="ex-1", content="Existing content here")
        candidates = [SearchResult(event=existing, score=0.35, match_type="semantic")]
        result = _filter_candidates(candidates, new)
        assert len(result) == 0

    def test_high_score_candidate_kept(self):
        """Candidates at or above 0.5 score are kept."""
        new = _make_event(id="new-1", content="New content here")
        existing = _make_event(id="ex-1", content="Existing content sufficient length text")
        candidates = [SearchResult(event=existing, score=0.7, match_type="semantic")]
        result = _filter_candidates(candidates, new)
        assert len(result) == 1

    def test_self_match_filtered(self):
        """Event with same ID as new_event is filtered."""
        new = _make_event(id="same-id", content="Content")
        existing = _make_event(id="same-id", content="Same event content")
        candidates = [SearchResult(event=existing, score=0.9, match_type="semantic")]
        result = _filter_candidates(candidates, new)
        assert len(result) == 0

    def test_stale_time_sensitive_filtered(self):
        """Time-sensitive event older than 14 days is filtered."""
        new = _make_event(id="new-1", content="New content here")
        old_date = datetime.now(timezone.utc) - timedelta(days=30)
        existing = _make_event(
            id="ex-old", content="Old time sensitive content that is long enough",
            temporality="time_sensitive", created_at=old_date,
        )
        candidates = [SearchResult(event=existing, score=0.8, match_type="semantic")]
        result = _filter_candidates(candidates, new)
        assert len(result) == 0

    def test_recent_time_sensitive_kept(self):
        """Time-sensitive event from yesterday is kept."""
        new = _make_event(id="new-1", content="New content here")
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        existing = _make_event(
            id="ex-recent", content="Recent time sensitive content long enough",
            temporality="time_sensitive", created_at=yesterday,
        )
        candidates = [SearchResult(event=existing, score=0.8, match_type="semantic")]
        result = _filter_candidates(candidates, new)
        assert len(result) == 1

    def test_weak_content_no_summary_filtered(self):
        """Event with weak key_points, no summary, short content is filtered."""
        new = _make_event(id="new-1", content="New content here")
        existing = _make_event(
            id="ex-weak", content="Short",
            summary="",
            key_points=[{"text": "(no structured key points)", "type": "claim"}],
        )
        candidates = [SearchResult(event=existing, score=0.8, match_type="semantic")]
        result = _filter_candidates(candidates, new)
        assert len(result) == 0

    def test_max_candidates_capped(self):
        """No more than 6 candidates returned."""
        new = _make_event(id="new-1", content="New content")
        candidates = [
            SearchResult(
                event=_make_event(id=f"ex-{i}", content=f"Content number {i} long enough text"),
                score=0.9,
                match_type="semantic",
            )
            for i in range(10)
        ]
        result = _filter_candidates(candidates, new)
        assert len(result) == 6


# ---------------------------------------------------------------------------
# Signal dedup and scoring tests (Step 4)
# ---------------------------------------------------------------------------

class TestSignalDedupAndScoring:

    def test_dedup_same_topic_keeps_highest_confidence(self):
        """Two signals with same topic+type: higher confidence wins."""
        signals = [
            ContradictionResult(
                new_event_id="n", existing_event_id="a",
                signal_type="contradiction", topic="AI", confidence=0.6,
            ),
            ContradictionResult(
                new_event_id="n", existing_event_id="b",
                signal_type="contradiction", topic="AI", confidence=0.9,
            ),
        ]
        result = _dedup_signals(signals)
        assert len(result) == 1
        assert result[0].confidence == 0.9

    def test_dedup_merges_evidence_event_ids(self):
        """Merged signal has both existing_event_ids."""
        signals = [
            ContradictionResult(
                new_event_id="n", existing_event_id="a",
                signal_type="contradiction", topic="AI", confidence=0.6,
            ),
            ContradictionResult(
                new_event_id="n", existing_event_id="b",
                signal_type="contradiction", topic="AI", confidence=0.9,
            ),
        ]
        result = _dedup_signals(signals)
        assert "a" in result[0].evidence_event_ids
        assert "b" in result[0].evidence_event_ids

    def test_dedup_different_topics_both_kept(self):
        """Different topics are not deduped."""
        signals = [
            ContradictionResult(
                new_event_id="n", existing_event_id="a",
                signal_type="contradiction", topic="AI", confidence=0.8,
            ),
            ContradictionResult(
                new_event_id="n", existing_event_id="b",
                signal_type="contradiction", topic="Biotech", confidence=0.7,
            ),
        ]
        result = _dedup_signals(signals)
        assert len(result) == 2

    def test_scoring_contradiction_beats_bridge(self):
        """Contradiction has higher base priority than bridge."""
        event = _make_event(source_weight=0.5)
        signals = [
            ContradictionResult(
                new_event_id="n", existing_event_id="a",
                signal_type="bridge", topic="A", confidence=0.9,
                evidence_event_ids=["a"],
            ),
            ContradictionResult(
                new_event_id="n", existing_event_id="b",
                signal_type="contradiction", topic="B", confidence=0.7,
                evidence_event_ids=["b"],
            ),
        ]
        result = _score_signals(signals, event)
        assert result[0].signal_type == "contradiction"

    def test_scoring_thesis_boost_applied(self):
        """Event with thesis_links gets higher score."""
        event_with = _make_event(thesis_links=["AI Dominance"], source_weight=0.5)
        event_without = _make_event(thesis_links=[], source_weight=0.5)
        signal = ContradictionResult(
            new_event_id="n", existing_event_id="a",
            signal_type="new_signal", topic="X", confidence=0.7,
            evidence_event_ids=["a"],
        )
        import copy
        s1 = copy.deepcopy(signal)
        s2 = copy.deepcopy(signal)
        _score_signals([s1], event_with)
        _score_signals([s2], event_without)
        assert s1.priority_score > s2.priority_score

    def test_scoring_disagree_stance_boost(self):
        """user_stance=disagree increases priority."""
        event_disagree = _make_event(user_stance="disagree", source_weight=0.5)
        event_none = _make_event(user_stance=None, source_weight=0.5)
        import copy
        signal = ContradictionResult(
            new_event_id="n", existing_event_id="a",
            signal_type="contradiction", topic="X", confidence=0.7,
            evidence_event_ids=["a"],
        )
        s1 = copy.deepcopy(signal)
        s2 = copy.deepcopy(signal)
        _score_signals([s1], event_disagree)
        _score_signals([s2], event_none)
        assert s1.priority_score > s2.priority_score

    def test_scoring_sort_order_descending(self):
        """Results are sorted highest priority first."""
        event = _make_event(source_weight=0.5)
        signals = [
            ContradictionResult(
                new_event_id="n", existing_event_id="a",
                signal_type="new_signal", topic="Low", confidence=0.3,
                evidence_event_ids=["a"],
            ),
            ContradictionResult(
                new_event_id="n", existing_event_id="b",
                signal_type="contradiction", topic="High", confidence=0.9,
                evidence_event_ids=["b"],
            ),
        ]
        result = _score_signals(signals, event)
        assert result[0].priority_score >= result[1].priority_score
        assert result[0].signal_type == "contradiction"


# ---------------------------------------------------------------------------
# PushDetector.check_signals tests (Step 5)
# ---------------------------------------------------------------------------

class TestPushDetectorSignals:

    def test_check_signals_contradiction_above_threshold(self):
        """Signal with high priority_score produces a notification."""
        storage = FakeStorage()
        push = PushDetector(storage=storage, workspace_id="default")
        signal = ContradictionResult(
            new_event_id="n", existing_event_id="a",
            signal_type="contradiction", topic="AI", summary="Conflict",
            confidence=0.9, priority_score=0.8,
            evidence_event_ids=["a", "b"],
            rationale="Directly contradicts prior claim",
        )
        notifs = push.check_signals([signal])
        assert len(notifs) == 1
        assert notifs[0].trigger_type == "contradiction_detected"
        assert notifs[0].priority == "high"
        assert "Directly contradicts" in notifs[0].body

    def test_check_signals_below_threshold_skipped(self):
        """Signal with low priority_score is skipped."""
        storage = FakeStorage()
        push = PushDetector(storage=storage, workspace_id="default")
        signal = ContradictionResult(
            new_event_id="n", existing_event_id="a",
            signal_type="answer", topic="X", confidence=0.3,
            priority_score=0.3, evidence_event_ids=["a"],
        )
        notifs = push.check_signals([signal])
        assert len(notifs) == 0

    def test_check_signals_new_signal_always_skipped(self):
        """new_signal type never produces a notification."""
        storage = FakeStorage()
        push = PushDetector(storage=storage, workspace_id="default")
        signal = ContradictionResult(
            new_event_id="n", existing_event_id="a",
            signal_type="new_signal", topic="X", confidence=0.9,
            priority_score=0.9, evidence_event_ids=["a"],
        )
        notifs = push.check_signals([signal])
        assert len(notifs) == 0

    @pytest.mark.asyncio
    async def test_check_all_with_signals_merges(self):
        """check_all with signals includes signal notifications."""
        storage = FakeStorageWithStaleCoverage(days_since_update=60, event_count=5)
        push = PushDetector(storage=storage, workspace_id="default")
        signal = ContradictionResult(
            new_event_id="n", existing_event_id="a",
            signal_type="contradiction", topic="AI",
            confidence=0.9, priority_score=0.8,
            evidence_event_ids=["a"],
        )
        notifs = await push.check_all(signals=[signal])
        types = {n.trigger_type for n in notifs}
        assert "contradiction_detected" in types
        assert "thesis_stale" in types

    @pytest.mark.asyncio
    async def test_check_all_without_signals_unchanged(self):
        """check_all() with no signals returns only stale+momentum."""
        storage = FakeStorageWithStaleCoverage(days_since_update=60, event_count=5)
        push = PushDetector(storage=storage, workspace_id="default")
        notifs = await push.check_all()
        types = {n.trigger_type for n in notifs}
        assert "thesis_stale" in types
        assert "contradiction_detected" not in types


# ---------------------------------------------------------------------------
# Classification Audit tests
# ---------------------------------------------------------------------------

class FakeStorageForAudit(FakeStorage):
    """Returns pre-configured events for audit testing."""

    def __init__(self, events: list[KnowledgeEvent]):
        super().__init__()
        self._audit_events = events

    async def get_events_without_classification(self, workspace_id="default", limit=50):
        return self._audit_events[:limit]


class TestAuditClassification:

    def _make_audit_event(self, **kwargs) -> KnowledgeEvent:
        defaults = dict(
            id=str(uuid.uuid4()),
            workspace_id="default",
            type=EventType.NOTE,
            title="Audit Event",
            content="Some content for audit",
            summary="Summary",
            tags=[],
            thesis_links=[],
            confidence=0.7,
            source="api",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        defaults.update(kwargs)
        return KnowledgeEvent(**defaults)

    @pytest.mark.asyncio
    async def test_clean_events_no_issues(self):
        """Fully classified events should produce zero issues."""
        from cortex.use_cases.maintenance import MaintenanceUseCase
        # No events returned from get_events_without_classification
        storage = FakeStorageForAudit(events=[])
        maint = MaintenanceUseCase(storage, FakeEmbedding())
        result = await maint.audit_classification()
        assert result["events_checked"] == 0
        assert all(c == 0 for c in result["issues"].values())

    @pytest.mark.asyncio
    async def test_missing_source_type(self):
        """Events with no source_type are flagged."""
        from cortex.use_cases.maintenance import MaintenanceUseCase
        evt = self._make_audit_event(source_type=None, temporality="trend",
                                     nature_tags=["claim"],
                                     key_points=[{"text": "some valid point", "type": "claim"}])
        storage = FakeStorageForAudit(events=[evt])
        maint = MaintenanceUseCase(storage, FakeEmbedding())
        result = await maint.audit_classification()
        assert result["issues"]["missing_source_type"] == 1

    @pytest.mark.asyncio
    async def test_invalid_source_type(self):
        """Events with unrecognized source_type are flagged."""
        from cortex.use_cases.maintenance import MaintenanceUseCase
        evt = self._make_audit_event(source_type="unknown_type", temporality="trend",
                                     nature_tags=["claim"],
                                     key_points=[{"text": "some valid point", "type": "claim"}])
        storage = FakeStorageForAudit(events=[evt])
        maint = MaintenanceUseCase(storage, FakeEmbedding())
        result = await maint.audit_classification()
        assert result["issues"]["invalid_source_type"] == 1

    @pytest.mark.asyncio
    async def test_weak_key_points_flagged(self):
        """Events with weak key_points are flagged."""
        from cortex.use_cases.maintenance import MaintenanceUseCase
        evt = self._make_audit_event(
            source_type="published", temporality="trend",
            nature_tags=["claim"],
            key_points=[{"text": "(no structured key points)", "type": "claim"}],
        )
        storage = FakeStorageForAudit(events=[evt])
        maint = MaintenanceUseCase(storage, FakeEmbedding())
        result = await maint.audit_classification()
        assert result["issues"]["weak_key_points"] == 1

    @pytest.mark.asyncio
    async def test_reclassify_ids_deduped(self):
        """event_ids_to_reclassify doesn't contain duplicates."""
        from cortex.use_cases.maintenance import MaintenanceUseCase
        # Event missing both source_type AND temporality
        evt = self._make_audit_event(source_type=None, temporality=None,
                                     nature_tags=["claim"],
                                     key_points=[{"text": "some valid point", "type": "claim"}])
        storage = FakeStorageForAudit(events=[evt])
        maint = MaintenanceUseCase(storage, FakeEmbedding())
        result = await maint.audit_classification()
        assert len(result["event_ids_to_reclassify"]) == 1


# ---------------------------------------------------------------------------
# Quality Gate (LLM skip) Tests
# ---------------------------------------------------------------------------

class TestQualityGate:

    @pytest.mark.asyncio
    async def test_skip_content_returns_none(self):
        """When LLM returns skip=True, import_text should return None."""
        storage = FakeStorage()
        embedding = FakeEmbedding()

        class SkippingLLM(FakeLLM):
            async def extract_metadata(self, content):
                return {"skip": True, "skip_reason": "prompt template"}

        llm = SkippingLLM()
        uc = IngestUseCase(storage, embedding, llm, workspace_id="default")
        result = await uc.import_text("Make shorter", "Make shorter")
        assert result is None
        assert len(storage._events) == 0

    @pytest.mark.asyncio
    async def test_keep_content_ingests_normally(self):
        """When LLM returns skip=False, content is ingested as normal."""
        storage = FakeStorage()
        embedding = FakeEmbedding()
        llm = FakeLLM()
        uc = IngestUseCase(storage, embedding, llm, workspace_id="default")
        result = await uc.import_text("光伏银浆成本降30%", "重要行业趋势")
        assert result is not None
        assert len(storage._events) == 1

    @pytest.mark.asyncio
    async def test_vault_import_counts_skips(self):
        """Vault import should count skipped files properly."""
        import tempfile, os
        storage = FakeStorage()
        embedding = FakeEmbedding()

        class SelectiveLLM(FakeLLM):
            async def extract_metadata(self, content):
                if "template" in content.lower():
                    return {"skip": True, "skip_reason": "tool template"}
                return await super().extract_metadata(content)

        llm = SelectiveLLM()
        uc = IngestUseCase(storage, embedding, llm, workspace_id="default")

        with tempfile.TemporaryDirectory() as td:
            # Real knowledge
            with open(os.path.join(td, "deal.md"), "w") as f:
                f.write("蛮酷 Series A 进展")
            # Template junk
            with open(os.path.join(td, "template.md"), "w") as f:
                f.write("Template: Make shorter")

            stats = await uc.import_vault(td)
            assert stats["imported"] == 1
            assert stats["skipped"] == 1


# ---------------------------------------------------------------------------
# Entity Embedding at Ingest Time (Phase 12)
# ---------------------------------------------------------------------------

class TestEntityEmbeddingAtIngest:

    @pytest.mark.asyncio
    async def test_entity_gets_embedding_at_ingest(self):
        """Entities extracted during ingest should have embeddings populated."""
        storage = FakeStorage()
        embedding = FakeEmbedding()

        class LLMWithEntities(FakeLLM):
            async def extract_metadata(self, content):
                base = await super().extract_metadata(content)
                base["entities"] = [
                    {"type": "company", "name": "OpenAI"},
                    {"type": "person", "name": "Sam Altman"},
                ]
                return base

        llm = LLMWithEntities()
        uc = IngestUseCase(storage, embedding, llm, workspace_id="default")
        await uc.import_text("GPT-5 News", "OpenAI announced GPT-5. Sam Altman confirmed.")

        # Two entities stored with canonical names and embeddings
        assert len(storage._entities) == 2
        names = {e.name for e in storage._entities.values()}
        assert names == {"openai", "sam altman"}
        for entity in storage._entities.values():
            assert len(entity.embedding) == embedding.dimensions

    @pytest.mark.asyncio
    async def test_entity_embedding_failure_does_not_block_ingest(self):
        """If embedding fails for an entity, ingest should still complete."""
        storage = FakeStorage()

        class FailingEmbedding(FakeEmbedding):
            async def embed(self, text):
                # Fail on the canonical name "openai"
                if text == "openai":
                    raise RuntimeError("Embedding service down")
                return await super().embed(text)

            async def embed_batch(self, texts):
                # Simulate partial failure: raise if any text would fail
                for t in texts:
                    if t == "openai":
                        raise RuntimeError("Batch embedding service down")
                return await super().embed_batch(texts)

        class LLMWithEntities(FakeLLM):
            async def extract_metadata(self, content):
                base = await super().extract_metadata(content)
                base["entities"] = [
                    {"type": "company", "name": "OpenAI"},
                    {"type": "person", "name": "Sam Altman"},
                ]
                return base

        llm = LLMWithEntities()
        uc = IngestUseCase(storage, FailingEmbedding(), llm, workspace_id="default")
        event = await uc.import_text("AI News", "OpenAI and Sam Altman news")

        # Event should still be created
        assert event is not None
        assert event.id in storage._events
        # Both entities stored — one without embedding (failed), one with
        assert len(storage._entities) == 2
        entities = list(storage._entities.values())
        names = {e.name for e in entities}
        assert names == {"openai", "sam altman"}
        openai_ent = next(e for e in entities if e.name == "openai")
        altman_ent = next(e for e in entities if e.name == "sam altman")
        assert openai_ent.embedding == []  # failed, empty
        assert len(altman_ent.embedding) == 512  # succeeded


# ---------------------------------------------------------------------------
# Entity Canonicalization (Phase 13)
# ---------------------------------------------------------------------------

class TestEntityCanonicalization:

    def _make_llm(self, entities):
        """Create a FakeLLM that returns specific entities."""
        class LLMWithEntities(FakeLLM):
            async def extract_metadata(self, content):
                base = await super().extract_metadata(content)
                base["entities"] = entities
                return base
        return LLMWithEntities()

    @pytest.mark.asyncio
    async def test_case_variants_resolve_to_same_entity(self):
        """'OpenAI', 'openai', 'OPENAI' should all map to one entity."""
        storage = FakeStorage()
        embedding = FakeEmbedding()

        # First ingest: "OpenAI"
        llm1 = self._make_llm([{"type": "company", "name": "OpenAI"}])
        uc1 = IngestUseCase(storage, embedding, llm1, workspace_id="default")
        await uc1.import_text("News 1", "OpenAI released something.")

        assert len(storage._entities) == 1
        ent = list(storage._entities.values())[0]
        assert ent.name == "openai"
        assert "OpenAI" in ent.aliases

        # Second ingest: "OPENAI" — should reuse same entity
        llm2 = self._make_llm([{"type": "company", "name": "OPENAI"}])
        uc2 = IngestUseCase(storage, embedding, llm2, workspace_id="default")
        await uc2.import_text("News 2", "OPENAI did something else.")

        assert len(storage._entities) == 1
        ent = list(storage._entities.values())[0]
        assert "OPENAI" in ent.aliases

    @pytest.mark.asyncio
    async def test_hyphen_space_variants_resolve(self):
        """'Open AI' and 'Open-AI' should resolve to same entity as 'openai'... wait,
        'Open AI' -> 'open ai' and 'Open-AI' -> 'open ai'. These match each other
        but not 'OpenAI' -> 'openai'. This is correct — only truly equivalent forms merge."""
        storage = FakeStorage()
        embedding = FakeEmbedding()

        llm1 = self._make_llm([{"type": "company", "name": "Open-AI"}])
        uc1 = IngestUseCase(storage, embedding, llm1, workspace_id="default")
        await uc1.import_text("News 1", "Open-AI stuff.")

        llm2 = self._make_llm([{"type": "company", "name": "Open AI"}])
        uc2 = IngestUseCase(storage, embedding, llm2, workspace_id="default")
        await uc2.import_text("News 2", "Open AI stuff.")

        # Both resolve to canonical "open ai"
        assert len(storage._entities) == 1
        ent = list(storage._entities.values())[0]
        assert ent.name == "open ai"

    @pytest.mark.asyncio
    async def test_corporate_suffix_stripped(self):
        """'Tesla, Inc.' and 'Tesla' should resolve to same entity."""
        storage = FakeStorage()
        embedding = FakeEmbedding()

        llm1 = self._make_llm([{"type": "company", "name": "Tesla, Inc."}])
        uc1 = IngestUseCase(storage, embedding, llm1, workspace_id="default")
        await uc1.import_text("News 1", "Tesla Inc filed.")

        llm2 = self._make_llm([{"type": "company", "name": "Tesla"}])
        uc2 = IngestUseCase(storage, embedding, llm2, workspace_id="default")
        await uc2.import_text("News 2", "Tesla earnings.")

        assert len(storage._entities) == 1

    @pytest.mark.asyncio
    async def test_different_entities_stay_separate(self):
        """Clearly different entities should not be merged."""
        storage = FakeStorage()
        embedding = FakeEmbedding()

        llm = self._make_llm([
            {"type": "company", "name": "OpenAI"},
            {"type": "company", "name": "Google"},
        ])
        uc = IngestUseCase(storage, embedding, llm, workspace_id="default")
        await uc.import_text("News", "OpenAI vs Google.")

        assert len(storage._entities) == 2

    @pytest.mark.asyncio
    async def test_different_types_stay_separate(self):
        """Same name but different entity types should remain separate."""
        storage = FakeStorage()
        embedding = FakeEmbedding()

        llm = self._make_llm([
            {"type": "company", "name": "Apple"},
            {"type": "concept", "name": "Apple"},
        ])
        uc = IngestUseCase(storage, embedding, llm, workspace_id="default")
        await uc.import_text("News", "Apple the company and apple the fruit.")

        assert len(storage._entities) == 2

    @pytest.mark.asyncio
    async def test_alias_appended_on_reuse(self):
        """When reusing a canonical entity, the raw name should be added as alias."""
        storage = FakeStorage()
        embedding = FakeEmbedding()

        llm1 = self._make_llm([{"type": "person", "name": "Sam Altman"}])
        uc1 = IngestUseCase(storage, embedding, llm1, workspace_id="default")
        await uc1.import_text("News 1", "Sam Altman spoke.")

        llm2 = self._make_llm([{"type": "person", "name": "SAM ALTMAN"}])
        uc2 = IngestUseCase(storage, embedding, llm2, workspace_id="default")
        await uc2.import_text("News 2", "SAM ALTMAN tweeted.")

        assert len(storage._entities) == 1
        ent = list(storage._entities.values())[0]
        assert ent.name == "sam altman"
        assert "Sam Altman" in ent.aliases
        assert "SAM ALTMAN" in ent.aliases


# ---------------------------------------------------------------------------
# Thesis Trend Logic (Phase 12)
# ---------------------------------------------------------------------------

from cortex.use_cases.analyze import AnalyzeUseCase


class TestThesisTrend:
    """Unit tests for AnalyzeUseCase.thesis_coverage trend calculation."""

    def _make_storage(self, thesis_coverage_data, trend_data):
        """Create a FakeStorage with preconfigured thesis_coverage + thesis_trend."""
        storage = FakeStorage()

        async def _thesis_coverage(workspace_id="default"):
            return thesis_coverage_data

        async def _thesis_trend(workspace_id="default", window_days=14):
            return trend_data

        storage.thesis_coverage = _thesis_coverage
        storage.thesis_trend = _thesis_trend
        return storage

    @pytest.mark.asyncio
    async def test_trend_up(self):
        """Delta > 0.05 => trend_direction = 'up'."""
        from cortex.domain.entities import ThesisCoverage
        tc = ThesisCoverage(
            thesis_name="AI Agents", event_count=10, avg_confidence=0.8,
            type_distribution={}, latest_update=None, days_since_update=0,
        )
        trend = {
            "AI Agents": {
                "recent_avg": 0.9, "previous_avg": 0.7,
                "recent_count": 5, "previous_count": 5,
            }
        }
        storage = self._make_storage([tc], trend)
        uc = AnalyzeUseCase(storage, "default")
        result = await uc.thesis_coverage()

        assert len(result) == 1
        assert result[0].trend_direction == "up"
        assert result[0].confidence_delta == 0.2

    @pytest.mark.asyncio
    async def test_trend_down(self):
        """Delta < -0.05 => trend_direction = 'down'."""
        from cortex.domain.entities import ThesisCoverage
        tc = ThesisCoverage(
            thesis_name="Solar", event_count=8, avg_confidence=0.6,
            type_distribution={}, latest_update=None, days_since_update=0,
        )
        trend = {
            "Solar": {
                "recent_avg": 0.5, "previous_avg": 0.8,
                "recent_count": 4, "previous_count": 4,
            }
        }
        storage = self._make_storage([tc], trend)
        uc = AnalyzeUseCase(storage, "default")
        result = await uc.thesis_coverage()

        assert result[0].trend_direction == "down"
        assert result[0].confidence_delta == -0.3

    @pytest.mark.asyncio
    async def test_trend_flat(self):
        """Delta between -0.05 and 0.05 => 'flat'."""
        from cortex.domain.entities import ThesisCoverage
        tc = ThesisCoverage(
            thesis_name="World Models", event_count=6, avg_confidence=0.75,
            type_distribution={}, latest_update=None, days_since_update=0,
        )
        trend = {
            "World Models": {
                "recent_avg": 0.76, "previous_avg": 0.74,
                "recent_count": 3, "previous_count": 3,
            }
        }
        storage = self._make_storage([tc], trend)
        uc = AnalyzeUseCase(storage, "default")
        result = await uc.thesis_coverage()

        assert result[0].trend_direction == "flat"
        assert abs(result[0].confidence_delta) <= 0.05

    @pytest.mark.asyncio
    async def test_insufficient_data_no_trend(self):
        """No trend data for a thesis => 'insufficient_data'."""
        from cortex.domain.entities import ThesisCoverage
        tc = ThesisCoverage(
            thesis_name="Orphan Thesis", event_count=2, avg_confidence=0.5,
            type_distribution={}, latest_update=None, days_since_update=0,
        )
        storage = self._make_storage([tc], {})
        uc = AnalyzeUseCase(storage, "default")
        result = await uc.thesis_coverage()

        assert result[0].trend_direction == "insufficient_data"

    @pytest.mark.asyncio
    async def test_low_sample_still_computes_trend(self):
        """Both windows have 1 sample each — enough for trend with relaxed threshold."""
        from cortex.domain.entities import ThesisCoverage
        tc = ThesisCoverage(
            thesis_name="Harness", event_count=3, avg_confidence=0.6,
            type_distribution={}, latest_update=None, days_since_update=0,
        )
        trend = {
            "Harness": {
                "recent_avg": 0.9, "previous_avg": 0.4,
                "recent_count": 1, "previous_count": 1,
            }
        }
        storage = self._make_storage([tc], trend)
        uc = AnalyzeUseCase(storage, "default")
        result = await uc.thesis_coverage()

        assert result[0].trend_direction == "up"
        assert result[0].confidence_delta is not None

    @pytest.mark.asyncio
    async def test_insufficient_data_one_window_null(self):
        """One window avg is None => 'insufficient_data'."""
        from cortex.domain.entities import ThesisCoverage
        tc = ThesisCoverage(
            thesis_name="Meta", event_count=1, avg_confidence=0.5,
            type_distribution={}, latest_update=None, days_since_update=0,
        )
        trend = {
            "Meta": {
                "recent_avg": 0.8, "previous_avg": None,
                "recent_count": 3, "previous_count": 0,
            }
        }
        storage = self._make_storage([tc], trend)
        uc = AnalyzeUseCase(storage, "default")
        result = await uc.thesis_coverage()

        assert result[0].trend_direction == "insufficient_data"


# ---------------------------------------------------------------------------
# MaintenanceUseCase — backfill / normalize / deduplicate
# ---------------------------------------------------------------------------

from cortex.use_cases.maintenance import MaintenanceUseCase


class TestBackfillEntityEmbeddings:

    @pytest.mark.asyncio
    async def test_backfill_processes_all(self):
        storage = FakeStorage()
        embedding = FakeEmbedding()
        _entities_without = [
            {"id": "e1", "name": "OpenAI"},
            {"id": "e2", "name": "Google"},
        ]
        total = len(_entities_without)

        async def _count(workspace_id="default"):
            return total

        async def _get(workspace_id="default", limit=50):
            batch = _entities_without[:limit]
            del _entities_without[:limit]
            return batch

        updated = {}
        async def _update(entity_id, emb):
            updated[entity_id] = emb

        storage.count_entities_without_embedding = _count
        storage.get_entities_without_embedding = _get
        storage.update_entity_embedding = _update

        uc = MaintenanceUseCase(storage, embedding, "default")
        stats = await uc.backfill_entity_embeddings()

        assert stats["total"] == 2
        assert stats["processed"] == 2
        assert "e1" in updated
        assert "e2" in updated
        assert len(updated["e1"]) == 512

    @pytest.mark.asyncio
    async def test_backfill_empty(self):
        storage = FakeStorage()
        embedding = FakeEmbedding()
        uc = MaintenanceUseCase(storage, embedding, "default")
        stats = await uc.backfill_entity_embeddings()
        assert stats["total"] == 0
        assert stats["processed"] == 0


class TestNormalizeTags:

    @pytest.mark.asyncio
    async def test_canonical_form_applied(self):
        storage = FakeStorage()
        embedding = FakeEmbedding()

        events_with_tags = [
            {"id": "ev1", "tags": ["AI", "ai", "Ai"]},
            {"id": "ev2", "tags": ["machine-learning"]},
        ]
        tag_config = {
            "canonical_forms": {
                "artificial intelligence": ["AI", "ai"],
            }
        }

        updated = {}
        async def _get_all(workspace_id="default"):
            return events_with_tags
        async def _update(event_id, tags):
            updated[event_id] = tags

        storage.get_all_events_with_tags = _get_all
        storage.update_event_tags = _update

        uc = MaintenanceUseCase(storage, embedding, "default", tag_config=tag_config)
        stats = await uc.normalize_tags()

        assert stats["events_checked"] == 2
        assert stats["events_updated"] >= 1
        assert "ev1" in updated
        # All three variants should map to canonical
        assert updated["ev1"] == ["artificial intelligence"]

    @pytest.mark.asyncio
    async def test_no_changes_needed(self):
        storage = FakeStorage()
        embedding = FakeEmbedding()

        async def _get_all(workspace_id="default"):
            return [{"id": "ev1", "tags": ["clean tag"]}]
        async def _update(event_id, tags):
            pass

        storage.get_all_events_with_tags = _get_all
        storage.update_event_tags = _update

        uc = MaintenanceUseCase(storage, embedding, "default")
        stats = await uc.normalize_tags()
        assert stats["events_updated"] == 0


class TestDeduplicateEntities:

    @pytest.mark.asyncio
    async def test_merges_duplicate_names(self):
        storage = FakeStorage()
        embedding = FakeEmbedding()

        entities = [
            {"id": "e1", "name": "OpenAI", "mention_count": 10},
            {"id": "e2", "name": "openai", "mention_count": 3},
            {"id": "e3", "name": "Google", "mention_count": 5},
        ]
        merged = []

        async def _get_all(workspace_id="default"):
            return entities
        async def _merge(keep_id, remove_id):
            merged.append((keep_id, remove_id))

        storage.get_all_entities = _get_all
        storage.merge_entities = _merge

        uc = MaintenanceUseCase(storage, embedding, "default")
        stats = await uc.deduplicate_entities()

        assert stats["merged"] == 1
        assert stats["candidates"] == 1
        # e1 has more mentions, so e2 gets merged into e1
        assert merged == [("e1", "e2")]

    @pytest.mark.asyncio
    async def test_no_duplicates(self):
        storage = FakeStorage()
        embedding = FakeEmbedding()

        entities = [
            {"id": "e1", "name": "OpenAI", "mention_count": 10},
            {"id": "e2", "name": "Google", "mention_count": 5},
        ]

        async def _get_all(workspace_id="default"):
            return entities
        async def _merge(keep_id, remove_id):
            pass

        storage.get_all_entities = _get_all
        storage.merge_entities = _merge

        uc = MaintenanceUseCase(storage, embedding, "default")
        stats = await uc.deduplicate_entities()

        assert stats["merged"] == 0
        assert stats["candidates"] == 0
