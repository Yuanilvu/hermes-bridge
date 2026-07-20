"""
Keyboard & text input endpoints.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from routers.desktop.core import cua_call, get_desktop_pid
from routers.platform_input import (
    key_down as pi_key_down,
    key_up as pi_key_up,
    mouse_move_relative as pi_mouse_move_relative,
)

router = APIRouter(tags=["Desktop"])


# ── Models ──────────────────────────────────────────────────────────

class TypeRequest(BaseModel):
    text: str
    pid: Optional[int] = None

class TypeSlowRequest(BaseModel):
    text: str
    delay_ms: int = 30
    pid: Optional[int] = None

class KeyRequest(BaseModel):
    keys: str = ""
    key_sequence: list[str] = []
    pid: Optional[int] = None

class SingleKeyRequest(BaseModel):
    key: str
    pid: Optional[int] = None

class KeyHoldRequest(BaseModel):
    key: str

class MouseMoveRelativeRequest(BaseModel):
    dx: int
    dy: int


# ── Type text ───────────────────────────────────────────────────────

@router.post("/type")
async def type_text(req: TypeRequest):
    """Type text at the focused window."""
    pid = req.pid or get_desktop_pid()
    result = cua_call("type_text", {"pid": pid, "text": req.text})
    return {"status": "ok", "chars": len(req.text), "result": result}


@router.post("/type-slow")
async def type_text_slow(req: TypeSlowRequest):
    """Type text character-by-character with configurable delay."""
    pid = req.pid or get_desktop_pid()
    result = cua_call("type_text_chars", {"pid": pid, "text": req.text, "delay_ms": req.delay_ms})
    return {"status": "ok", "chars": len(req.text), "delay_ms": req.delay_ms, "result": result}


# ── Key combos ──────────────────────────────────────────────────────

@router.post("/key")
async def press_key(req: KeyRequest):
    """Press a key combination (e.g. 'ctrl+shift+t', 'Return')."""
    pid = req.pid or get_desktop_pid()
    if req.key_sequence:
        args = {"pid": pid, "keys": req.key_sequence}
    elif req.keys:
        parts = req.keys.split("+")
        args = {"pid": pid, "keys": parts if len(parts) > 1 else [req.keys]}
    else:
        raise HTTPException(400, "Provide 'keys' (str) or 'key_sequence' (list[str])")
    cua_call("hotkey", args)
    return {"status": "ok", "keys": req.keys or req.key_sequence}


@router.post("/press-key")
async def press_single_key(req: SingleKeyRequest):
    """Press a single key (tap — press then release)."""
    pid = req.pid or get_desktop_pid()
    cua_call("press_key", {"pid": pid, "key": req.key})
    return {"status": "ok", "key": req.key}


# ── Key hold / release (cross-platform) ─────────────────────────────

@router.post("/key-down")
async def key_down(req: KeyHoldRequest):
    """Press and hold a key (gaming — WASD movement, etc).

    Backend: Linux → xdotool, Windows/macOS → pyautogui.
    """
    body, status_code = pi_key_down(req.key)
    if status_code:
        raise HTTPException(status_code=status_code, detail=body["error"])
    return body


@router.post("/key-up")
async def key_up(req: KeyHoldRequest):
    """Release a previously-held key.

    Backend: Linux → xdotool, Windows/macOS → pyautogui.
    """
    body, status_code = pi_key_up(req.key)
    if status_code:
        raise HTTPException(status_code=status_code, detail=body["error"])
    return body


@router.post("/mouse-move-relative")
async def mouse_move_relative(req: MouseMoveRelativeRequest):
    """Move cursor relative to current position (camera look in games).

    Backend: Linux → xdotool, Windows/macOS → pyautogui.
    """
    body, status_code = pi_mouse_move_relative(req.dx, req.dy)
    if status_code:
        raise HTTPException(status_code=status_code, detail=body["error"])
    return body
