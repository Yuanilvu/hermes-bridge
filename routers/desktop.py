"""
Desktop control router -- Hermes Bridge v0.2.1
Tangan & mata untuk Wayland via cua-driver CLI.

Menyediakan ~30 endpoint untuk kontrol desktop penuh:
mouse, keyboard, scroll, drag, apps, accessibility, screenshot.
"""
import json
import logging
import os
import subprocess
import base64
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from routers.platform_input import key_down as _pi_key_down, key_up as _pi_key_up, mouse_move_relative as _pi_mouse_move_relative

from auth import verify_api_key
from config_loader import config
from rate_limit import limiter

router = APIRouter(
    prefix="/api/desktop",
    tags=["Desktop"],
    dependencies=[Depends(verify_api_key)],
)

CUA_DRIVER = Path.home() / ".local" / "bin" / "cua-driver"
logger = logging.getLogger("hermes-bridge.desktop")


# ─── helpers ───────────────────────────────────────────────────────────────

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
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"raw": result.stdout.strip()}
    except json.JSONDecodeError:
        return {"raw": result.stdout}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="cua-driver timed out")
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="cua-driver not found")


def _get_desktop_pid() -> int:
    """Discover a usable PID for desktop interaction."""
    try:
        windows = _cua_call("list_windows")
        for w in windows.get("windows", []):
            if w.get("title") == "mutter-x11-frames" and w.get("pid"):
                return w["pid"]
        for w in windows.get("windows", []):
            if w.get("pid"):
                return w["pid"]
    except Exception:
        pass
    # Fallback: try xdotool getactivewindow -> getwindowpid
    try:
        wid = subprocess.run(
            ["xdotool", "getactivewindow"],
            capture_output=True, text=True, timeout=3,
        )
        if wid.returncode == 0 and wid.stdout.strip().isdigit():
            pid = subprocess.run(
                ["xdotool", "getwindowpid", wid.stdout.strip()],
                capture_output=True, text=True, timeout=3,
            )
            if pid.returncode == 0 and pid.stdout.strip().isdigit():
                return int(pid.stdout.strip())
    except Exception:
        pass
    # Ultimate fallback: env var or hardcoded default
    return int(os.getenv("HERMES_DESKTOP_PID", "5540"))


def _get_guard_window_id() -> int:
    """Get the mutter guard window's window_id (full-screen overlay)."""
    try:
        windows = _cua_call("list_windows")
        for w in windows.get("windows", []):
            if w.get("title") == "mutter guard window" and w.get("window_id"):
                return w["window_id"]
        for w in windows.get("windows", []):
            if w.get("title") == "Cua.AgentCursorOverlay.default" and w.get("window_id"):
                return w["window_id"]
    except Exception:
        pass
    return int(os.getenv("HERMES_GUARD_WINDOW_ID", "4194314"))


def _desktop_context() -> dict:
    """Return pid + window_id for desktop-wide interaction."""
    return {"pid": _get_desktop_pid(), "window_id": _get_guard_window_id()}


SESSION = "hermes-bridge"  # cua-driver daemon session id


# ─── info ──────────────────────────────────────────────────────────────────

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


@router.get("/screen-size")
async def screen_size():
    """Get screen dimensions."""
    return _cua_call("get_screen_size")


@router.get("/cursor")
async def cursor_position():
    """Get current mouse cursor position."""
    return _cua_call("get_cursor_position")


@router.post("/cursor")
async def move_cursor(x: int = Query(...), y: int = Query(...)):
    """Move cursor to (x, y)."""
    _cua_call("move_cursor", {"x": x, "y": y})
    return {"status": "ok", "position": {"x": x, "y": y}}


@router.get("/windows")
async def list_windows():
    """List visible X11 windows."""
    return _cua_call("list_windows")


@router.get("/tree")
async def accessibility_tree():
    """Get accessibility tree (running processes + visible X11 windows)."""
    return _cua_call("get_accessibility_tree")


@router.get("/window-state")
async def window_state(pid: Optional[int] = Query(None)):
    """Get AT-SPI structured elements for a window (or all windows)."""
    args = {}
    if pid:
        args["pid"] = pid
    return _cua_call("get_window_state", args or None)


# ─── screenshot ────────────────────────────────────────────────────────────

