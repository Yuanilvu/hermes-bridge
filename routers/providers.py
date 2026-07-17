"""Hermes Bridge - Provider management endpoints."""
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from auth import verify_api_key
from config_loader import config, load_providers
from models import ProviderCreate, ProviderUpdate
from store import get_store, ProviderStore

router = APIRouter(prefix="/api/providers", tags=["Providers"], dependencies=[Depends(verify_api_key)])

DATA_DIR = Path(__file__).parent.parent / "data"


def _get_store() -> ProviderStore:
    return get_store(DATA_DIR)


@router.get("")
async def list_providers():
    """Get all providers."""
    store = _get_store()
    return store.get_all()


@router.get("/health")
async def providers_health():
    """Check status of all providers."""
    store = _get_store()
    providers = store.get_all()

    results = []
    for p in providers:
        try:
            t0 = datetime.now()
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{config.nine_router.url}/v1/chat/completions",
                    headers={"Authorization": f"Bearer {p.api_key}"},
                    json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "ping"}]},
                )
            latency = (datetime.now() - t0).total_seconds() * 1000
            results.append({
                "id": p.id,
                "label": p.label,
                "status": "ok" if resp.status_code < 500 else "error",
                "latency_ms": round(latency, 1),
                "http_status": resp.status_code,
            })
        except Exception as e:
            results.append({
                "id": p.id,
                "label": p.label,
                "status": "error",
                "error": str(e),
            })

    return {
        "total": len(results),
        "providers": results,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_provider(provider: ProviderCreate):
    """Add a new provider."""
    store = _get_store()
    return store.create(provider)


@router.get("/{provider_id}")
async def get_provider(provider_id: str):
    """Get a specific provider."""
    store = _get_store()
    provider = store.get(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@router.patch("/{provider_id}")
async def update_provider(provider_id: str, update: ProviderUpdate):
    """Update a provider."""
    store = _get_store()
    updated = store.update(provider_id, update.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Provider not found")
    return updated


@router.delete("/{provider_id}")
async def delete_provider(provider_id: str):
    """Delete a provider."""
    store = _get_store()
    if store.delete(provider_id):
        return {"status": "deleted", "id": provider_id}
    raise HTTPException(status_code=404, detail="Provider not found")


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_providers():
    """Import providers from config/providers.txt."""
    providers = load_providers()
    if not providers:
        return {"imported": 0, "message": "No providers found in config/providers.txt"}
    store = _get_store()
    created = store.import_from_list(providers)
    return {"imported": len(created), "providers": created}
