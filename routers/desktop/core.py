"""
Shared helpers for desktop sub-modules.
"""
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, status

logger = logging.getLogger("hermes-bridge.desktop")

CUA_DRIVER = Path.home() / ".local" / "bin" / "cua-driver"
SESSION = "hermes-bridge"  # cua-driver daemon session id


def cua_call(tool: str, args: Optional[dict] = None) -> dict:
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


def get_desktop_pid() -> int:
    """Discover a usable PID for desktop interaction."""
    try:
        windows = cua_call("list_windows")
        for w in windows.get("windows", []):
            if w.get("title") == "mutter-x11-frames" and w.get("pid"):
                return w["pid"]
        for w in windows.get("windows", []):
            if w.get("pid"):
                return w["pid"]
    except Exception:
        pass
    # Fallback: try xdotool getactivewindow -> getwindowpid (Linux only)
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
    return int(os.getenv("HERMES_DESKTOP_PID", "5540"))


def get_guard_window_id() -> int:
    """Get the mutter guard window's window_id (full-screen overlay)."""
    try:
        windows = cua_call("list_windows")
        for w in windows.get("windows", []):
            if w.get("title") == "mutter guard window" and w.get("window_id"):
                return w["window_id"]
        for w in windows.get("windows", []):
            if w.get("title") == "Cua.AgentCursorOverlay.default" and w.get("window_id"):
                return w["window_id"]
    except Exception:
        pass
    return int(os.getenv("HERMES_GUARD_WINDOW_ID", "4194314"))


def desktop_context() -> dict:
    """Return pid + window_id for desktop-wide interaction."""
    return {"pid": get_desktop_pid(), "window_id": get_guard_window_id()}
