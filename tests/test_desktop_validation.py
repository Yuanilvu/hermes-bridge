"""Tests for desktop router — input validation & endpoint existence."""
from fastapi.testclient import TestClient


class TestDesktopValidation:
    """Desktop endpoints should validate input properly."""

    def test_click_missing_coordinates(self, client: TestClient, auth_headers):
        """Click without x/y should fail validation."""
        resp = client.post("/api/desktop/click", json={}, headers=auth_headers)
        assert resp.status_code == 422

    def test_click_negative_coordinates(self, client: TestClient, auth_headers):
        """Click with negative coords should still pass (cua-driver handles bounds)."""
        resp = client.post(
            "/api/desktop/click",
            json={"x": -100, "y": -100, "button": "left"},
            headers=auth_headers,
        )
        # 200 = cua-driver handles it, 500/502 = env dependent
        assert resp.status_code in (200, 500, 502)

    def test_scroll_invalid_direction(self, client: TestClient, auth_headers):
        """Scroll with invalid direction should pass validation (str field)."""
        resp = client.post(
            "/api/desktop/scroll",
            json={"direction": "invalid", "amount": 3},
            headers=auth_headers,
        )
        assert resp.status_code in (200, 500, 502)

    def test_key_empty_sequence(self, client: TestClient, auth_headers):
        """Key press with empty input should fail."""
        resp = client.post(
            "/api/desktop/key",
            json={"keys": ""},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_type_empty_text(self, client: TestClient, auth_headers):
        """Type endpoint with empty text should still work."""
        resp = client.post(
            "/api/desktop/type",
            json={"text": ""},
            headers=auth_headers,
        )
        assert resp.status_code in (200, 500, 502)

    def test_screenshot_requires_auth(self, client: TestClient, unauth_headers):
        resp = client.get("/api/desktop/screenshot", headers=unauth_headers)
        assert resp.status_code == 401

    def test_screenshot_no_header(self, client: TestClient):
        """Missing X-Bridge-Key entirely → 422."""
        resp = client.get("/api/desktop/screenshot")
        assert resp.status_code == 422

    def test_info_endpoints_exist(self, client: TestClient, auth_headers):
        """Info endpoints should return valid responses."""
        endpoints = [
            ("GET", "/api/desktop/status"),
            ("GET", "/api/desktop/screen-size"),
            ("GET", "/api/desktop/cursor"),
            ("GET", "/api/desktop/windows"),
            ("GET", "/api/desktop/tree"),
            ("GET", "/api/desktop/apps"),
            ("GET", "/api/desktop/daemon/status"),
        ]
        for method, path in endpoints:
            if method == "GET":
                resp = client.get(path, headers=auth_headers)
            else:
                resp = client.post(path, headers=auth_headers)
            # 200 = normal, 502/503 = cua-driver not available in test env
            assert resp.status_code in (200, 500, 502, 503), (
                f"{method} {path} returned {resp.status_code}"
            )
