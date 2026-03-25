"""
Shared fixtures for the Cortex test suite.
Provides fake adapters and a TestClient wired with them.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cortex.api.routes import router
from cortex.domain.entities import (
    Annotation,
    ContradictionResult,
    KnowledgeEvent,
    EventType,
    Notification,
    NotificationStatus,
    SearchResult,
    SignalFeedback,
    ThesisCoverage,
)
from cortex.domain.ports import EmbeddingPort, LLMPort, StoragePort
from cortex.use_cases.analyze import AnalyzeUseCase
from cortex.use_cases.ingest import IngestUseCase
from cortex.use_cases.search import SearchUseCase


# ------------------------------------------------------------------
# Fake adapters
# ------------------------------------------------------------------

class FakeStorage(StoragePort):
    """In-memory storage for tests."""

    def __init__(self):
        self._events: dict[str, KnowledgeEvent] = {}
        self._annotations: list[Annotation] = []
        self._signals: list[ContradictionResult] = []
        self._signal_feedback: list[SignalFeedback] = []
        self._notifications: dict[str, Notification] = {}

    def _make_event(self, **kwargs) -> KnowledgeEvent:
        defaults = dict(
            id=str(uuid.uuid4()),
            workspace_id="default",
            type=EventType.NOTE,
            title="Test Event",
            content="Test content",
            summary="Test summary",
            tags=["test"],
            thesis_links=[],
            confidence=0.8,
            source="api",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        defaults.update(kwargs)
        return KnowledgeEvent(**defaults)

    # --- write ---

    async def insert_event(self, event: KnowledgeEvent) -> str:
        self._events[event.id] = event
        return event.id

    async def insert_entity(self, entity) -> str:
        return entity.id

    async def insert_relation(self, relation) -> str:
        return relation.id

    # --- reads ---

    async def get_event(self, event_id: str, workspace_id: str = "default") -> Optional[KnowledgeEvent]:
        return self._events.get(event_id)

    async def semantic_search(self, embedding, *, workspace_id="default", limit=10,
                              type_filter=None, min_score=0.0) -> list[SearchResult]:
        results = []
        for ev in list(self._events.values())[:limit]:
            results.append(SearchResult(event=ev, score=0.9, match_type="semantic"))
        return results

    async def fulltext_search(self, query, *, workspace_id="default", limit=10,
                              type_filter=None) -> list[SearchResult]:
        results = []
        for ev in list(self._events.values())[:limit]:
            results.append(SearchResult(event=ev, score=0.8, match_type="fulltext"))
        return results

    async def get_by_thesis(self, thesis_name, workspace_id="default") -> list[KnowledgeEvent]:
        return [ev for ev in self._events.values() if thesis_name in ev.thesis_links]

    async def get_relations_for(self, object_id, workspace_id="default") -> list[dict]:
        return []

    async def find_related(self, event_id, *, workspace_id="default", limit=10) -> list[SearchResult]:
        return []

    async def stale_events(self, days=30, workspace_id="default") -> list[KnowledgeEvent]:
        return []

    async def thesis_coverage(self, workspace_id="default") -> list[ThesisCoverage]:
        return []

    async def daily_events(self, target_date, workspace_id="default") -> list[KnowledgeEvent]:
        return []

    async def stats(self, workspace_id="default") -> dict:
        return {
            "total_events": len(self._events),
            "total_entities": 0,
            "total_relations": 0,
            "workspace": workspace_id,
        }

    async def event_exists(self, source_path, workspace_id="default") -> bool:
        return False

    async def count_entities_without_embedding(self, workspace_id="default") -> int:
        return 0

    async def get_entities_without_embedding(self, workspace_id="default", limit=50) -> list[dict]:
        return []

    async def update_entity_embedding(self, entity_id, embedding):
        pass

    async def get_all_events_with_tags(self, workspace_id="default") -> list[dict]:
        return []

    async def update_event_tags(self, event_id, tags):
        pass

    async def get_all_entities(self, workspace_id="default") -> list[dict]:
        return []

    async def merge_entities(self, keep_id, remove_id):
        pass

    async def semantic_search_entities(self, embedding, *, workspace_id="default",
                                       entity_types=None, limit=20) -> list[dict]:
        return []

    async def get_events_for_entity(self, entity_id, workspace_id="default", limit=50) -> list[KnowledgeEvent]:
        return []

    async def recent_events_by_thesis(self, days=1, workspace_id="default") -> list[dict]:
        return []

    async def high_confidence_recent(self, days=7, min_confidence=0.8,
                                     workspace_id="default", limit=10) -> list[KnowledgeEvent]:
        return []

    async def entity_momentum(self, days=7, workspace_id="default", limit=10) -> list[dict]:
        return []

    async def get_existing_source_paths(self, workspace_id="default") -> dict[str, str]:
        return {}

    async def create_annotation(self, annotation) -> str:
        self._annotations.append(annotation)
        return annotation.id

    async def get_annotations(self, workspace_id, target_type, target_id) -> list:
        return [
            a for a in self._annotations
            if a.target_type == target_type and a.target_id == target_id
        ]

    async def get_events_without_classification(self, workspace_id="default", limit=50) -> list[KnowledgeEvent]:
        return []

    async def update_event_classification(self, event_id, source_type, source_weight,
                                          nature_tags, temporality, key_points, stance):
        pass

    # --- Phase 3.6: Signal operations ---

    async def upsert_signal(self, signal: ContradictionResult) -> str:
        for i, s in enumerate(self._signals):
            if s.id == signal.id:
                self._signals[i] = signal
                return signal.id
        self._signals.append(signal)
        return signal.id

    async def get_signals(self, workspace_id, *, event_id=None, limit=50):
        results = [s for s in self._signals if s.workspace_id == workspace_id]
        if event_id:
            results = [s for s in results if s.new_event_id == event_id]
        return results[:limit]

    async def create_signal_feedback(self, feedback: SignalFeedback) -> str:
        self._signal_feedback.append(feedback)
        return feedback.id

    async def get_feedback_summary(self, workspace_id):
        from collections import defaultdict
        groups = defaultdict(lambda: {"useful": 0, "not_useful": 0, "wrong": 0, "save_for_later": 0})
        for fb in self._signal_feedback:
            if fb.workspace_id != workspace_id:
                continue
            # Find signal to get type and topic
            sig = next((s for s in self._signals if s.id == fb.signal_id), None)
            if not sig:
                continue
            key = (sig.signal_type, (sig.topic or "").lower().strip())
            groups[key][fb.verdict] += 1
        return dict(groups)

    async def get_thesis_feedback_stats(self, workspace_id):
        from collections import defaultdict
        thesis_stats = defaultdict(lambda: {"useful": 0, "not_useful": 0, "wrong": 0})
        for fb in self._signal_feedback:
            if fb.workspace_id != workspace_id:
                continue
            sig = next((s for s in self._signals if s.id == fb.signal_id), None)
            if not sig or not sig.thesis_links:
                continue
            thesis = sig.thesis_links[0]
            if fb.verdict in thesis_stats[thesis]:
                thesis_stats[thesis][fb.verdict] += 1
        return [{"thesis_link": k, **v} for k, v in thesis_stats.items()]

    # --- Phase 4: Notification operations ---

    async def insert_notification(self, notification: Notification) -> str:
        self._notifications[notification.id] = notification
        return notification.id

    async def get_notifications(self, workspace_id, *, status=None, limit=50):
        results = [
            n for n in self._notifications.values()
            if n.workspace_id == workspace_id
        ]
        if status:
            results = [n for n in results if n.status.value == status]
        results.sort(key=lambda n: n.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return results[:limit]

    async def get_notification(self, notification_id, workspace_id="default"):
        n = self._notifications.get(notification_id)
        if n and n.workspace_id == workspace_id:
            return n
        return None

    async def update_notification_status(self, notification_id, new_status, *,
                                          delivered_at=None, acted_at=None):
        n = self._notifications.get(notification_id)
        if not n:
            return False
        n.status = new_status
        if delivered_at:
            n.delivered_at = delivered_at
        if acted_at:
            n.acted_at = acted_at
        return True

    async def check_dedup(self, workspace_id, dedup_key):
        terminal = {NotificationStatus.ACKED, NotificationStatus.DISMISSED, NotificationStatus.FAILED}
        for n in self._notifications.values():
            if (n.workspace_id == workspace_id
                    and n.dedup_key == dedup_key
                    and n.status not in terminal):
                return True
        return False


class FakeEmbedding(EmbeddingPort):
    """Returns zero vectors of the configured dimension."""

    @property
    def dimensions(self) -> int:
        return 512

    async def embed(self, text: str) -> list[float]:
        return [0.0] * self.dimensions

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self.dimensions for _ in texts]


class FakeLLM(LLMPort):
    """Returns minimal valid responses without any real LLM call."""

    async def extract_metadata(self, content: str) -> dict:
        return {
            "summary": content[:100].replace("\n", " "),
            "tags": ["test"],
            "entities": [],
            "thesis_links": [],
            "confidence": 0.7,
            "event_type": "note",
        }

    async def classify_three_dimensions(self, content: str) -> dict:
        return {
            "source_type": "first_hand",
            "nature_tags": ["claim"],
            "temporality": "permanent",
            "key_points": [],
            "stance": {},
        }

    async def parse_stance_llm(self, annotation: str) -> str:
        return "neutral"

    async def summarize(self, content: str, max_length: int = 200) -> str:
        return content[:max_length]

    async def chat(self, prompt: str) -> str:
        return "OK"


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _build_test_app(storage: FakeStorage, embedding: FakeEmbedding, llm: FakeLLM) -> FastAPI:
    """Create a bare FastAPI app wired with fake adapters (no lifespan)."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    workspace = "default"
    app.state.config = {"workspace": workspace}
    app.state.storage = storage
    app.state.embedding = embedding
    app.state.llm = llm
    app.state.file_store = None
    app.state.workspace = workspace
    app.state.ingest = IngestUseCase(storage, embedding, llm, workspace)
    app.state.search = SearchUseCase(storage, embedding, workspace)
    app.state.analyze = AnalyzeUseCase(storage, workspace)

    return app


@pytest.fixture()
def fake_storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture()
def fake_embedding() -> FakeEmbedding:
    return FakeEmbedding()


@pytest.fixture()
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture()
def client(fake_storage, fake_embedding, fake_llm) -> TestClient:
    app = _build_test_app(fake_storage, fake_embedding, fake_llm)
    return TestClient(app, raise_server_exceptions=True)
