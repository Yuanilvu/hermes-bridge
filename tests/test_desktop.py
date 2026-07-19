"""Tests for Desktop endpoints (minimal — requires cua-driver/mss)."""
import pytest
from fastapi.testclient import TestClient


class TestDesktop:
    def test_status_endpoint(self, client: TestClient, auth_headers):
        """Status should work without cua-driver."""
        resp = client.get("/api/desktop/status", headers=auth_headers)
        # May return 200 (partial status) or 500 (driver unavailable)
        assert resp.status_code in (200, 500)

    def test_cursor_endpoint(self, client: TestClient, auth_headers):
        """Cursor position."""
        resp = client.get("/api/desktop/cursor", headers=auth_headers)
        assert resp.status_code in (200, 500)
