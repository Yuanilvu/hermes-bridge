"""Hermes Bridge - Authentication dependency."""
from fastapi import Header, HTTPException, status
from config_loader import config


async def verify_api_key(x_bridge_key: str = Header(..., alias="X-Bridge-Key")):
    """FastAPI dependency: verify X-Bridge-Key header matches config."""
    if x_bridge_key != config.bridge.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Bridge-Key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return x_bridge_key
