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
    EvidenceImpact,
    KnowledgeEvent,
    EventType,
    Notification,
    NotificationStatus,
    SearchResult,
    SignalFeedback,
    Thesis,
    ThesisCoverage,
    ThesisEvidence,
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
        self._entities: dict[str, object] = {}
        self._annotations: list[Annotation] = []
        self._signals: list[ContradictionResult] = []
        self._signal_feedback: list[SignalFeedback] = []
        self._notifications: dict[str, Notification] = {}
        self._theses: dict[str, Thesis] = {}
        self._thesis_evidence: list[ThesisEvidence] = []

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
        self._entities[entity.id] = entity
        return entity.id

    async def find_entity_by_name(self, workspace_id, entity_type, name):
        etype = entity_type.value if hasattr(entity_type, "value") else entity_type
        for e in self._entities.values():
            et = e.type.value if hasattr(e.type, "value") else e.type
            if e.workspace_id == workspace_id and et == etype and e.name == name:
                return e
        return None

    async def append_entity_alias(self, entity_id, alias):
        e = self._entities.get(entity_id)
        if e and alias not in e.aliases:
            e.aliases.append(alias)

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
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return [
            e for e in self._events.values()
            if e.workspace_id == workspace_id
            and e.updated_at
            and e.updated_at < cutoff
        ]

    async def thesis_coverage(self, workspace_id="default") -> list[ThesisCoverage]:
        thesis_map: dict[str, list] = {}
        for e in self._events.values():
            if e.workspace_id != workspace_id:
                continue
            for t in (e.thesis_links or []):
                thesis_map.setdefault(t, []).append(e)
        result = []
        for thesis, events in thesis_map.items():
            avg_conf = sum(e.confidence for e in events) / len(events) if events else 0
            latest = max((e.updated_at for e in events if e.updated_at), default=None)
            days_since = 0
            if latest:
                days_since = (datetime.now(timezone.utc) - latest).days
            result.append(ThesisCoverage(
                thesis_name=thesis,
                event_count=len(events),
                avg_confidence=avg_conf,
                type_distribution={},
                latest_update=latest,
                days_since_update=days_since,
            ))
        return result

    async def thesis_trend(self, workspace_id="default", window_days=14) -> dict:
        return {}

    async def daily_events(self, target_date, workspace_id="default") -> list[KnowledgeEvent]:
        return []

    async def stats(self, workspace_id="default") -> dict:
        type_dist: dict[str, int] = {}
        for e in self._events.values():
            type_dist[e.type] = type_dist.get(e.type, 0) + 1
        return {
            "events": len(self._events),
            "entities": len(self._entities),
            "relations": 0,
            "type_distribution": type_dist,
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

    async def list_events(self, workspace_id="default", *, limit=50, offset=0, days=None, sort="recent"):
        events = [e for e in self._events.values() if e.workspace_id == workspace_id]
        if days:
            from datetime import timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            events = [e for e in events if e.created_at and e.created_at >= cutoff]
        if sort == "relevance":
            events.sort(key=lambda e: (e.relevance or 0, e.created_at or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
        else:
            events.sort(key=lambda e: e.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return events[offset:offset + limit]

    async def update_event_fields(
        self,
        event_id: str,
        workspace_id: str,
        *,
        tags=None,
        thesis_links=None,
        title=None,
    ) -> bool:
        ev = self._events.get(event_id)
        if not ev or ev.workspace_id != workspace_id:
            return False
        if tags is not None:
            ev.tags = tags
        if thesis_links is not None:
            ev.thesis_links = thesis_links
        if title is not None:
            ev.title = title
        return True

    async def update_event_tags(self, event_id, tags):
        pass

    async def get_all_entities(self, workspace_id="default", *, limit=0, order_by="name") -> list[dict]:
        result = [
            {"id": e.id, "type": e.type.value if hasattr(e.type, "value") else e.type,
             "name": e.name, "mention_count": 0}
            for e in self._entities.values()
            if e.workspace_id == workspace_id
        ]
        if order_by == "mention_count":
            result.sort(key=lambda x: x["mention_count"], reverse=True)
        else:
            result.sort(key=lambda x: x["name"])
        if limit > 0:
            result = result[:limit]
        return result

    async def merge_entities(self, keep_id, remove_id):
        pass

    async def semantic_search_entities(self, embedding, *, workspace_id="default",
                                       entity_types=None, limit=20) -> list[dict]:
        return []

    async def get_events_for_entity(self, entity_id, workspace_id="default", limit=50) -> list[KnowledgeEvent]:
        return []

    async def get_thesis_entity_graph(self, workspace_id="default", entity_limit=50, per_thesis_limit=5) -> dict:
        return {"entities": [], "relations": []}

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

    async def update_event_user_stance(self, event_id: str, user_stance: str):
        e = self._events.get(event_id)
        if e:
            e.user_stance = user_stance

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


    # --- Phase 6: Thesis CRUD + evidence ---

    def _compute_confidence_for(self, thesis_id: str) -> float:
        score = 0.5
        for e in self._thesis_evidence:
            if e.thesis_id != thesis_id:
                continue
            if e.impact == EvidenceImpact.SUPPORTS:
                score += e.confidence_delta * 0.1
            elif e.impact == EvidenceImpact.CONTRADICTS:
                score -= e.confidence_delta * 0.1
        return max(0.0, min(1.0, score))

    async def create_thesis(self, thesis: Thesis) -> str:
        self._theses[thesis.id] = thesis
        return thesis.id

    async def get_thesis(self, thesis_id, workspace_id="default"):
        t = self._theses.get(thesis_id)
        if t and t.workspace_id == workspace_id:
            t.confidence = self._compute_confidence_for(thesis_id)
            return t
        return None

    async def list_theses(self, workspace_id="default", *, status=None, theme=None, confirmed_only=False):
        results = [t for t in self._theses.values() if t.workspace_id == workspace_id]
        if status:
            st = status.value if hasattr(status, "value") else status
            results = [t for t in results if (t.status.value if hasattr(t.status, "value") else t.status) == st]
        if theme:
            results = [t for t in results if t.theme == theme]
        if confirmed_only:
            results = [t for t in results if t.confirmed]
        for t in results:
            t.confidence = self._compute_confidence_for(t.id)
        return results

    async def update_thesis(self, thesis_id, workspace_id, *, text=None, stance=None,
                            status=None, expires_at=None, theme=None, confirmed=None):
        t = self._theses.get(thesis_id)
        if not t or t.workspace_id != workspace_id:
            return False
        if text is not None:
            t.text = text
        if stance is not None:
            from cortex.domain.entities import ThesisStance
            t.stance = ThesisStance(stance) if isinstance(stance, str) else stance
        if status is not None:
            from cortex.domain.entities import ThesisStatus
            t.status = ThesisStatus(status) if isinstance(status, str) else status
        if expires_at is not None:
            t.expires_at = expires_at
        if theme is not None:
            t.theme = theme
        if confirmed is not None:
            t.confirmed = confirmed
        return True

    async def delete_thesis(self, thesis_id, workspace_id):
        t = self._theses.get(thesis_id)
        if t and t.workspace_id == workspace_id:
            del self._theses[thesis_id]
            self._thesis_evidence = [e for e in self._thesis_evidence if e.thesis_id != thesis_id]
            return True
        return False

    async def record_evidence(self, evidence: ThesisEvidence) -> str:
        self._thesis_evidence = [
            e for e in self._thesis_evidence
            if not (e.thesis_id == evidence.thesis_id and e.event_id == evidence.event_id)
        ]
        self._thesis_evidence.append(evidence)
        return evidence.id

    async def get_evidence_for_thesis(self, thesis_id, workspace_id="default", limit=50):
        results = [e for e in self._thesis_evidence if e.thesis_id == thesis_id]
        results.sort(key=lambda e: e.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return results[:limit]

    async def get_evidence_for_event(self, event_id, workspace_id="default"):
        return [e for e in self._thesis_evidence if e.event_id == event_id]


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
            "skip": False,
            "summary": content[:100].replace("\n", " "),
            "tags": ["test"],
            "entities": [],
            "thesis_links": [],
            "confidence": 0.7,
            "event_type": "note",
            "relevance": 0.5,
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

    async def assess_thesis_impact(
        self, event_content: str, event_summary: str, thesis_text: str, thesis_stance: str,
    ) -> dict:
        return {"impact": "neutral", "confidence_delta": 0.0, "rationale": "stub"}

    async def generate_theses(self, theme: str, events_text: str) -> list[dict]:
        return [{"text": f"Test thesis for {theme}", "stance": "bullish", "rationale": "stub"}]


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


def _build_authed_test_app(
    storage: FakeStorage, embedding: FakeEmbedding, llm: FakeLLM, token: str,
) -> FastAPI:
    """Create a test app with Bearer auth middleware enabled."""
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request as StarletteRequest
    from starlette.responses import JSONResponse
    import hmac

    app = _build_test_app(storage, embedding, llm)

    _PUBLIC_PATHS = frozenset({"/api/v1/health", "/api/v1/ready"})

    class _TestAuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: StarletteRequest, call_next):
            if request.url.path in _PUBLIC_PATHS:
                return await call_next(request)
            if not request.url.path.startswith("/api/"):
                return await call_next(request)
            auth = request.headers.get("authorization", "")
            if hmac.compare_digest(auth, f"Bearer {token}"):
                return await call_next(request)
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)

    app.add_middleware(_TestAuthMiddleware)
    return app


@pytest.fixture()
def authed_client(fake_storage, fake_embedding, fake_llm) -> tuple:
    """Returns (client, token) where client has auth middleware enabled."""
    token = "test-secret-token-12345"
    app = _build_authed_test_app(fake_storage, fake_embedding, fake_llm, token)
    return TestClient(app, raise_server_exceptions=True), token


# ------------------------------------------------------------------
# Shared test factories
# ------------------------------------------------------------------

def make_event(**kwargs) -> KnowledgeEvent:
    """Create a KnowledgeEvent with sensible defaults; override any field via kwargs."""
    defaults = dict(
        id=str(uuid.uuid4()),
        workspace_id="default",
        type=EventType.NOTE,
        title="Sample Event",
        content="Sample content",
        summary="Sample summary",
        tags=["sample"],
        thesis_links=[],
        confidence=0.75,
        source="api",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return KnowledgeEvent(**defaults)


def make_signal(**kwargs) -> ContradictionResult:
    """Create a ContradictionResult with sensible defaults; override any field via kwargs."""
    defaults = dict(
        id=str(uuid.uuid4()),
        workspace_id="default",
        new_event_id=str(uuid.uuid4()),
        existing_event_id=str(uuid.uuid4()),
        signal_type="contradiction",
        confidence=0.85,
        explanation="Test signal",
        topic="test-topic",
        priority_score=0.7,
        value_score=0.6,
    )
    defaults.update(kwargs)
    return ContradictionResult(**defaults)


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
