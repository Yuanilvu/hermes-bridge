"""Pytest configuration for Hermes Bridge."""
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure the bridge package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("BRIDGE_API_KEY", "test-key-12345")
os.environ.setdefault("BRIDGE_HOST", "127.0.0.1")
os.environ.setdefault("BRIDGE_PORT", "8199")
os.environ.setdefault("VAULT_PATH", str(Path(__file__).parent.parent / "tests" / "fixtures" / "vault"))


@pytest.fixture(scope="session")
def app():
    """Build the FastAPI app for TestClient (lazy import to avoid side effects on import)."""
    # Set test env before ANY bridge module is imported
    from server import app as bridge_app
    return bridge_app


@pytest.fixture(scope="session")
def client(app):
    """TestClient wrapping the Hermes Bridge app."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def api_key() -> str:
    return "test-key-12345"


@pytest.fixture(scope="session")
def auth_headers(api_key) -> dict:
    return {"X-Bridge-Key": api_key}


@pytest.fixture(scope="session")
def unauth_headers() -> dict:
    return {"X-Bridge-Key": "wrong-key"}