@router.get("/screenshot")
@limiter.limit(config.rate_limit.desktop)
async def screenshot(request: Request):
    """Capture the full screen and return as base64 PNG.
    
    Uses mss (cross-platform screenshot) via X11/XWayland.
    Falls back to gnome-screenshot via systemd-run.
    """
    w, h = 1920, 1080

    # Method 1 — mss
    try:
        import mss
        with mss.MSS() as sct:
            monitor = sct.monitors[0]
            im = sct.grab(monitor)
            w, h = im.size
            import io
            from PIL import Image
            pil_im = Image.frombytes("RGB", im.size, im.rgb)
            buf = io.BytesIO()
            pil_im.save(buf, format="PNG")
            img_b64 = base64.b64encode(buf.getvalue()).decode()
            return {
                "width": w, "height": h,
                "image": img_b64, "format": "png",
                "method": "mss",
            }
    except Exception as e:
        logger.warning(f"mss screenshot failed: {e}")

    # Method 2 — gnome-screenshot via systemd-run
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        result = subprocess.run(
            [
                "systemd-run", "--user", "--machine=yuan@", "--quiet", "--collect",
                "--wait",
                "gnome-screenshot", "-f", tmp.name,
            ],
            capture_output=True, timeout=10,
            env={
                "DISPLAY": ":0",
                "WAYLAND_DISPLAY": "wayland-0",
                "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
                "XDG_RUNTIME_DIR": "/run/user/1000",
                "HOME": "/home/yuan",
            },
        )
        if result.returncode == 0 and os.path.exists(tmp.name) and os.path.getsize(tmp.name) > 100:
            with open(tmp.name, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            os.unlink(tmp.name)
            return {"width": w, "height": h, "image": img_b64, "format": "png", "method": "gnome-screenshot-via-systemd-run"}
        logger.warning(f"gnome-screenshot failed: rc={result.returncode}")
        try: os.unlink(tmp.name)
        except: pass
    except Exception as e:
        logger.warning(f"gnome-screenshot via systemd-run exception: {e}")
        try: os.unlink(tmp.name) if os.path.exists(tmp.name) else None
        except: pass

    raise HTTPException(status_code=502, detail="No screenshot method available")


@router.post("/zoom")
async def zoom_region(x1: int = Query(...), y1: int = Query(...),
                      x2: int = Query(...), y2: int = Query(...),
                      window_id: Optional[int] = Query(None)):
    """Capture a cropped JPEG region of a window (10-80% of screen works best)."""
    wid = window_id or _get_guard_window_id()
    result = _cua_call("zoom", {
        "window_id": wid,
        "x1": x1, "y1": y1,
        "x2": x2, "y2": y2,
    })
    # zoom returns base64 JPEG
    return result


# ─── click ─────────────────────────────────────────────────────────────────

class ClickRequest(BaseModel):
    x: int
    y: int
    button: str = "left"
    pid: Optional[int] = None
    window_id: Optional[int] = None


@router.post("/click")
async def click(req: ClickRequest):
    """Click at (x, y) coordinates. button: left|right|middle."""
    ctx = _desktop_context()
    pid = req.pid or ctx["pid"]
    wid = req.window_id or ctx["window_id"]
    if req.button == "right":
        _cua_call("right_click", {"pid": pid, "window_id": wid, "x": req.x, "y": req.y})
    elif req.button == "middle":
        _cua_call("click", {"pid": pid, "window_id": wid, "x": req.x, "y": req.y, "button": "middle"})
    else:
        _cua_call("click", {"pid": pid, "window_id": wid, "x": req.x, "y": req.y, "button": "left"})
    return {"status": "ok", "position": {"x": req.x, "y": req.y}, "button": req.button}


class DoubleClickRequest(BaseModel):
    x: int
    y: int
    pid: Optional[int] = None
    window_id: Optional[int] = None


@router.post("/double-click")
async def double_click(req: DoubleClickRequest):
    """Double-click at (x, y)."""
    ctx = _desktop_context()
    pid = req.pid or ctx["pid"]
    wid = req.window_id or ctx["window_id"]
    _cua_call("double_click", {"pid": pid, "window_id": wid, "x": req.x, "y": req.y})
    return {"status": "ok", "position": {"x": req.x, "y": req.y}, "action": "double_click"}


class RightClickRequest(BaseModel):
    x: int
    y: int
    pid: Optional[int] = None
    window_id: Optional[int] = None


@router.post("/right-click")
async def right_click(req: RightClickRequest):
    """Right-click at (x, y)."""
    ctx = _desktop_context()
    pid = req.pid or ctx["pid"]
    wid = req.window_id or ctx["window_id"]
    _cua_call("right_click", {"pid": pid, "window_id": wid, "x": req.x, "y": req.y})
    return {"status": "ok", "position": {"x": req.x, "y": req.y}, "action": "right_click"}


class MouseDownRequest(BaseModel):
    x: int
    y: int
    button: str = "left"
    pid: Optional[int] = None
    window_id: Optional[int] = None


@router.post("/mouse-down")
async def mouse_button_down(req: MouseDownRequest):
    """Press and hold a mouse button at (x,y) — for drag & gaming."""
    ctx = _desktop_context()
    pid = req.pid or ctx["pid"]
    wid = req.window_id or ctx["window_id"]
    _cua_call("mouse_button_down", {"pid": pid, "window_id": wid, "x": req.x, "y": req.y, "button": req.button, "session": SESSION})
    return {"status": "ok", "position": {"x": req.x, "y": req.y}, "button": req.button, "action": "down"}


class MouseUpRequest(BaseModel):
    pid: Optional[int] = None
    window_id: Optional[int] = None


@router.post("/mouse-up")
async def mouse_button_up(req: MouseUpRequest):
    """Release a previously-held mouse button."""
    ctx = _desktop_context()
    pid = req.pid or ctx["pid"]
    wid = req.window_id or ctx["window_id"]
    _cua_call("mouse_button_up", {"pid": pid, "window_id": wid, "session": SESSION})
    return {"status": "ok", "action": "up"}


class MouseDragRequest(BaseModel):
    to_x: int
    to_y: int
    pid: Optional[int] = None
    window_id: Optional[int] = None


@router.post("/mouse-drag")
async def mouse_drag(req: MouseDragRequest):
    """Move cursor while holding mouse button (after mouse-down)."""
    ctx = _desktop_context()
    pid = req.pid or ctx["pid"]
    wid = req.window_id or ctx["window_id"]
    _cua_call("mouse_drag", {"pid": pid, "window_id": wid, "x": req.to_x, "y": req.to_y, "session": SESSION})
    return {"status": "ok", "to": {"x": req.to_x, "y": req.to_y}}


class DragRequest(BaseModel):
    from_x: int
    from_y: int
    to_x: int
    to_y: int
    pid: Optional[int] = None
    window_id: Optional[int] = None


@router.post("/drag")
async def drag(req: DragRequest):
    """Press-drag-release gesture from (from_x,from_y) to (to_x,to_y)."""
    ctx = _desktop_context()
    pid = req.pid or ctx["pid"]
    wid = req.window_id or ctx["window_id"]
    _cua_call("drag", {
        "pid": pid, "window_id": wid,
        "from_x": req.from_x, "from_y": req.from_y,
        "to_x": req.to_x, "to_y": req.to_y,
    })
    return {"status": "ok", "from": {"x": req.from_x, "y": req.from_y}, "to": {"x": req.to_x, "y": req.to_y}}


class ParallelDragItem(BaseModel):
    from_x: Optional[float] = None
    from_y: Optional[float] = None
    to_x: Optional[float] = None
    to_y: Optional[float] = None
    fn: Optional[str] = None  # math expression y(x), e.g. "300+120*sin(x/40)"
    x_from: Optional[float] = None
    x_to: Optional[float] = None
    path: Optional[list[list[float]]] = None  # explicit waypoints
    button: str = "left"
    duration_ms: int = 500
    samples: int = 80
    steps: Optional[int] = None


class ParallelDragRequest(BaseModel):
    drags: list[ParallelDragItem] = Field(..., min_length=2, description="2+ drag gestures to run concurrently")
    pid: Optional[int] = None
    window_id: Optional[int] = None


@router.post("/parallel-drag")
async def parallel_drag(req: ParallelDragRequest):
    """Run multiple mouse drag gestures concurrently via MPX/XI2 (gaming).

    Each drag runs on its own virtual master pointer — true concurrent input.
    Supply 2+ drags. Each drag can be:
    - Straight segment: from_x/from_y → to_x/to_y
    - Math function: fn=y(x) with x_from/x_to domain
    - Explicit waypoints: path=[[x,y],...]
    Requires cua-driver daemon running (starts automatically).
    """
    ctx = _desktop_context()
    pid = req.pid or ctx["pid"]
    wid = req.window_id or ctx["window_id"]
    if len(req.drags) < 2:
        raise HTTPException(400, "parallel-drag needs at least 2 drags")

    drag_items = []
    for d in req.drags:
        item = {"session": SESSION, "window_id": wid, "pid": pid,
                "button": d.button, "duration_ms": d.duration_ms}
        if d.path:
            item["path"] = d.path
        elif d.fn:
            item["fn"] = d.fn
            item["samples"] = d.samples
            if d.x_from is not None: item["x_from"] = d.x_from
            if d.x_to is not None: item["x_to"] = d.x_to
        else:
            item["from_x"] = d.from_x or 0
            item["from_y"] = d.from_y or 0
            item["to_x"] = d.to_x or 100
            item["to_y"] = d.to_y or 100
        if d.steps is not None: item["steps"] = d.steps
        drag_items.append(item)

    _cua_call("parallel_mouse_drag", {"drags": drag_items})
    return {"status": "ok", "drag_count": len(req.drags)}


# ─── scroll ────────────────────────────────────────────────────────────────

class ScrollRequest(BaseModel):
    direction: str = "down"  # up|down|left|right
    amount: int = 3  # scroll ticks
    pid: Optional[int] = None


@router.post("/scroll")
async def scroll(req: ScrollRequest):
    """Scroll the focused region.
    
    direction: up|down|left|right
    amount: number of scroll ticks (default 3)
    """
    pid = req.pid or _get_desktop_pid()
    _cua_call("scroll", {
        "pid": pid,
        "direction": req.direction,
        "amount": req.amount,
    })
    return {"status": "ok", "direction": req.direction, "amount": req.amount}


# ─── keyboard ──────────────────────────────────────────────────────────────

class TypeRequest(BaseModel):
    text: str
    pid: Optional[int] = None


@router.post("/type")
async def type_text(req: TypeRequest):
    """Type text at the focused window."""
    pid = req.pid or _get_desktop_pid()
    result = _cua_call("type_text", {"pid": pid, "text": req.text})
    return {"status": "ok", "chars": len(req.text), "result": result}


class TypeSlowRequest(BaseModel):
    text: str
    delay_ms: int = 30
    pid: Optional[int] = None


@router.post("/type-slow")
async def type_text_slow(req: TypeSlowRequest):
    """Type text character-by-character with configurable delay (gaming/input)."""
    pid = req.pid or _get_desktop_pid()
    result = _cua_call("type_text_chars", {"pid": pid, "text": req.text, "delay_ms": req.delay_ms})
    return {"status": "ok", "chars": len(req.text), "delay_ms": req.delay_ms, "result": result}


class KeyRequest(BaseModel):
    """Key press request. Accepts either:
    - keys: str (e.g. "ctrl+shift+t") — simple key combo string
    - key_sequence: list[str] (e.g. ["ctrl","c"]) — individual key array
    """
    keys: str = ""
    key_sequence: list[str] = []
    pid: Optional[int] = None


@router.post("/key")
async def press_key(req: KeyRequest):
    """Press a key combination (e.g. 'ctrl+shift+t', 'Return')."""
    pid = req.pid or _get_desktop_pid()
    if req.key_sequence:
        args = {"pid": pid, "keys": req.key_sequence}
    elif req.keys:
        parts = req.keys.split("+")
        args = {"pid": pid, "keys": parts if len(parts) > 1 else [req.keys]}
    else:
        raise HTTPException(400, "Provide 'keys' (str) or 'key_sequence' (list[str])")
    _cua_call("hotkey", args)
    return {"status": "ok", "keys": req.keys or req.key_sequence}


class SingleKeyRequest(BaseModel):
    key: str
    pid: Optional[int] = None


@router.post("/press-key")
async def press_single_key(req: SingleKeyRequest):
    """Press a single key (tap — press then release)."""
    pid = req.pid or _get_desktop_pid()
    _cua_call("press_key", {"pid": pid, "key": req.key})
    return {"status": "ok", "key": req.key}


# ─── key hold / release (gaming) ─────────────────────────────────────────


class KeyHoldRequest(BaseModel):
    key: str  # single key name (e.g. "w", "Shift_L")


@router.post("/key-down")
async def key_down(req: KeyHoldRequest):
    """Press and hold a key (for gaming — WASD movement, sprint, etc).

    Backend: Linux → xdotool, Windows/macOS → pyautogui.
    Call key-up to release.
    """
    body, status_code = _pi_key_down(req.key)
    if status_code:
        raise HTTPException(status_code=status_code, detail=body["error"])
    return body


@router.post("/key-up")
async def key_up(req: KeyHoldRequest):
    """Release a previously-held key (gaming).

    Backend: Linux → xdotool, Windows/macOS → pyautogui.
    """
    body, status_code = _pi_key_up(req.key)
    if status_code:
        raise HTTPException(status_code=status_code, detail=body["error"])
    return body


class MouseMoveRelativeRequest(BaseModel):
    dx: int
    dy: int


@router.post("/mouse-move-relative")
async def mouse_move_relative(req: MouseMoveRelativeRequest):
    """Move cursor relative to current position (for camera look in games).

    Backend: Linux → xdotool, Windows/macOS → pyautogui.
    Positive dx = right, positive dy = down.
    """
    body, status_code = _pi_mouse_move_relative(req.dx, req.dy)
    if status_code:
        raise HTTPException(status_code=status_code, detail=body["error"])
    return body


# ─── apps ──────────────────────────────────────────────────────────────────

class LaunchRequest(BaseModel):
    name: Optional[str] = None  # app name e.g. "firefox", "nautilus"
    launch_path: Optional[str] = None  # full path e.g. "/usr/bin/code"
    urls: list[str] = []  # URLs to open


@router.post("/launch")
async def launch_app(req: LaunchRequest):
    """Launch an application in the background.
    
    Provide one of: name (e.g. "firefox"), launch_path (e.g. "/usr/bin/code"), or urls.
    """
    args = {}
    if req.name:
        args["name"] = req.name
    if req.launch_path:
        args["launch_path"] = req.launch_path
    if req.urls:
        args["urls"] = req.urls
    if not args:
        raise HTTPException(400, "Provide 'name', 'launch_path', or 'urls'")
    result = _cua_call("launch_app", args)
    return {"status": "ok", **args, "result": result}


class KillRequest(BaseModel):
    pid: int


@router.post("/kill")
async def kill_app(req: KillRequest):
    """Force-terminate a process by PID."""
    _cua_call("kill_app", {"pid": req.pid})
    return {"status": "ok", "pid": req.pid, "action": "killed"}


@router.get("/apps")
async def list_apps():
    """List running + installed apps."""
    return _cua_call("list_apps")


class FocusRequest(BaseModel):
    pid: Optional[int] = None
    window_id: Optional[int] = None


@router.post("/focus")
async def focus_window(req: FocusRequest):
    """Bring a window to front (Linux: not supported by cua-driver, use click instead)."""
    args = {}
    if req.pid:
        args["pid"] = req.pid
    if req.window_id:
        args["window_id"] = req.window_id
    if not args:
        raise HTTPException(400, "Provide 'pid' or 'window_id'")
    try:
        _cua_call("bring_to_front", args)
        return {"status": "ok", **args}
    except HTTPException as e:
        # On Linux, bring_to_front isn't available — return actionable hint
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Window focus is not available on Linux (Wayland). "
                   f"Alternative: click on the window coordinates to activate it. "
                   f"Error: {e.detail}",
        )


