"""Tests that all protected endpoints reject unauthorized requests."""
from fastapi.testclient import TestClient


PROTECTED_ENDPOINTS = [
    ("GET", "/api"),
    ("GET", "/api/providers"),
    ("POST", "/api/providers"),
    ("GET", "/api/providers/some-id"),
    ("PATCH", "/api/providers/some-id"),
    ("DELETE", "/api/providers/some-id"),
    ("GET", "/api/providers/health"),
    ("GET", "/api/vault"),
    ("GET", "/api/vault/files/structure"),
    ("GET", "/api/vault/files/search?q=test"),
    ("GET", "/api/vault/files/read?file=test.md"),
    ("POST", "/api/vault/files/write"),
    ("GET", "/api/desktop/status"),
    ("GET", "/api/desktop/cursor"),
    ("POST", "/api/desktop/click"),
    ("POST", "/api/desktop/scroll"),
    ("POST", "/api/desktop/key"),
    ("GET", "/api/desktop/apps"),
    ("GET", "/api/desktop/daemon/status"),
    ("GET", "/api/desktop/driver-config"),
    ("GET", "/api/desktop/health-report"),
    ("GET", "/api/proxy/allowed-domains"),
    ("GET", "/api/proxy/http"),
]


class TestAuth:
    """All protected endpoints should return 401 without valid API key."""

    def test_all_protected_endpoints_require_auth(self, client: TestClient, unauth_headers):
        for method, path in PROTECTED_ENDPOINTS:
            # Build a dict of params if needed
            if "?" in path:
                base, qs = path.split("?", 1)
                params = dict(p.split("=") for p in qs.split("&"))
                path = base
            else:
                params = {}

            if method == "GET":
                resp = client.get(path, params=params, headers=unauth_headers)
            elif method == "POST":
                resp = client.post(path, json={}, params=params, headers=unauth_headers)
            elif method == "PATCH":
                resp = client.patch(path, json={}, params=params, headers=unauth_headers)
            elif method == "DELETE":
                resp = client.delete(path, params=params, headers=unauth_headers)
            else:
                continue

            assert resp.status_code == 401, (
                f"{method} {path} returned {resp.status_code}, expected 401"
            )

    def test_all_protected_endpoints_require_auth_no_header(self, client: TestClient):
        """Same as above but without any auth header at all — returns 422 (missing required header)."""
        for method, path in PROTECTED_ENDPOINTS:
            if "?" in path:
                base, qs = path.split("?", 1)
                params = dict(p.split("=") for p in qs.split("&"))
                path = base
            else:
                params = {}

            if method == "GET":
                resp = client.get(path, params=params)
            elif method == "POST":
                resp = client.post(path, json={}, params=params)
            elif method == "PATCH":
                resp = client.patch(path, json={}, params=params)
            elif method == "DELETE":
                resp = client.delete(path, params=params)
            else:
                continue

            # No Header at all = required field missing → 422
            assert resp.status_code == 422, (
                f"{method} {path} returned {resp.status_code}, expected 422 (missing header)"
            )
