"""Hermes Bridge - Main entry point."""
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from rate_limit import limiter

from auth import verify_api_key
from config_loader import config
from logging_config import configure_logging
from routers import (
    health as health_router,
    providers as providers_router,
    proxy as proxy_router,
    vault as vault_router,
)

# Structured logging init (before app creation)
configure_logging(log_level="INFO", json_output=False)

# Create data directory
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Hermes Bridge",
    description="Local automation bridge for Hermes Agent",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow local access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting — shared limiter from rate_limit.py
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Mount routers
app.include_router(health_router.router)
app.include_router(providers_router.router)
app.include_router(proxy_router.router)
app.include_router(vault_router.router)


@app.get("/")
async def root():
    """Root endpoint — API info."""
    return {
        "name": "Hermes Bridge",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/api", dependencies=[Depends(verify_api_key)])
async def api_root():
    """API root — list available endpoints."""
    return {
        "endpoints": {
            "health": "/api/health",
            "health/nine-router": "/api/health/nine-router",
            "providers": "/api/providers",
            "providers/health": "/api/providers/health",
            "providers/import": "/api/providers/import",
        }
    }


def main():
    host = config.bridge.host
    port = config.bridge.port
    print(f"🟢 Hermes Bridge running on http://{host}:{port}")
    print(f"📘 API docs at http://{host}:{port}/docs")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
