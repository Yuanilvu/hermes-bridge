"""
Vault info endpoint — provides metadata about Hermes bridge state.
"""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from auth import verify_api_key
from config_loader import config
from store import get_store, ProviderStore

DATA_DIR = Path(__file__).parent.parent / "data"

router = APIRouter(
    prefix="/api",
    tags=["Vault"],
    dependencies=[Depends(verify_api_key)],
)


def _get_store() -> ProviderStore:
    return get_store(DATA_DIR)


@router.get("/vault")
async def vault_info():
    """Return metadata about the Hermes bridge vault."""
    store = _get_store()
    providers = store.get_all()
    return {
        "provider_count": len(providers),
        "providers": [{"id": p.id, "label": p.label, "model": p.model} for p in providers],
        "bridge_version": "0.1.0",
    }


@router.get("/vault/providers/{provider_id}")
async def vault_provider_detail(provider_id: str):
    """Return detail for a specific provider."""
    store = _get_store()
    provider = store.get(provider_id)
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    return {
        "id": provider.id,
        "label": provider.label,
        "base_url": provider.base_url,
        "model": provider.model,
    }
