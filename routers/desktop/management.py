"""
Daemon lifecycle, session management, and utility endpoints.
"""
import subprocess
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from routers.desktop.core import cua_call, CUA_DRIVER, SESSION

router = APIRouter(tags=["Desktop"])


# ── Daemon ──────────────────────────────────────────────────────────

@router.post("/daemon/start")
async def daemon_start():
    """Start the cua-driver daemon (needed for stateful mouse/key operations)."""
    try:
        subprocess.Popen(
            [str(CUA_DRIVER), "serve", "--no-overlay", "--cursor-id", SESSION],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return {"status": "ok", "session": SESSION}
    except Exception as e:
        raise HTTPException(500, detail=f"Failed to start daemon: {e}")


@router.post("/daemon/stop")
async def daemon_stop():
    """Stop the cua-driver daemon."""
    try:
        subprocess.run([str(CUA_DRIVER), "stop"], capture_output=True, timeout=10)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, detail=f"Failed to stop daemon: {e}")


@router.get("/daemon/status")
async def daemon_status():
    """Check if cua-driver daemon is running."""
    result = subprocess.run(
        [str(CUA_DRIVER), "status"],
        capture_output=True, text=True, timeout=5,
    )
    running = "is running" in result.stdout
    parts = {}
    for line in result.stdout.strip().split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            parts[k.strip()] = v.strip()
    return {"running": running, "details": parts}


# ── Session ─────────────────────────────────────────────────────────

@router.post("/session/start")
async def session_start(session: Optional[str] = None):
    """Declare a named session (for stateful operations)."""
    sid = session or SESSION
    return cua_call("start_session", {"session": sid})


@router.post("/session/end")
async def session_end(session: Optional[str] = None):
    """End a named session and remove its cursor."""
    sid = session or SESSION
    return cua_call("end_session", {"session": sid})


# ── Utilities ───────────────────────────────────────────────────────

class SetValueRequest(BaseModel):
    element_index: int
    value: str


@router.post("/set-value")
async def set_element_value(req: SetValueRequest):
    """Set value of an AT-SPI element (form filling)."""
    cua_call("set_value", {"element_index": req.element_index, "value": req.value})
    return {"status": "ok", "element_index": req.element_index}


@router.post("/hide-cursor")
async def hide_agent_cursor():
    """Hide the agent cursor overlay."""
    cua_call("set_agent_cursor_enabled", {"enabled": False})
    return {"status": "ok", "cursor_visible": False}


@router.post("/show-cursor")
async def show_agent_cursor():
    """Show the agent cursor overlay."""
    cua_call("set_agent_cursor_enabled", {"enabled": True})
    return {"status": "ok", "cursor_visible": True}


@router.get("/driver-config")
async def driver_config():
    """Get cua-driver configuration."""
    return cua_call("get_config")


@router.get("/health-report")
async def driver_health():
    """Full cua-driver diagnostics report."""
    return cua_call("health_report")
