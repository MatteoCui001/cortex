"""
Integration tests for the Cortex REST API.

Uses TestClient with fake adapters — no real database or LLM required.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from cortex.domain.entities import EventType, KnowledgeEvent

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_event(**kwargs) -> KnowledgeEvent:
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


# ------------------------------------------------------------------
# Happy-path tests
# ------------------------------------------------------------------


def test_stats_returns_valid_structure(client):
    """GET /api/v1/stats returns a dict with event count fields."""
    response = client.get("/api/v1/stats")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "total_events" in data


def test_search_text_returns_results(client, fake_storage):
    """POST /api/v1/search returns a list of search results."""
    event = _make_event()
    fake_storage._events[event.id] = event

    response = client.post(
        "/api/v1/search",
        json={"query": "test query", "mode": "fulltext", "limit": 5},
    )
    assert response.status_code == 200
    results = response.json()
    assert isinstance(results, list)
    assert len(results) >= 1
    first = results[0]
    assert "event" in first
    assert "score" in first
    assert "match_type" in first
    assert "id" in first["event"]
    assert "title" in first["event"]


def test_ingest_text_creates_event_returns_201(client):
    """POST /api/v1/events/ingest with text content returns 201 and the created event."""
    response = client.post(
        "/api/v1/events/ingest",
        json={
            "title": "My Note",
            "content": "This is some note content.",
            "source": "api",
            "raw_input_type": "text",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "My Note"
    assert "id" in data
    assert data["source"] == "api"


def test_ingest_url_creates_event_returns_201(client, fake_storage, monkeypatch):
    """POST /api/v1/events/ingest with a URL triggers the link pipeline and returns 201."""
    # Patch IngestLinkUseCase so we don't hit the network

    dummy_event = _make_event(title="Fetched Article", source="link")

    class FakeLinkUseCase:
        def __init__(self, *args, **kwargs):
            pass

        async def import_link(self, url, user_annotation=None):
            return dummy_event

    monkeypatch.setattr(
        "cortex.use_cases.ingest_link.IngestLinkUseCase",
        FakeLinkUseCase,
    )

    response = client.post(
        "/api/v1/events/ingest",
        json={
            "url": "https://example.com/article",
            "title": "Article from URL",
            "workspace_id": "default",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data


def test_get_event_by_id_returns_event(client, fake_storage):
    """GET /api/v1/events/{id} returns the event when it exists."""
    event = _make_event(title="Stored Event")
    fake_storage._events[event.id] = event

    response = client.get(f"/api/v1/events/{event.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == event.id
    assert data["title"] == "Stored Event"


def test_annotate_event_creates_annotation(client, fake_storage):
    """POST /api/v1/events/{id}/annotate creates and returns an annotation."""
    event = _make_event()
    fake_storage._events[event.id] = event

    response = client.post(
        f"/api/v1/events/{event.id}/annotate",
        json={"annotation": "This is very interesting.", "stance": "agree"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["target_id"] == event.id
    assert data["target_type"] == "event"
    assert data["annotation"] == "This is very interesting."
    assert data["stance"] == "agree"
    assert "id" in data


def test_get_annotations_for_event(client, fake_storage):
    """GET /api/v1/annotations/event/{id} returns a list of annotations."""
    event = _make_event()
    fake_storage._events[event.id] = event

    # Create an annotation first
    client.post(
        f"/api/v1/events/{event.id}/annotate",
        json={"annotation": "Interesting finding."},
    )

    response = client.get(f"/api/v1/annotations/event/{event.id}")
    assert response.status_code == 200
    annotations = response.json()
    assert isinstance(annotations, list)
    assert len(annotations) >= 1
    assert annotations[0]["target_id"] == event.id


def test_get_notifications_returns_list(client):
    """GET /api/v1/notifications returns a list (possibly empty)."""
    response = client.get("/api/v1/notifications")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_digest_returns_structure(client):
    """GET /api/v1/digest returns a dict with expected digest keys."""
    response = client.get("/api/v1/digest")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "thesis_activity" in data
    assert "high_confidence" in data
    assert "stale_theses" in data
    assert "entity_momentum" in data


def test_thesis_evidence_returns_list(client, fake_storage):
    """GET /api/v1/thesis/{name} returns a list of events for that thesis."""
    thesis_name = "AI dominance"
    event = _make_event(thesis_links=[thesis_name])
    fake_storage._events[event.id] = event

    response = client.get(f"/api/v1/thesis/{thesis_name}")
    assert response.status_code == 200
    results = response.json()
    assert isinstance(results, list)
    assert any(r["id"] == event.id for r in results)


# ------------------------------------------------------------------
# Error scenarios
# ------------------------------------------------------------------


def test_ingest_empty_body_still_creates_event(client):
    """POST /api/v1/events/ingest with empty body — all fields optional, text branch runs."""
    response = client.post("/api/v1/events/ingest", json={})
    # IngestRequest has all optional fields: empty body goes through text branch
    # with empty content. This should succeed (not crash).
    assert response.status_code == 201
    data = response.json()
    assert "id" in data


def test_get_nonexistent_event_returns_404(client):
    """GET /api/v1/events/{id} returns 404 when the event does not exist."""
    missing_id = str(uuid.uuid4())
    response = client.get(f"/api/v1/events/{missing_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Event not found"


def test_ingest_invalid_url_returns_500(fake_storage, fake_embedding, fake_llm, monkeypatch):
    """POST /api/v1/events/ingest with invalid URL — use case raises, API returns 500."""

    class FakeLinkUseCaseRaises:
        def __init__(self, *args, **kwargs):
            pass

        async def import_link(self, url, user_annotation=None):
            raise ValueError(f"Cannot fetch URL: {url}")

    import cortex.use_cases.ingest_link as ingest_link_module

    monkeypatch.setattr(ingest_link_module, "IngestLinkUseCase", FakeLinkUseCaseRaises)

    from tests.conftest import _build_test_app

    app = _build_test_app(fake_storage, fake_embedding, fake_llm)
    error_client = TestClient(app, raise_server_exceptions=False)

    response = error_client.post(
        "/api/v1/events/ingest",
        json={"url": "not-a-real-url"},
    )
    # Unhandled ValueError in route → 500 Internal Server Error
    assert response.status_code == 500
