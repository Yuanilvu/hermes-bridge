"""Tests for Health endpoints."""
from fastapi.testclient import TestClient
from hermes_bridge import VERSION


class TestHealth:
    def test_root_returns_version(self, client: TestClient):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == VERSION
        assert data["name"] == "Hermes Bridge"

    def test_health_endpoint(self, client: TestClient):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["bridge_version"] == VERSION
        assert data["uptime_seconds"] >= 0

    def test_api_root_lists_endpoints(self, client: TestClient, auth_headers):
        resp = client.get("/api", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == VERSION
        assert "endpoints" in data
        assert "/api/health" in data["endpoints"]["health"]

    def test_api_root_requires_auth(self, client: TestClient, unauth_headers):
        resp = client.get("/api", headers=unauth_headers)
        assert resp.status_code == 401