# ─── daemon ─────────────────────────────────────────────────────────────────

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


@router.post("/session/start")
async def session_start(session: Optional[str] = None):
    """Declare a named session (for stateful operations)."""
    sid = session or SESSION
    return _cua_call("start_session", {"session": sid})


@router.post("/session/end")
async def session_end(session: Optional[str] = None):
    """End a named session and remove its cursor."""
    sid = session or SESSION
    return _cua_call("end_session", {"session": sid})


# ─── utilities ─────────────────────────────────────────────────────────────

class SetValueRequest(BaseModel):
    element_index: int
    value: str


@router.post("/set-value")
async def set_element_value(req: SetValueRequest):
    """Set value of an AT-SPI element (form filling)."""
    _cua_call("set_value", {"element_index": req.element_index, "value": req.value})
    return {"status": "ok", "element_index": req.element_index}


@router.post("/hide-cursor")
async def hide_agent_cursor():
    """Hide the agent cursor overlay."""
    _cua_call("set_agent_cursor_enabled", {"enabled": False})
    return {"status": "ok", "cursor_visible": False}


@router.post("/show-cursor")
async def show_agent_cursor():
    """Show the agent cursor overlay."""
    _cua_call("set_agent_cursor_enabled", {"enabled": True})
    return {"status": "ok", "cursor_visible": True}


@router.get("/driver-config")
async def driver_config():
    """Get cua-driver configuration."""
    return _cua_call("get_config")


@router.get("/health-report")
async def driver_health():
    """Full cua-driver diagnostics report."""
    return _cua_call("health_report")
