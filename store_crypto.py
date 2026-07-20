"""
Encryption at rest for provider store — Hermes Bridge.
Uses Fernet (symmetric) to encrypt API keys before writing to disk.

Key sources (in order of precedence):
1. HERMES_STORE_KEY environment variable (base64-encoded 32-byte key)
2. .store.key file in data directory (auto-generated on first use)
"""
import base64
import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger("hermes-bridge.store_crypto")

# At least 32 bytes of entropy for key derivation
_KEY_ENV_VAR = "HERMES_STORE_KEY"
_KEY_FILE = ".store.key"
_KEY_BYTES = 32

_fernet_instance = None


def _load_or_create_key(data_dir: Path) -> bytes:
    """Load key from env var or file; create key file if missing."""
    env_key = os.environ.get(_KEY_ENV_VAR)
    if env_key:
        try:
            return base64.urlsafe_b64decode(env_key)
        except Exception as e:
            logger.warning(f"Invalid HERMES_STORE_KEY; falling back to file key: {e}")

    key_path = data_dir / _KEY_FILE
    if key_path.exists():
        raw = key_path.read_bytes().strip()
        return base64.urlsafe_b64decode(raw)

    # Generate new key
    raw_key = os.urandom(_KEY_BYTES)
    encoded = base64.urlsafe_b64encode(raw_key).decode()
    data_dir.mkdir(parents=True, exist_ok=True)
    key_path.write_text(encoded + "\n")
    key_path.chmod(0o600)  # owner-read-only
    logger.info(f"Generated new store encryption key at {key_path}")
    return raw_key


def _get_fernet(data_dir: Path) -> Fernet:
    global _fernet_instance
    if _fernet_instance is None:
        raw_key = _load_or_create_key(data_dir)
        fernet_key = base64.urlsafe_b64encode(raw_key)
        _fernet_instance = Fernet(fernet_key)
    return _fernet_instance


def encrypt_api_key(api_key: str, data_dir: Path) -> str:
    """Encrypt an API key and return a base64 ciphertext string."""
    if not api_key:
        return ""
    f = _get_fernet(data_dir)
    return f.encrypt(api_key.encode()).decode()


def decrypt_api_key(ciphertext: str, data_dir: Path) -> str:
    """Decrypt a base64 ciphertext back to the original API key."""
    if not ciphertext:
        return ""
    f = _get_fernet(data_dir)
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        logger.error("Failed to decrypt API key — key may have changed or data is corrupted")
        return ""
    except Exception as e:
        logger.error(f"Decryption error: {e}")
        return ""


def reset_fernet():
    """Reset cached Fernet instance (for testing)."""
    global _fernet_instance
    _fernet_instance = None
