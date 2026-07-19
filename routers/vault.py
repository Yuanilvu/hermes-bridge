"""
Vault router — Hermes Bridge v0.2.1
Provider store + actual vault filesystem search.
"""
import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status

from auth import verify_api_key
from config_loader import config
from store import get_store, ProviderStore
from pydantic import BaseModel, field_validator


DATA_DIR = Path(__file__).parent.parent / "data"

router = APIRouter(
    prefix="/api",
    tags=["Vault"],
    dependencies=[Depends(verify_api_key)],
)


def _get_store() -> ProviderStore:
    return get_store(DATA_DIR)


# ── Existing: provider store endpoints ──────────────────────────────


@router.get("/vault")
async def vault_info():
    """Return metadata about the Hermes bridge vault (provider store)."""
    store = _get_store()
    providers = store.get_all()
    return {
        "provider_count": len(providers),
        "providers": [{"id": p.id, "label": p.label, "model": p.model} for p in providers],
        "bridge_version": "0.2.1",
    }


@router.get("/vault/providers/{provider_id}")
async def vault_provider_detail(provider_id: str):
    """Return detail for a specific provider."""
    store = _get_store()
    provider = store.get(provider_id)
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    return {
        "id": provider.id,
        "label": provider.label,
        "base_url": provider.base_url,
        "model": provider.model,
    }


# ── New: vault filesystem search ────────────────────────────────────


@router.get("/vault/files/search")
async def vault_search(
    q: str = Query(..., description="Search query (regex or plain text)", min_length=1),
    path: str = Query("notes", description="Subdirectory under vault to search (e.g. notes, notes/daily)"),
    max_results: int = Query(20, ge=1, le=100),
):
    """Search files in the Obsidian vault by content.

    Uses ripgrep (rg) for fast recursive search.
    """
    vault_root = Path(config.vault.path).expanduser().resolve()
    search_dir = vault_root / path

    if not search_dir.exists():
        raise HTTPException(status_code=404, detail=f"Path '{path}' not found in vault")

    try:
        result = subprocess.run(
            ["rg", "-l", "--smart-case", "--max-count", "5", q, str(search_dir)],
            capture_output=True, text=True, timeout=30,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="ripgrep (rg) not found")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Search timed out")

    files = [f for f in result.stdout.strip().split("\n") if f.strip()]
    # Show relative paths
    files_rel = [str(Path(f).relative_to(vault_root)) for f in files[:max_results]]

    return {
        "query": q,
        "path": path,
        "total": len(files),
        "results": files_rel,
    }


@router.get("/vault/files/structure")
async def vault_structure():
    """List vault directory structure (top-level folders and file counts)."""
    vault_root = Path(config.vault.path).expanduser().resolve()
    if not vault_root.exists():
        raise HTTPException(status_code=404, detail="Vault path not found")

    structure = {}
    for child in sorted(vault_root.iterdir()):
        if child.is_dir() and not child.name.startswith("."):
            md_count = len(list(child.glob("*.md")))
            structure[child.name] = {"files": md_count, "path": str(child.relative_to(vault_root))}

    return {
        "vault_root": str(vault_root),
        "structure": structure,
        "total_dirs": len(structure),
    }


@router.get("/vault/files/read")
async def vault_read(
    file: str = Query(..., description="File path relative to vault root"),
    offset: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    """Read a vault file with line numbers and pagination."""
    vault_root = Path(config.vault.path).expanduser().resolve()
    full_path = (vault_root / file).resolve()

    # Ensure it's inside vault
    if not str(full_path).startswith(str(vault_root)):
        raise HTTPException(status_code=403, detail="Path traversal detected")

    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail=f"File '{file}' not found")

    try:
        lines = full_path.read_text(encoding="utf-8").splitlines()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {e}")

    total = len(lines)
    start = offset - 1
    end = start + limit
    page = lines[start:end]

    return {
        "file": file,
        "total_lines": total,
        "offset": offset,
        "limit": limit,
        "lines": [
            {"num": i + start + 1, "content": line}
            for i, line in enumerate(page)
        ],
    }


class VaultWriteRequest(BaseModel):
    file: str  # path relative to vault root
    content: str  # full file content (overwrites existing)
    create_dirs: bool = True  # auto-create parent directories

    @field_validator("content")
    @classmethod
    def validate_content(cls, v):
        max_bytes = 1024 * 1024  # 1 MB
        if len(v.encode("utf-8")) > max_bytes:
            raise ValueError(f"Content too large (max {max_bytes // 1024} KB)")
        return v


@router.post("/vault/files/write")
async def vault_write(req: VaultWriteRequest):
    """Write content to a vault file (creates or overwrites).

    - file: path relative to vault root (e.g. 'notes/inbox/new-note.md')
    - content: full file content (overwrites existing)
    - create_dirs: auto-create parent directories (default: true)
    """
    vault_root = Path(config.vault.path).expanduser().resolve()
    full_path = (vault_root / req.file).resolve()

    # Path traversal check
    if not str(full_path).startswith(str(vault_root)):
        raise HTTPException(status_code=403, detail="Path traversal detected")

    if req.create_dirs:
        full_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        full_path.write_text(req.content, encoding="utf-8")
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Error writing file: {e}")

    return {
        "status": "ok",
        "file": req.file,
        "bytes": len(req.content.encode("utf-8")),
    }
