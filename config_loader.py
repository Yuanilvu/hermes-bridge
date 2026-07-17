"""
Hermes Bridge config loader.
Baca environment, config/settings.toml, dan config/providers.txt.
"""
import os
from pathlib import Path
from typing import Any, Dict, List

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from models import ProviderCreate

BASE_DIR = Path(__file__).parent
CONFIG_TOML_PATH = BASE_DIR / "config" / "settings.toml"
PROVIDERS_TXT_PATH = BASE_DIR / "config" / "providers.txt"


class _Bridge:
    host: str
    port: int
    api_key: str


class _NineRouter:
    url: str


class _GitHub:
    owner: str
    repo: str


class _Vault:
    path: str


class _Hub:
    def __init__(self):
        bridge = _Bridge()
        bridge.host = os.getenv("BRIDGE_HOST", "127.0.0.1")
        bridge.port = int(os.getenv("BRIDGE_PORT", "8199"))
        bridge.api_key = os.getenv("BRIDGE_API_KEY", "hermes-local-2026")
        self.bridge = bridge

        nr = _NineRouter()
        nr.url = os.getenv("NINE_ROUTER_URL", "http://localhost:20128")
        self.nine_router = nr

        gh = _GitHub()
        gh.owner = os.getenv("GITHUB_OWNER", "Yuanilvu")
        gh.repo = os.getenv("GITHUB_REPO", "hermes-bridge")
        self.github = gh

        vault = _Vault()
        vault.path = os.getenv("VAULT_PATH", str(BASE_DIR.parent / "hermes-workspace"))
        self.vault = vault

    @staticmethod
    def load_toml() -> Dict[str, Any]:
        if not CONFIG_TOML_PATH.exists():
            return {}
        with open(CONFIG_TOML_PATH, "rb") as f:
            return tomllib.load(f)

    @staticmethod
    def load_providers() -> List[ProviderCreate]:
        providers: List[ProviderCreate] = []
        if not PROVIDERS_TXT_PATH.exists():
            return providers
        with open(PROVIDERS_TXT_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(",", 1)
                if len(parts) != 2:
                    continue
                label, api_key = parts
                providers.append(ProviderCreate(label=label.strip(), api_key=api_key.strip()))
        return providers


config = _Hub()


def load_providers() -> List[ProviderCreate]:
    """Module-level helper — delegates to config.load_providers()."""
    return config.load_providers()
