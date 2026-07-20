"""
Desktop info endpoints — read-only queries for screen, cursor, windows, tree.
"""
from typing import Optional

from fastapi import APIRouter, Query
from routers.desktop.core import cua_call

router = APIRouter(tags=["Desktop"])


@router.get("/status")
async def desktop_status():
    """Check desktop availability — screen size, windows, cursor."""
    screen = cua_call("get_screen_size")
    windows = cua_call("list_windows")
    cursor = cua_call("get_cursor_position")
    return {
        "screen": screen,
        "window_count": len(windows.get("windows", [])),
        "cursor": cursor,
        "driver_version": "0.6.8",
    }


@router.get("/screen-size")
async def screen_size():
    """Get screen dimensions."""
    return cua_call("get_screen_size")


@router.get("/cursor")
async def cursor_position():
    """Get current mouse cursor position."""
    return cua_call("get_cursor_position")


@router.post("/cursor")
async def move_cursor(x: int = Query(...), y: int = Query(...)):
    """Move cursor to (x, y)."""
    cua_call("move_cursor", {"x": x, "y": y})
    return {"status": "ok", "position": {"x": x, "y": y}}


@router.get("/windows")
async def list_windows():
    """List visible X11 windows."""
    return cua_call("list_windows")


@router.get("/tree")
async def accessibility_tree():
    """Get accessibility tree (running processes + visible X11 windows)."""
    return cua_call("get_accessibility_tree")


@router.get("/window-state")
async def window_state(pid: Optional[int] = Query(None)):
    """Get AT-SPI structured elements for a window (or all windows)."""
    args = {}
    if pid:
        args["pid"] = pid
    return cua_call("get_window_state", args or None)
