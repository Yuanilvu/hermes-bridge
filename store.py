"""
Simple JSON file-based provider store.
"""
import json
from pathlib import Path
from typing import List, Optional

from models import Provider, ProviderCreate


class ProviderStore:
    def __init__(self, data_dir: Path):
        self.file_path = data_dir / "providers.json"
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._providers: List[Provider] = self._load()

    def _load(self) -> List[Provider]:
        if not self.file_path.exists():
            return []
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
                return [Provider(**item) for item in raw]
        except Exception:
            return []

    def _save(self):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump([p.model_dump() for p in self._providers], f, indent=2)

    def get_all(self) -> List[Provider]:
        return self._providers.copy()

    def get(self, provider_id: str) -> Optional[Provider]:
        for p in self._providers:
            if p.id == provider_id:
                return p
        return None

    def create(self, provider_create: ProviderCreate) -> Provider:
        provider = Provider(label=provider_create.label, api_key=provider_create.api_key)
        self._providers.append(provider)
        self._save()
        return provider

    def update(self, provider_id: str, updates: dict) -> Optional[Provider]:
        provider = self.get(provider_id)
        if not provider:
            return None
        if "label" in updates:
            provider.label = updates["label"]
        if "api_key" in updates:
            provider.api_key = updates["api_key"]
        self._save()
        return provider

    def delete(self, provider_id: str) -> bool:
        provider = self.get(provider_id)
        if not provider:
            return False
        self._providers.remove(provider)
        self._save()
        return True

    def import_from_list(self, provider_creates: List[ProviderCreate]) -> List[Provider]:
        return [self.create(pc) for pc in provider_creates]


_default_store: Optional[ProviderStore] = None


def get_store(data_dir: Path) -> ProviderStore:
    global _default_store
    if _default_store is None:
        _default_store = ProviderStore(data_dir)
    return _default_store
