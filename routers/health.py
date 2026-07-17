"""Hermes Bridge - Health check endpoints."""
import time
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends

from auth import verify_api_key
from config_loader import config

router = APIRouter(prefix="/api/health", tags=["Health"])

_start_time = time.time()


@router.get("")
async def health_check():
    """System health check."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "bridge_version": "0.1.0",
        "uptime_seconds": round(time.time() - _start_time, 2),
    }


@router.get("/nine-router", dependencies=[Depends(verify_api_key)])
async def nine_router_health():
    """Check 9router connectivity."""
    nr_url = config.nine_router.url
    try:
        t0 = time.time()
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{nr_url}/api/providers")
        latency = round((time.time() - t0) * 1000, 1)
        return {
            "reachable": True,
            "latency_ms": latency,
            "status_code": resp.status_code,
        }
    except httpx.RequestError as e:
        return {
            "reachable": False,
            "latency_ms": None,
            "error": str(e),
        }
