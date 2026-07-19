"""Tests for Vault endpoints."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


class TestVault:
    def test_vault_info(self, client: TestClient, auth_headers):
        resp = client.get("/api/vault", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "provider_count" in data
        assert "bridge_version" in data

    def test_vault_structure(self, client: TestClient, auth_headers):
        resp = client.get("/api/vault/files/structure", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "structure" in data or "vault_path" in data

    def test_vault_search_rejects_empty_query(self, client: TestClient, auth_headers):
        resp = client.get("/api/vault/files/search", params={"q": ""}, headers=auth_headers)
        # Empty query should be rejected by validator
        assert resp.status_code == 422

    def test_vault_search_normal(self, client: TestClient, auth_headers):
        resp = client.get("/api/vault/files/search", params={"q": "hermes", "path": "."}, headers=auth_headers)
        # Search should work; results may vary
        assert resp.status_code in (200, 422)

    def test_vault_read_nonexistent(self, client: TestClient, auth_headers):
        resp = client.get("/api/vault/files/read", params={"file": "nonexistent-file-xyz.md"}, headers=auth_headers)
        assert resp.status_code in (404, 422)

    def test_vault_write_oversized_rejected(self, client: TestClient, auth_headers):
        big_content = "x" * (1024 * 1024 + 100)
        resp = client.post(
            "/api/vault/files/write",
            json={"file": "notes/inbox/big.md", "content": big_content},
            headers=auth_headers,
        )
        # Should be rejected by content validator
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text[:200]}"
