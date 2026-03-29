"""
Integration tests for the Cortex REST API.

Uses TestClient with fake adapters — no real database or LLM required.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from cortex.domain.entities import EventType, KnowledgeEvent
from datetime import datetime, timezone

from tests.conftest import make_event as _make_event


# ------------------------------------------------------------------
# Happy-path tests
# ------------------------------------------------------------------

def test_stats_returns_valid_structure(client):
    """GET /api/v1/stats returns a dict with event count fields."""
    response = client.get("/api/v1/stats")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "events" in data
    assert "type_distribution" in data


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
    from cortex.domain.entities import KnowledgeEvent, EventType
    from datetime import datetime, timezone

    dummy_event = _make_event(title="Fetched Article", source="link")

    class FakeLinkUseCase:
        def __init__(self, *args, **kwargs):
            pass

        async def import_link(self, url, user_annotation=None):
            return dummy_event

    import cortex.api.routes as routes_module
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


# ------------------------------------------------------------------
# Phase 3.6: Signal API tests
# ------------------------------------------------------------------

class TestSignalAPI:

    def test_get_signals_returns_empty_list(self, client):
        response = client.get("/api/v1/signals")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_signals_returns_persisted(self, client, fake_storage):
        from cortex.domain.entities import ContradictionResult
        sig = ContradictionResult(
            new_event_id="evt-1", existing_event_id="evt-2",
            signal_type="contradiction", topic="rates",
            priority_score=0.8, workspace_id="default",
        )
        import asyncio
        asyncio.run(fake_storage.upsert_signal(sig))
        response = client.get("/api/v1/signals")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["signal_type"] == "contradiction"

    def test_get_signals_filtered_by_event_id(self, client, fake_storage):
        from cortex.domain.entities import ContradictionResult
        import asyncio
        sig1 = ContradictionResult(
            new_event_id="evt-1", existing_event_id="evt-x",
            signal_type="answer", workspace_id="default",
        )
        sig2 = ContradictionResult(
            new_event_id="evt-2", existing_event_id="evt-x",
            signal_type="bridge", workspace_id="default",
        )
        asyncio.run(fake_storage.upsert_signal(sig1))
        asyncio.run(fake_storage.upsert_signal(sig2))
        response = client.get("/api/v1/signals?event_id=evt-1")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_submit_feedback_returns_201(self, client, fake_storage):
        from cortex.domain.entities import ContradictionResult
        import asyncio
        sig = ContradictionResult(
            new_event_id="e1", existing_event_id="e2",
            signal_type="contradiction", topic="AI",
            workspace_id="default",
        )
        asyncio.run(fake_storage.upsert_signal(sig))
        response = client.post(
            f"/api/v1/signals/{sig.id}/feedback",
            json={"verdict": "useful"},
        )
        assert response.status_code == 201
        assert response.json()["verdict"] == "useful"

    def test_submit_feedback_rejects_invalid_verdict(self, client):
        response = client.post(
            "/api/v1/signals/fake-id/feedback",
            json={"verdict": "maybe"},
        )
        assert response.status_code == 422

    def test_thesis_feedback_stats_returns_list(self, client):
        response = client.get("/api/v1/signals/thesis-feedback")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


# ------------------------------------------------------------------
# Phase 4: Notification API tests
# ------------------------------------------------------------------

class TestNotificationAPI:

    def test_get_notifications_returns_empty_list(self, client):
        response = client.get("/api/v1/notifications")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_notifications_returns_stored(self, client, fake_storage):
        from cortex.domain.entities import Notification
        import asyncio
        n = Notification(title="Test", body="Body", source_kind="signal")
        asyncio.run(fake_storage.insert_notification(n))
        response = client.get("/api/v1/notifications")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Test"

    def test_get_notifications_filter_by_status(self, client, fake_storage):
        from cortex.domain.entities import Notification, NotificationStatus
        import asyncio
        n1 = Notification(title="A", body="a", source_kind="signal")
        n2 = Notification(title="B", body="b", source_kind="signal",
                          status=NotificationStatus.DELIVERED)
        asyncio.run(fake_storage.insert_notification(n1))
        asyncio.run(fake_storage.insert_notification(n2))
        response = client.get("/api/v1/notifications?status=pending")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "pending"

    def test_mark_notification_read(self, client, fake_storage):
        from cortex.domain.entities import Notification, NotificationStatus
        import asyncio
        n = Notification(title="T", body="B", source_kind="signal",
                         status=NotificationStatus.DELIVERED)
        asyncio.run(fake_storage.insert_notification(n))
        response = client.post(f"/api/v1/notifications/{n.id}/read")
        assert response.status_code == 200
        assert response.json()["status"] == "read"

    def test_mark_notification_acked(self, client, fake_storage):
        from cortex.domain.entities import Notification
        import asyncio
        n = Notification(title="T", body="B", source_kind="signal")
        asyncio.run(fake_storage.insert_notification(n))
        response = client.post(f"/api/v1/notifications/{n.id}/ack")
        assert response.status_code == 200
        assert response.json()["status"] == "acked"

    def test_mark_notification_dismissed(self, client, fake_storage):
        from cortex.domain.entities import Notification
        import asyncio
        n = Notification(title="T", body="B", source_kind="signal")
        asyncio.run(fake_storage.insert_notification(n))
        response = client.post(f"/api/v1/notifications/{n.id}/dismiss")
        assert response.status_code == 200
        assert response.json()["status"] == "dismissed"

    def test_mark_notification_delivered(self, client, fake_storage):
        from cortex.domain.entities import Notification
        import asyncio
        n = Notification(title="T", body="B", source_kind="signal")
        asyncio.run(fake_storage.insert_notification(n))
        response = client.post(f"/api/v1/notifications/{n.id}/deliver")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "delivered"
        assert data["delivered_at"] is not None
        assert data.get("acted_at") is None

    def test_deliver_already_delivered_returns_409(self, client, fake_storage):
        from cortex.domain.entities import Notification, NotificationStatus
        import asyncio
        n = Notification(title="T", body="B", source_kind="signal",
                         status=NotificationStatus.DELIVERED)
        asyncio.run(fake_storage.insert_notification(n))
        response = client.post(f"/api/v1/notifications/{n.id}/deliver")
        assert response.status_code == 409

    def test_deliver_acked_returns_409(self, client, fake_storage):
        from cortex.domain.entities import Notification, NotificationStatus
        import asyncio
        n = Notification(title="T", body="B", source_kind="signal",
                         status=NotificationStatus.ACKED)
        asyncio.run(fake_storage.insert_notification(n))
        response = client.post(f"/api/v1/notifications/{n.id}/deliver")
        assert response.status_code == 409

    def test_deliver_nonexistent_returns_404(self, client):
        response = client.post("/api/v1/notifications/nonexistent/deliver")
        assert response.status_code == 404

    def test_invalid_transition_returns_409(self, client, fake_storage):
        from cortex.domain.entities import Notification, NotificationStatus
        import asyncio
        n = Notification(title="T", body="B", source_kind="signal",
                         status=NotificationStatus.ACKED)
        asyncio.run(fake_storage.insert_notification(n))
        response = client.post(f"/api/v1/notifications/{n.id}/read")
        assert response.status_code == 409

    def test_unknown_notification_returns_404(self, client):
        response = client.post("/api/v1/notifications/nonexistent/read")
        assert response.status_code == 404


# ------------------------------------------------------------------
# Phase 5: Event Editing + Bulk Notifications
# ------------------------------------------------------------------

class TestEventPatch:

    def test_patch_event_tags(self, client, fake_storage):
        event = _make_event()
        fake_storage._events[event.id] = event
        response = client.patch(f"/api/v1/events/{event.id}", json={"tags": ["ai", "vc"]})
        assert response.status_code == 200
        data = response.json()
        assert data["tags"] == ["ai", "vc"]

    def test_patch_event_title(self, client, fake_storage):
        event = _make_event()
        fake_storage._events[event.id] = event
        response = client.patch(f"/api/v1/events/{event.id}", json={"title": "New Title"})
        assert response.status_code == 200
        assert response.json()["title"] == "New Title"

    def test_patch_event_thesis_links(self, client, fake_storage):
        event = _make_event()
        fake_storage._events[event.id] = event
        response = client.patch(f"/api/v1/events/{event.id}", json={"thesis_links": ["AI Agents"]})
        assert response.status_code == 200
        assert response.json()["thesis_links"] == ["AI Agents"]

    def test_patch_event_not_found(self, client):
        response = client.patch("/api/v1/events/nonexistent", json={"title": "X"})
        assert response.status_code == 404

    def test_patch_event_partial(self, client, fake_storage):
        event = _make_event()
        event.tags = ["original"]
        event.title = "Original"
        fake_storage._events[event.id] = event
        response = client.patch(f"/api/v1/events/{event.id}", json={"tags": ["new"]})
        assert response.status_code == 200
        data = response.json()
        assert data["tags"] == ["new"]
        assert data["title"] == "Original"


class TestBulkNotification:

    def test_bulk_read_by_status(self, client, fake_storage):
        from cortex.domain.entities import Notification
        import asyncio
        for i in range(3):
            n = Notification(title=f"N{i}", body="b", source_kind="signal")
            asyncio.run(fake_storage.insert_notification(n))
        response = client.post("/api/v1/notifications/bulk-action",
                               json={"action": "ack", "status_filter": "pending"})
        assert response.status_code == 200
        data = response.json()
        assert data["updated"] == 3
        assert data["failed"] == 0

    def test_bulk_dismiss_by_ids(self, client, fake_storage):
        from cortex.domain.entities import Notification
        import asyncio
        n1 = Notification(title="A", body="a", source_kind="signal")
        n2 = Notification(title="B", body="b", source_kind="signal")
        asyncio.run(fake_storage.insert_notification(n1))
        asyncio.run(fake_storage.insert_notification(n2))
        response = client.post("/api/v1/notifications/bulk-action",
                               json={"action": "dismiss", "ids": [n1.id]})
        assert response.status_code == 200
        data = response.json()
        assert data["updated"] == 1

    def test_bulk_invalid_action_rejected(self, client):
        response = client.post("/api/v1/notifications/bulk-action",
                               json={"action": "invalid"})
        assert response.status_code == 422


# ------------------------------------------------------------------
# Phase 5: Health / Ready
# ------------------------------------------------------------------

class TestHealthReady:

    def test_health_returns_ok(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_ready_with_storage(self, client):
        response = client.get("/api/v1/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["storage"] is True


# ------------------------------------------------------------------
# Previously-untested API routes
# ------------------------------------------------------------------

class TestCreateEvent:
    """POST /events (simple create, not /events/ingest)."""

    def test_create_event_returns_201(self, client):
        response = client.post(
            "/api/v1/events",
            json={
                "title": "Direct Create",
                "content": "Created via POST /events.",
                "source": "api",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Direct Create"
        assert "id" in data

    def test_create_event_requires_title(self, client):
        response = client.post(
            "/api/v1/events",
            json={"content": "Missing title"},
        )
        assert response.status_code == 422


class TestListEvents:
    """GET /events (list endpoint)."""

    def test_list_events_empty(self, client):
        response = client.get("/api/v1/events")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_events_returns_stored(self, client, fake_storage):
        e1 = _make_event(title="Event A")
        e2 = _make_event(title="Event B")
        fake_storage._events[e1.id] = e1
        fake_storage._events[e2.id] = e2

        response = client.get("/api/v1/events?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        titles = {d["title"] for d in data}
        assert titles == {"Event A", "Event B"}

    def test_list_events_with_days_filter(self, client, fake_storage):
        from datetime import timedelta
        old = _make_event(
            title="Old",
            created_at=datetime.now(timezone.utc) - timedelta(days=60),
        )
        recent = _make_event(title="Recent")
        fake_storage._events[old.id] = old
        fake_storage._events[recent.id] = recent

        response = client.get("/api/v1/events?days=7")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Recent"


class TestThesisCoverage:
    """GET /thesis (coverage report)."""

    def test_thesis_coverage_empty(self, client):
        response = client.get("/api/v1/thesis")
        assert response.status_code == 200
        assert response.json() == []

    def test_thesis_coverage_returns_structure(self, client, fake_storage):
        e = _make_event(thesis_links=["AI Agent Infra"], confidence=0.9)
        fake_storage._events[e.id] = e

        response = client.get("/api/v1/thesis")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        thesis = data[0]
        assert "thesis" in thesis
        assert "event_count" in thesis
        assert "avg_confidence" in thesis
        assert "trend_direction" in thesis


class TestStaleEvents:
    """GET /stale."""

    def test_stale_events_empty(self, client):
        response = client.get("/api/v1/stale")
        assert response.status_code == 200
        assert response.json() == []

    def test_stale_events_returns_old_events(self, client, fake_storage):
        from datetime import timedelta
        stale = _make_event(
            title="Stale Event",
            updated_at=datetime.now(timezone.utc) - timedelta(days=60),
        )
        fake_storage._events[stale.id] = stale

        response = client.get("/api/v1/stale?days=30")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["title"] == "Stale Event"


class TestEntityGraph:
    """GET /entity/{id}/graph."""

    def test_entity_graph_returns_list(self, client, fake_storage):
        e = _make_event()
        fake_storage._events[e.id] = e

        response = client.get(f"/api/v1/entity/{e.id}/graph")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestRelatedSearch:
    """GET /search/related/{event_id}."""

    def test_related_empty(self, client, fake_storage):
        e = _make_event()
        fake_storage._events[e.id] = e

        response = client.get(f"/api/v1/search/related/{e.id}")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestEntitySearch:
    """GET /entities/search."""

    def test_entity_search_returns_list(self, client):
        response = client.get("/api/v1/entities/search?q=test")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestEntityEvents:
    """GET /entities/{entity_id}/events."""

    def test_entity_events_returns_list(self, client):
        response = client.get(f"/api/v1/entities/{uuid.uuid4()}/events")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestBearerAuth:
    """Tests for Bearer token authentication middleware."""

    def test_health_is_public(self, authed_client):
        client, _token = authed_client
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_ready_is_public(self, authed_client):
        client, _token = authed_client
        response = client.get("/api/v1/ready")
        assert response.status_code == 200

    def test_api_rejects_no_token(self, authed_client):
        client, _token = authed_client
        response = client.get("/api/v1/stats")
        assert response.status_code == 401
        assert response.json()["detail"] == "Unauthorized"

    def test_api_rejects_wrong_token(self, authed_client):
        client, _token = authed_client
        response = client.get(
            "/api/v1/stats",
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert response.status_code == 401

    def test_api_accepts_correct_token(self, authed_client):
        client, token = authed_client
        response = client.get(
            "/api/v1/stats",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    def test_post_endpoint_requires_auth(self, authed_client):
        client, _token = authed_client
        response = client.post(
            "/api/v1/search",
            json={"query": "test"},
        )
        assert response.status_code == 401

    def test_post_endpoint_with_auth(self, authed_client):
        client, token = authed_client
        response = client.post(
            "/api/v1/search",
            json={"query": "test"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200


class TestSettings:
    """GET /settings and PUT /settings/llm."""

    def test_get_settings_returns_structure(self, client):
        response = client.get("/api/v1/settings")
        assert response.status_code == 200
        data = response.json()
        assert "llm" in data
        assert "workspace" in data
        assert "embedding_model" in data
        assert isinstance(data["llm"]["configured"], bool)

    def test_get_settings_llm_status(self, client):
        """FakeLLM is configured in test fixtures, so configured=True."""
        response = client.get("/api/v1/settings")
        data = response.json()
        # Test fixture provides a FakeLLM, so LLM is configured
        assert data["llm"]["configured"] is True

    def test_update_llm_with_key(self, client):
        response = client.put(
            "/api/v1/settings/llm",
            json={"api_key": "sk-test-key", "model": "test-model", "base_url": "https://test.api/v1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "updated"
        assert data["llm_configured"] is True
        assert data["model"] == "test-model"

        # Verify settings reflect the change
        settings = client.get("/api/v1/settings").json()
        assert settings["llm"]["configured"] is True
        assert settings["llm"]["model"] == "test-model"

    def test_clear_llm(self, client):
        # First configure
        client.put("/api/v1/settings/llm", json={"api_key": "sk-test"})
        # Then clear
        response = client.put("/api/v1/settings/llm", json={"api_key": ""})
        assert response.status_code == 200
        assert response.json()["status"] == "cleared"

        settings = client.get("/api/v1/settings").json()
        assert settings["llm"]["configured"] is False
