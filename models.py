"""
Pydantic models untuk Hermes Bridge.
"""
from uuid import uuid4
from pydantic import BaseModel, Field


class Provider(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    label: str
    api_key: str


class ProviderCreate(BaseModel):
    label: str
    api_key: str


class ProviderUpdate(BaseModel):
    label: str | None = None
    api_key: str | None = None
