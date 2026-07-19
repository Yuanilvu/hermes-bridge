"""Tests for HTTP Proxy endpoints."""
from fastapi.testclient import TestClient


class TestProxy:
    def test_allowed_domains(self, client: TestClient, auth_headers):
        resp = client.get("/api/proxy/allowed-domains", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "allowed_domains" in data
        assert "api.github.com" in data["allowed_domains"]

    def test_proxy_rejects_http_url_without_host(self, client: TestClient, auth_headers):
        """Proxy should reject malformed URL with no hostname."""
        resp = client.get("/api/proxy/http", params={"url": "http://"}, headers=auth_headers)
        assert resp.status_code == 400
        assert "Could not parse hostname" in resp.text

    def test_proxy_rejects_forbidden_domain(self, client: TestClient, auth_headers):
        resp = client.get("/api/proxy/http", params={"url": "http://evil-malware.com"}, headers=auth_headers)
        assert resp.status_code == 403
        assert "not in allowed list" in resp.text

    def test_proxy_rejects_not_http(self, client: TestClient, auth_headers):
        resp = client.get("/api/proxy/http", params={"url": "ftp://example.com/file"}, headers=auth_headers)
        assert resp.status_code == 400
        assert "URL must start with http" in resp.text
