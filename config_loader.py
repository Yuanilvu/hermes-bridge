"""Hermes Bridge config loader."""
import logging
import os
import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from models import ProviderCreate

BASE_DIR = Path(__file__).parent
CONFIG_TOML_PATH = BASE_DIR / "config" / "settings.toml"
PROVIDERS_TXT_PATH = BASE_DIR / "config" / "providers.txt"
API_KEY_FILE = BASE_DIR / "data" / ".api_key"

logger = logging.getLogger("hermes-bridge.config")


def _ensure_api_key(toml_val: str | None) -> str:
    """Return API key from env var, toml, auto-generated file, or fresh random."""
    env_key = os.getenv("BRIDGE_API_KEY")
    if env_key:
        return env_key
    if toml_val and toml_val != "hermes-local-2026":
        return toml_val

    # Check persisted key file
    if API_KEY_FILE.exists():
        key = API_KEY_FILE.read_text().strip()
        if key:
            return key

    # Generate fresh random key
    new_key = secrets.token_urlsafe(32)
    API_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    API_KEY_FILE.write_text(new_key + "\n")
    API_KEY_FILE.chmod(0o600)
    logger.warning(
        "No BRIDGE_API_KEY set. Generated random key — save it:\n"
        f"    BRIDGE_API_KEY={new_key}\n"
        f"Key also saved to {API_KEY_FILE} (owner-read-only)."
    )
    return new_key


class _Bridge:
    host: str
    port: int
    api_key: str


class _Cors:
    origins: List[str]


class _NineRouter:
    url: str


class _GitHub:
    owner: str
    repo: str


class _Vault:
    path: str


class _RateLimit:
    default: str
    health: str
    desktop: str
    vault: str
    proxy: str


class _Hub:
    def __init__(self):
        toml = self._load_toml()
        br = _Bridge()
        br.host = os.getenv("BRIDGE_HOST") or _toml_get(toml, "bridge", "host", "127.0.0.1")
        br.port = int(os.getenv("BRIDGE_PORT") or str(_toml_get(toml, "bridge", "port", 8199)))
        br.api_key = _ensure_api_key(_toml_get(toml, "bridge", "api_key", None))
        self.bridge = br

        cors = _Cors()
        cors_raw = _toml_get(toml, "cors", "origins", ["*"])
        cors.origins = cors_raw if isinstance(cors_raw, list) else [cors_raw]
        self.cors = cors

        nr = _NineRouter()
        nr.url = os.getenv("NINE_ROUTER_URL") or _toml_get(toml, "nine_router", "url", "http://localhost:20128")
        self.nine_router = nr

        gh = _GitHub()
        gh.owner = os.getenv("GITHUB_OWNER") or _toml_get(toml, "github", "owner", "Yuanilvu")
        gh.repo = os.getenv("GITHUB_REPO") or _toml_get(toml, "github", "repo", "hermes-bridge")
        self.github = gh

        vault = _Vault()
        vault.path = os.getenv("VAULT_PATH") or _toml_get(toml, "vault", "path", str(BASE_DIR.parent / "hermes-workspace"))
        self.vault = vault

        rl = _RateLimit()
        rl_toml = toml.get("rate_limit", {})
        rl.default = os.getenv("RATE_LIMIT_DEFAULT") or rl_toml.get("default", "30/minute")
        rl.health = os.getenv("RATE_LIMIT_HEALTH") or rl_toml.get("health", "60/minute")
        rl.desktop = os.getenv("RATE_LIMIT_DESKTOP") or rl_toml.get("desktop", "15/minute")
        rl.vault = os.getenv("RATE_LIMIT_VAULT") or rl_toml.get("vault", "30/minute")
        rl.proxy = os.getenv("RATE_LIMIT_PROXY") or rl_toml.get("proxy", "20/minute")
        self.rate_limit = rl

    def _load_toml(self) -> Dict[str, Any]:
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


def _toml_get(toml: dict, section: str, key: str, default: Any = None) -> Any:
    """Deep-get from toml dict with type-coercion."""
    s = toml.get(section, {})
    val = s.get(key)
    return val if val is not None else default


config = _Hub()


def load_providers() -> List[ProviderCreate]:
    return config.load_providers()
