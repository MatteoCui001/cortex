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
    KnowledgeEvent,
    EventType,
    SearchResult,
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
