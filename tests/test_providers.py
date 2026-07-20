"""Tests for Provider CRUD endpoints."""
import uuid

import pytest
from fastapi.testclient import TestClient


class TestProviders:
    PROVIDER_ENDPOINT = "/api/providers"
    
    def test_list_providers_empty(self, client: TestClient, auth_headers):
        resp = client.get(self.PROVIDER_ENDPOINT, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
    
    def test_create_provider(self, client: TestClient, auth_headers):
        payload = {
            "label": "test-openai",
            "api_key": "sk-test-abc-123",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o-mini",
        }
        resp = client.post(self.PROVIDER_ENDPOINT, json=payload, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["label"] == payload["label"]
        assert data["api_key"] == payload["api_key"]  # returned in response
        assert data["base_url"] == payload["base_url"]
        assert data["model"] == payload["model"]
        assert "id" in data
    
    def test_provider_crud_lifecycle(self, client: TestClient, auth_headers):
        """Full CRUD lifecycle: create → list → get → update → delete."""
        # Create
        payload = {
            "label": "crud-test",
            "api_key": "sk-crud-key",
            "base_url": "https://test.api.com",
            "model": "gpt-5",
        }
        resp = client.post(self.PROVIDER_ENDPOINT, json=payload, headers=auth_headers)
        assert resp.status_code == 201
        pid = resp.json()["id"]
        
        # List — should include new provider
        resp = client.get(self.PROVIDER_ENDPOINT, headers=auth_headers)
        ids = [p["id"] for p in resp.json()]
        assert pid in ids
        
        # Get by id
        resp = client.get(f"{self.PROVIDER_ENDPOINT}/{pid}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["label"] == "crud-test"
        
        # Update
        update = {"label": "crud-test-renamed", "model": "gpt-5-turbo"}
        resp = client.patch(f"{self.PROVIDER_ENDPOINT}/{pid}", json=update, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["label"] == "crud-test-renamed"
        assert resp.json()["model"] == "gpt-5-turbo"
        
        # Delete
        resp = client.delete(f"{self.PROVIDER_ENDPOINT}/{pid}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"
        
        # Verify gone
        resp = client.get(f"{self.PROVIDER_ENDPOINT}/{pid}", headers=auth_headers)
        assert resp.status_code == 404
    
    def test_get_nonexistent_provider(self, client: TestClient, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"{self.PROVIDER_ENDPOINT}/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404
    
    def test_delete_nonexistent_provider(self, client: TestClient, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = client.delete(f"{self.PROVIDER_ENDPOINT}/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404
    
    def test_create_provider_wrong_auth(self, client: TestClient, unauth_headers):
        """Create provider with wrong auth should fail."""
        resp = client.post(self.PROVIDER_ENDPOINT, json={"label": "x", "api_key": "y"}, headers=unauth_headers)
        assert resp.status_code == 401

    def test_create_provider_no_header(self, client: TestClient):
        """Create provider without auth header → 422."""
        resp = client.post(self.PROVIDER_ENDPOINT, json={"label": "x", "api_key": "y"})
        assert resp.status_code == 422

    def test_list_providers_wrong_auth(self, client: TestClient, unauth_headers):
        resp = client.get(self.PROVIDER_ENDPOINT, headers=unauth_headers)
        assert resp.status_code == 401

    def test_list_providers_no_header(self, client: TestClient):
        resp = client.get(self.PROVIDER_ENDPOINT)
        assert resp.status_code == 422
    
    def test_provider_health_endpoint(self, client: TestClient, auth_headers):
        """Health check endpoint should return list (possibly empty)."""
        resp = client.get(f"{self.PROVIDER_ENDPOINT}/health", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "providers" in data
