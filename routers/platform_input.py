"""
Cross-platform input backend — Hermes Bridge
Abstraksi untuk key hold/release & mouse move relative.

Linux   → xdotool (existing)
Windows → pyautogui / ctypes
macOS   → pyautogui / osascript
"""
import logging
import platform
import subprocess
import sys
from typing import Optional

logger = logging.getLogger("hermes-bridge.input")

SYSTEM = platform.system().lower()  # 'linux', 'windows', 'darwin'


def _xdotool_available() -> bool:
    """Check if xdotool binary exists."""
    try:
        subprocess.run(["xdotool", "--version"], capture_output=True, timeout=3)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _load_pyautogui():
    """Lazy-import pyautogui. Returns None if unavailable."""
    if "pyautogui" not in sys.modules:
        try:
            import pyautogui
            pyautogui.FAILSAFE = False  # disable corner-fail for API usage
            sys.modules["pyautogui"] = pyautogui
        except ImportError:
            return None
    return sys.modules["pyautogui"]


# ── Key hold / release ──────────────────────────────────────────────

def key_down(key: str):
    """Press and hold a key. Returns (body_dict, http_status_or_None)."""
    if SYSTEM == "linux" and _xdotool_available():
        return _xdotool_keydown(key)
    if SYSTEM == "linux":
        return {"error": "xdotool not installed (sudo apt-get install xdotool)"}, 503
    # Windows / macOS → pyautogui
    pg = _load_pyautogui()
    if pg:
        try:
            pg.keyDown(key)
            return {"status": "ok", "key": key, "action": "keydown"}, None
        except Exception as e:
            return {"error": f"pyautogui keyDown failed: {e}"}, 500
    return {"error": f"No key-down backend available for {SYSTEM}"}, 501


def key_up(key: str):
    """Release a previously-held key. Returns (body_dict, http_status_or_None)."""
    if SYSTEM == "linux" and _xdotool_available():
        return _xdotool_keyup(key)
    if SYSTEM == "linux":
        return {"error": "xdotool not installed (sudo apt-get install xdotool)"}, 503
    pg = _load_pyautogui()
    if pg:
        try:
            pg.keyUp(key)
            return {"status": "ok", "key": key, "action": "keyup"}, None
        except Exception as e:
            return {"error": f"pyautogui keyUp failed: {e}"}, 500
    return {"error": f"No key-up backend available for {SYSTEM}"}, 501


def mouse_move_relative(dx: int, dy: int):
    """Move cursor relative to current position."""
    if SYSTEM == "linux" and _xdotool_available():
        return _xdotool_mousemove_relative(dx, dy)
    if SYSTEM == "linux":
        return {"error": "xdotool not installed (sudo apt-get install xdotool)"}, 503
    pg = _load_pyautogui()
    if pg:
        try:
            pg.moveRel(dx, dy)
            return {"status": "ok", "dx": dx, "dy": dy}, None
        except Exception as e:
            return {"error": f"pyautogui moveRel failed: {e}"}, 500
    return {"error": f"No mouse-move-relative backend available for {SYSTEM}"}, 501


# ── Linux xdotool backends ──────────────────────────────────────────

def _xdotool_keydown(key: str) -> dict:
    try:
        subprocess.run(
            ["xdotool", "keydown", key],
            capture_output=True, text=True, timeout=5,
        )
        return {"status": "ok", "key": key, "action": "keydown"}, None
    except subprocess.TimeoutExpired:
        return {"error": "xdotool keydown timed out"}, 504
    except Exception as e:
        return {"error": f"xdotool keydown failed: {e}"}, 500


def _xdotool_keyup(key: str) -> dict:
    try:
        subprocess.run(
            ["xdotool", "keyup", key],
            capture_output=True, text=True, timeout=5,
        )
        return {"status": "ok", "key": key, "action": "keyup"}, None
    except subprocess.TimeoutExpired:
        return {"error": "xdotool keyup timed out"}, 504
    except Exception as e:
        return {"error": f"xdotool keyup failed: {e}"}, 500


def _xdotool_mousemove_relative(dx: int, dy: int) -> dict:
    try:
        subprocess.run(
            ["xdotool", "mousemove_relative", "--", str(dx), str(dy)],
            capture_output=True, text=True, timeout=5,
        )
        return {"status": "ok", "dx": dx, "dy": dy}, None
    except subprocess.TimeoutExpired:
        return {"error": "xdotool mousemove_relative timed out"}, 504
    except Exception as e:
        return {"error": f"xdotool mousemove_relative failed: {e}"}, 500
