"""Tests for /theses API endpoints."""
from __future__ import annotations

import pytest


class TestThesisAPI:
    """CRUD tests for /api/v1/theses endpoints."""

    def test_list_empty(self, client):
        r = client.get("/api/v1/theses")
        assert r.status_code == 200
        assert r.json() == []

    def test_create_and_get(self, client):
        r = client.post("/api/v1/theses", json={
            "text": "Solar will dominate",
            "stance": "bullish",
            "theme": "solar",
        })
        assert r.status_code == 201
        body = r.json()
        assert body["text"] == "Solar will dominate"
        assert body["stance"] == "bullish"
        assert body["theme"] == "solar"
        assert body["confirmed"] is True
        assert body["confidence"] == 0.5
        assert body["status"] == "active"

        # Get by id
        r2 = client.get(f"/api/v1/theses/{body['id']}")
        assert r2.status_code == 200
        assert r2.json()["id"] == body["id"]

    def test_create_defaults(self, client):
        r = client.post("/api/v1/theses", json={"text": "Just a thesis"})
        assert r.status_code == 201
        body = r.json()
        assert body["stance"] == "neutral"
        assert body["theme"] is None
        assert body["created_by"] == "manual"

    def test_get_not_found(self, client):
        r = client.get("/api/v1/theses/nonexistent-id")
        assert r.status_code == 404

    def test_patch(self, client):
        r = client.post("/api/v1/theses", json={"text": "Original"})
        tid = r.json()["id"]
        r2 = client.patch(f"/api/v1/theses/{tid}", json={"text": "Updated", "stance": "bearish"})
        assert r2.status_code == 200
        assert r2.json()["text"] == "Updated"
        assert r2.json()["stance"] == "bearish"

    def test_patch_not_found(self, client):
        r = client.patch("/api/v1/theses/nonexistent", json={"text": "X"})
        assert r.status_code == 404

    def test_patch_empty_body(self, client):
        r = client.post("/api/v1/theses", json={"text": "T"})
        tid = r.json()["id"]
        r2 = client.patch(f"/api/v1/theses/{tid}", json={})
        assert r2.status_code == 400

    def test_resolve(self, client):
        r = client.post("/api/v1/theses", json={"text": "To resolve"})
        tid = r.json()["id"]
        r2 = client.post(f"/api/v1/theses/{tid}/resolve")
        assert r2.status_code == 200
        assert r2.json()["status"] == "resolved"

    def test_invalidate(self, client):
        r = client.post("/api/v1/theses", json={"text": "To invalidate"})
        tid = r.json()["id"]
        r2 = client.post(f"/api/v1/theses/{tid}/invalidate")
        assert r2.status_code == 200
        assert r2.json()["status"] == "invalidated"

    def test_confirm(self, client):
        r = client.post("/api/v1/theses", json={"text": "Inferred", "created_by": "inferred"})
        tid = r.json()["id"]
        assert r.json()["confirmed"] is False
        r2 = client.post(f"/api/v1/theses/{tid}/confirm")
        assert r2.status_code == 200
        assert r2.json()["confirmed"] is True

    def test_delete(self, client):
        r = client.post("/api/v1/theses", json={"text": "To delete"})
        tid = r.json()["id"]
        r2 = client.delete(f"/api/v1/theses/{tid}")
        assert r2.status_code == 200
        r3 = client.get(f"/api/v1/theses/{tid}")
        assert r3.status_code == 404

    def test_delete_not_found(self, client):
        r = client.delete("/api/v1/theses/nonexistent")
        assert r.status_code == 404

    def test_list_filter_status(self, client):
        client.post("/api/v1/theses", json={"text": "Active"})
        r2 = client.post("/api/v1/theses", json={"text": "Will resolve"})
        client.post(f"/api/v1/theses/{r2.json()['id']}/resolve")
        active = client.get("/api/v1/theses?status=active").json()
        assert len(active) == 1
        assert active[0]["text"] == "Active"

    def test_evidence_empty(self, client):
        r = client.post("/api/v1/theses", json={"text": "T"})
        tid = r.json()["id"]
        r2 = client.get(f"/api/v1/theses/{tid}/evidence")
        assert r2.status_code == 200
        assert r2.json() == []
