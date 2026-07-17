"""
Pydantic models untuk Hermes Bridge.
"""
import time
from uuid import uuid4
from typing import List, Optional
from pydantic import BaseModel, Field


# ── Provider Store ──

class Provider(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    label: str
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"


class ProviderCreate(BaseModel):
    label: str
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"


class ProviderUpdate(BaseModel):
    label: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None


# ── OpenAI-compatible Chat Completion ──

class ChatMessage(BaseModel):
    role: str  # system | user | assistant
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "gpt-4o-mini"
    messages: List[ChatMessage]
    stream: bool = False
    temperature: float | None = 0.7
    max_tokens: int | None = None


class ChatChoice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: str = "stop"


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid4().hex[:12]}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[ChatChoice]
    usage: Usage | None = None


# ── Streaming Chunk (SSE) ──

class DeltaMessage(BaseModel):
    role: str | None = None
    content: str | None = None


class ChunkChoice(BaseModel):
    index: int = 0
    delta: DeltaMessage = Field(default_factory=DeltaMessage)
    finish_reason: str | None = None


class ChatCompletionChunk(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid4().hex[:12]}")
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[ChunkChoice]


# ── Provider-specific adapters ──

class ProviderAdapter:
    """Base adapter — transform generic request → provider-native format."""

    def __init__(self, provider: Provider):
        self.label = provider.label
        self.api_key = provider.api_key
        self.base_url = provider.base_url.rstrip("/")
        self.model = provider.model

    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def chat_url(self) -> str:
        return f"{self.base_url}/chat/completions"

    def transform_request(self, req: ChatCompletionRequest) -> dict:
        body: dict = {
            "model": self.model,
            "messages": [m.model_dump() for m in req.messages],
            "stream": req.stream,
        }
        if req.temperature is not None:
            body["temperature"] = req.temperature
        if req.max_tokens is not None:
            body["max_tokens"] = req.max_tokens
        return body

    def transform_stream_line(self, line: str) -> str | None:
        if line.startswith("data: "):
            return line
        return None


class GeminiAdapter(ProviderAdapter):
    """Gemini → OpenAI format adapter."""

    def __init__(self, provider: Provider):
        super().__init__(provider)
        # Force Gemini base_url
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    def chat_url(self) -> str:
        return f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"

    def headers(self) -> dict:
        return {"Content-Type": "application/json"}

    def transform_request(self, req: ChatCompletionRequest) -> dict:
        gemini_messages = []
        system_prompt = ""
        for m in req.messages:
            if m.role == "system":
                system_prompt += m.content + "\n"
            elif m.role == "user":
                gemini_messages.append({"role": "user", "parts": [{"text": m.content}]})
            elif m.role == "assistant":
                gemini_messages.append({"role": "model", "parts": [{"text": m.content}]})

        body = {"contents": gemini_messages}
        if system_prompt.strip():
            body["system_instruction"] = {"parts": [{"text": system_prompt.strip()}]}
        return body

    def transform_stream_line(self, line: str) -> str | None:
        if line.startswith("data: "):
            return line
        return None


# ── Adapter registry ──

ADAPTER_MAP: dict[str, type[ProviderAdapter]] = {
    "openai": ProviderAdapter,
    "groq": ProviderAdapter,
    "together": ProviderAdapter,
    "deepseek": ProviderAdapter,
    "9router": ProviderAdapter,
    "openrouter": ProviderAdapter,
    "anthropic": ProviderAdapter,
    "gemini": GeminiAdapter,
}


def get_adapter(provider: Provider) -> ProviderAdapter:
    label_lower = provider.label.lower().replace(" ", "-").replace("_", "-")
    for key, cls in ADAPTER_MAP.items():
        if key in label_lower:
            return cls(provider)
    return ProviderAdapter(provider)
