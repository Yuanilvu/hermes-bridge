"""
SQLite-backed provider store.
Replaces the JSON file store for better concurrent access and querying.
"""
import json
import sqlite3
import structlog
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from models import Provider, ProviderCreate

logger = structlog.get_logger()

DATA_DIR = Path(__file__).parent / "data"


def _db_path() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / "providers.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS providers (
            id TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            provider TEXT NOT NULL DEFAULT 'openai',
            api_key TEXT NOT NULL DEFAULT '',
            base_url TEXT NOT NULL DEFAULT '',
            models TEXT NOT NULL DEFAULT '[]',
            health_ok INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    logger.info("sqlite_db_initialized", path=str(_db_path()))


class SQLiteProviderStore:
    """Provider store backed by SQLite."""

    def list_all(self) -> List[Provider]:
        conn = _get_conn()
        rows = conn.execute("SELECT * FROM providers ORDER BY created_at ASC").fetchall()
        conn.close()
        return [self._row_to_provider(r) for r in rows]

    def get(self, provider_id: str) -> Optional[Provider]:
        conn = _get_conn()
        row = conn.execute("SELECT * FROM providers WHERE id = ?", (provider_id,)).fetchone()
        conn.close()
        return self._row_to_provider(row) if row else None

    def create(self, data: ProviderCreate) -> Provider:
        provider = Provider(
            id=str(uuid4()),
            label=data.label,
            provider=data.provider or "openai",
            api_key=data.api_key or "",
            base_url=data.base_url or "",
            models=data.models or [],
        )
        conn = _get_conn()
        conn.execute(
            "INSERT INTO providers (id, label, provider, api_key, base_url, models) VALUES (?, ?, ?, ?, ?, ?)",
            (provider.id, provider.label, provider.provider, provider.api_key, provider.base_url, json.dumps(provider.models)),
        )
        conn.commit()
        conn.close()
        logger.info("provider_created_sqlite", id=provider.id, label=provider.label)
        return provider

    def update(self, provider_id: str, data: ProviderCreate) -> Optional[Provider]:
        existing = self.get(provider_id)
        if not existing:
            return None
        conn = _get_conn()
        conn.execute(
            """UPDATE providers SET label=?, provider=?, api_key=?, base_url=?, models=?,
               updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (
                data.label or existing.label,
                data.provider or existing.provider,
                data.api_key or existing.api_key,
                data.base_url or existing.base_url,
                json.dumps(data.models or existing.models),
                provider_id,
            ),
        )
        conn.commit()
        conn.close()
        logger.info("provider_updated_sqlite", id=provider_id)
        return self.get(provider_id)

    def delete(self, provider_id: str) -> bool:
        conn = _get_conn()
        cur = conn.execute("DELETE FROM providers WHERE id = ?", (provider_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        conn.close()
        if deleted:
            logger.info("provider_deleted_sqlite", id=provider_id)
        return deleted

    def import_bulk(self, providers_data: List[ProviderCreate]) -> List[Provider]:
        created = []
        conn = _get_conn()
        for data in providers_data:
            pid = str(uuid4())
            conn.execute(
                "INSERT INTO providers (id, label, provider, api_key, base_url, models) VALUES (?, ?, ?, ?, ?, ?)",
                (pid, data.label, data.provider or "openai", data.api_key or "", data.base_url or "", json.dumps(data.models or [])),
            )
            created.append(Provider(
                id=pid, label=data.label, provider=data.provider or "openai",
                api_key=data.api_key or "", base_url=data.base_url or "", models=data.models or [],
            ))
        conn.commit()
        conn.close()
        logger.info("providers_imported_sqlite", count=len(created))
        return created

    def health_check_all(self) -> List[dict]:
        """Return health status for all providers (lightweight)."""
        results = []
        for p in self.list_all():
            results.append({
                "id": p.id,
                "label": p.label,
                "provider": p.provider,
                "health_ok": p.health_ok,
            })
        return results

    @staticmethod
    def _row_to_provider(row) -> Provider:
        return Provider(
            id=row["id"],
            label=row["label"],
            provider=row["provider"],
            api_key=row["api_key"],
            base_url=row["base_url"],
            models=json.loads(row["models"]) if isinstance(row["models"], str) else (row["models"] or []),
            health_ok=bool(row["health_ok"]),
        )


# Singleton
_store_instance: Optional[SQLiteProviderStore] = None


def get_store() -> SQLiteProviderStore:
    global _store_instance
    if _store_instance is None:
        init_db()
        _store_instance = SQLiteProviderStore()
    return _store_instance
