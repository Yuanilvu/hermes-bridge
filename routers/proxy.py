"""
Proxy router — OpenAI-compatible /v1/chat/completions endpoint
with provider failover and streaming passthrough.
"""
import json
import structlog
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from auth import verify_api_key
from config_loader import config
from models import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatChoice,
    ChatMessage,
    ChunkChoice,
    DeltaMessage,
    Usage,
    get_adapter,
)
from store import get_store, ProviderStore

logger = structlog.get_logger()

router = APIRouter(
    prefix="/v1",
    tags=["Chat Completions"],
    dependencies=[Depends(verify_api_key)],
)

DATA_DIR = Path(__file__).parent.parent / "data"


def _get_store() -> ProviderStore:
    return get_store(DATA_DIR)


async def _try_provider(
    client: httpx.AsyncClient,
    provider,
    req: ChatCompletionRequest,
) -> ChatCompletionResponse:
    """Call one provider synchronously (non-streaming)."""
    adapter = get_adapter(provider)
    body = adapter.transform_request(req)

    resp = await client.post(
        adapter.chat_url(),
        headers=adapter.headers(),
        json=body,
        timeout=60.0,
    )
    resp.raise_for_status()
    data = resp.json()

    # Parse OpenAI-format response
    choice_raw = data["choices"][0]
    message = ChatMessage(
        role=choice_raw.get("message", {}).get("role", "assistant"),
        content=choice_raw.get("message", {}).get("content", ""),
    )
    usage_raw = data.get("usage")
    usage = Usage(**usage_raw) if usage_raw else None

    return ChatCompletionResponse(
        model=req.model,
        choices=[ChatChoice(message=message)],
        usage=usage,
    )


async def _try_provider_stream(
    client: httpx.AsyncClient,
    provider,
    req: ChatCompletionRequest,
):
    """Call one provider with streaming. Yields SSE bytes."""
    adapter = get_adapter(provider)
    body = adapter.transform_request(req)
    body["stream"] = True

    async with client.stream(
        "POST",
        adapter.chat_url(),
        headers=adapter.headers(),
        json=body,
        timeout=120.0,
    ) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line.strip():
                continue
            transformed = adapter.transform_stream_line(line)
            if transformed is not None:
                yield f"{transformed}\n\n"
        # Final [DONE] signal
        yield "data: [DONE]\n\n"


@router.post("/chat/completions")
async def chat_completions(req: ChatCompletionRequest):
    """Proxy chat completion request with automatic failover across providers."""
    store = _get_store()
    providers = store.get_all()
    if not providers:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No providers configured. Add a provider via POST /api/providers first.",
        )

    last_error = None

    if req.stream:
        return await _stream_chat(providers, req)

    # Non-streaming: try each provider in order
    async with httpx.AsyncClient() as client:
        for provider in providers:
            try:
                return await _try_provider(client, provider, req)
            except httpx.TimeoutException as e:
                last_error = f"Provider '{provider.label}' timed out"
                logger.warning("proxy_timeout", provider=provider.label, error=str(e))
            except httpx.HTTPStatusError as e:
                last_error = f"Provider '{provider.label}' returned {e.response.status_code}"
                logger.warning("proxy_http_error", provider=provider.label, status=e.response.status_code)
            except Exception as e:
                last_error = f"Provider '{provider.label}' failed: {e}"
                logger.error("proxy_error", provider=provider.label, error=str(e))

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"All providers failed. Last error: {last_error}",
    )


async def _stream_chat(providers, req: ChatCompletionRequest):
    """Try streaming across providers with failover."""
    async with httpx.AsyncClient() as client:
        for provider in providers:
            try:
                streamer = _try_provider_stream(client, provider, req)

                async def _gen(s=streamer):
                    async for chunk in s:
                        yield chunk

                return StreamingResponse(
                    _gen(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                    },
                )
            except Exception as e:
                logger.warning("stream_failover", provider=provider.label, error=str(e))
                continue

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="All providers failed for streaming request.",
    )
