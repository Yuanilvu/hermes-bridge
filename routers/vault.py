"""
Vault filesystem router — Hermes Bridge v0.2.3
Read, write, search files in the Hermes/Obsidian vault.
"""
import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, field_validator

from auth import verify_api_key
from config_loader import config
from rate_limit import limiter

router = APIRouter(
    prefix="/api/vault",
    tags=["Vault"],
    dependencies=[Depends(verify_api_key)],
)


@router.get("")
async def vault_info():
    """Return metadata about the vault."""
    vault_root = Path(config.vault.path).expanduser().resolve()
    if not vault_root.exists():
        raise HTTPException(status_code=404, detail="Vault path not found")

    total_md = 0
    structure = {}
    for child in sorted(vault_root.iterdir()):
        if child.is_dir() and not child.name.startswith("."):
            md_count = len(list(child.glob("*.md")))
            structure[child.name] = {"files": md_count}
            total_md += md_count

    return {
        "vault_root": str(vault_root),
        "total_markdown_files": total_md,
        "structure": structure,
    }


@router.get("/files/search")
async def vault_search(
    q: str = Query(..., description="Search query (regex or plain text)", min_length=1),
    path: str = Query("notes", description="Subdirectory under vault to search"),
    max_results: int = Query(20, ge=1, le=100),
):
    """Search files in the vault by content (uses ripgrep)."""
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
    files_rel = [str(Path(f).relative_to(vault_root)) for f in files[:max_results]]

    return {
        "query": q,
        "path": path,
        "total": len(files),
        "results": files_rel,
    }


@router.get("/files/structure")
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


@router.get("/files/read")
async def vault_read(
    file: str = Query(..., description="File path relative to vault root"),
    offset: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    """Read a vault file with line numbers and pagination."""
    vault_root = Path(config.vault.path).expanduser().resolve()
    full_path = (vault_root / file).resolve()

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
    file: str
    content: str
    create_dirs: bool = True

    @field_validator("content")
    @classmethod
    def validate_content(cls, v):
        max_bytes = 1024 * 1024  # 1 MB
        if len(v.encode("utf-8")) > max_bytes:
            raise ValueError(f"Content too large (max {max_bytes // 1024} KB)")
        return v


@router.post("/files/write")
@limiter.limit(config.rate_limit.vault)
async def vault_write(request: Request, req: VaultWriteRequest):
    """Write content to a vault file (creates or overwrites)."""
    vault_root = Path(config.vault.path).expanduser().resolve()
    full_path = (vault_root / req.file).resolve()

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
