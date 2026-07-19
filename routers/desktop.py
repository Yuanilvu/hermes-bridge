"""
Desktop control router — Hermes Bridge v0.2.0
Tangan & mata untuk Wayland via cua-driver CLI.
"""
import json
import subprocess
import base64
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from auth import verify_api_key

router = APIRouter(
    prefix="/api/desktop",
    tags=["Desktop"],
    dependencies=[Depends(verify_api_key)],
)

CUA_DRIVER = Path.home() / ".local" / "bin" / "cua-driver"


def _cua_call(tool: str, args: Optional[dict] = None) -> dict:
    """Call cua-driver tool and return parsed JSON."""
    cmd = [str(CUA_DRIVER), "call", tool]
    if args:
        cmd.append(json.dumps(args))
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"cua-driver error: {result.stderr.strip() or result.stdout.strip()}",
            )
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"raw": result.stdout}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="cua-driver timed out")
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="cua-driver not found")


@router.get("/status")
async def desktop_status():
    """Check desktop availability — screen size, windows, cursor."""
    screen = _cua_call("get_screen_size")
    windows = _cua_call("list_windows")
    cursor = _cua_call("get_cursor_position")
    return {
        "screen": screen,
        "window_count": len(windows.get("windows", [])),
        "cursor": cursor,
        "driver_version": "0.6.8",
    }


@router.get("/screenshot")
async def screenshot():
    """Capture the full screen and return as base64 PNG."""
    screen = _cua_call("get_screen_size")
    w, h = screen.get("width", 1920), screen.get("height", 1080)

    try:
        result = subprocess.run(
            [str(CUA_DRIVER), "call", "zoom", json.dumps({"x1": 0, "y1": 0, "x2": w, "y2": h})],
            capture_output=True, timeout=30,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=502, detail=f"capture failed: {result.stderr.strip()}")
        data = json.loads(result.stdout)
        img_b64 = data.get("jpeg_base64", data.get("data", ""))
        return {
            "width": w,
            "height": h,
            "image": img_b64,
            "format": "jpeg",
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="capture timed out")


class ClickRequest(BaseModel):
    x: int
    y: int
    button: str = "left"


@router.post("/click")
async def click(req: ClickRequest):
    """Click at (x, y) coordinates."""
    result = _cua_call("click", {"x": req.x, "y": req.y, "button": req.button})
    return {"status": "ok", "position": {"x": req.x, "y": req.y}, "button": req.button}


class TypeRequest(BaseModel):
    text: str


@router.post("/type")
async def type_text(req: TypeRequest):
    """Type text at the focused window."""
    _cua_call("type_text", {"text": req.text})
    return {"status": "ok", "chars": len(req.text)}


class KeyRequest(BaseModel):
    keys: str


@router.post("/key")
async def press_key(req: KeyRequest):
    """Press a key combination (e.g. 'ctrl+shift+t', 'Return')."""
    _cua_call("hotkey", {"keys": req.keys})
    return {"status": "ok", "keys": req.keys}


@router.get("/cursor")
async def cursor_position():
    """Get current mouse cursor position."""
    return _cua_call("get_cursor_position")


@router.post("/cursor/{x}/{y}")
async def move_cursor(x: int, y: int):
    """Move cursor to (x, y)."""
    _cua_call("move_cursor", {"x": x, "y": y})
    return {"status": "ok", "position": {"x": x, "y": y}}


@router.get("/windows")
async def list_windows():
    """List visible X11 windows."""
    return _cua_call("list_windows")
