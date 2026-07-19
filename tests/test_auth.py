"""Tests for Authentication."""
from fastapi.testclient import TestClient


class TestAuth:
    """All protected endpoints should reject missing/wrong keys."""

    # Endpoints that REQUIRE X-Bridge-Key (have Depends(verify_api_key))
    # Note: POST endpoints excluded — they need specific request bodies
    PROTECTED_ENDPOINTS = [
        ("GET", "/api"),
        ("GET", "/api/vault"),
        ("GET", "/api/vault/files/search?q=test"),
        ("GET", "/api/vault/files/structure"),
        ("GET", "/api/vault/files/read?file=test.md"),
        ("GET", "/api/desktop/status"),
        ("GET", "/api/desktop/screenshot"),
        ("GET", "/api/proxy/http?url=http://example.com"),
        ("GET", "/api/proxy/allowed-domains"),
        ("GET", "/api/health/nine-router"),
    ]

    # Endpoints public (no auth needed — for Docker HEALTHCHECK etc.)
    PUBLIC_ENDPOINTS = [
        ("GET", "/"),
        ("GET", "/api/health"),
    ]

    def test_protected_missing_header_rejected(self, client: TestClient):
        """No X-Bridge-Key header → 422 (FastAPI required param validator)."""
        for method, path in self.PROTECTED_ENDPOINTS:
            resp = client.request(method, path)
            assert resp.status_code == 422, f"{method} {path} returned {resp.status_code}, expected 422"

    def test_protected_wrong_key_rejected(self, client: TestClient, unauth_headers):
        """Wrong X-Bridge-Key → 401 Unauthorized."""
        for method, path in self.PROTECTED_ENDPOINTS:
            resp = client.request(method, path, headers=unauth_headers)
            assert resp.status_code == 401, f"{method} {path} returned {resp.status_code}, expected 401"

    def test_public_endpoints_no_auth_needed(self, client: TestClient):
        """Public endpoints should work without any auth."""
        for method, path in self.PUBLIC_ENDPOINTS:
            resp = client.request(method, path)
            assert resp.status_code == 200, f"{method} {path} returned {resp.status_code}, expected 200"

    def test_protected_with_valid_key(self, client: TestClient, auth_headers):
        """Valid key should pass on all protected endpoints."""
        for method, path in self.PROTECTED_ENDPOINTS:
            # Skip proxy/http — it has its own domain whitelist that may 403
            if "proxy/http" in path:
                continue
            resp = client.request(method, path, headers=auth_headers)
            # These endpoints may return 200 or other codes for other reasons
            # (e.g. 404 for non-existent file), but they must NOT be 401/403/422
            assert resp.status_code not in (401, 403, 422), f"{method} {path} returned {resp.status_code}"
