"""
HTTP Proxy router — Hermes Bridge v0.2.0
Proxy HTTP requests to allowed external services.
"""
import base64
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status

from auth import verify_api_key

router = APIRouter(
    prefix="/api/proxy",
    tags=["HTTP Proxy"],
    dependencies=[Depends(verify_api_key)],
)

# Whitelist — hanya domain ini yang bisa di-proxy
ALLOWED_DOMAINS = {
    "api.github.com",
    "raw.githubusercontent.com",
    "github.com",
    "localhost",
    "127.0.0.1",
}

TIMEOUT = 30.0
MAX_RESPONSE_BYTES = 512 * 1024  # 512 KB


@router.get("/http")
async def http_proxy(url: str = Query(..., description="URL to proxy to"), method: str = Query("GET")):
    """Proxy an HTTP GET/HEAD request to an allowed domain.

    Args:
        url: Full URL (must be https:// or http://)
        method: HTTP method (GET or HEAD)

    Returns:
        Status code, headers, and body of the proxied response.
    """
    # Validate URL
    if not url.startswith(("https://", "http://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

    parsed = urlparse(url)
    hostname = parsed.hostname

    # Check whitelist
    if hostname and hostname not in ALLOWED_DOMAINS and not hostname.endswith(".github.com"):
        raise HTTPException(
            status_code=403,
            detail=f"Domain '{hostname}' not in allowed list. Allowed: {sorted(ALLOWED_DOMAINS)}",
        )

    if method.upper() not in ("GET", "HEAD"):
        raise HTTPException(status_code=400, detail="Only GET and HEAD methods are supported")

    # Proxy the request
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method=method.upper(),
                url=url,
                timeout=TIMEOUT,
                follow_redirects=True,
            )

            # Read body with size limit
            content = resp.content[:MAX_RESPONSE_BYTES]
            truncated = len(resp.content) > MAX_RESPONSE_BYTES

            # Try to decode as text, fallback to base64 for binary
            try:
                body = content.decode("utf-8")
                body_b64 = None
            except UnicodeDecodeError:
                body = None
                body_b64 = base64.b64encode(content).decode()

            return {
                "status_code": resp.status_code,
                "headers": dict(resp.headers),
                "body": body,
                "body_base64": body_b64,
                "truncated": truncated,
            }

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail=f"Timeout connecting to {url}")
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail=f"Could not connect to {url}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"HTTP error: {str(e)}")


@router.get("/allowed-domains")
async def allowed_domains():
    """List domains that can be proxied."""
    return {"allowed_domains": sorted(ALLOWED_DOMAINS)}
