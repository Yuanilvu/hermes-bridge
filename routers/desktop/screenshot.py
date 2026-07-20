"""
Screenshot endpoints.
"""
import base64
import io
import logging
import os
import subprocess
import tempfile
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from routers.desktop.core import cua_call, get_guard_window_id
from rate_limit import limiter

logger = logging.getLogger("hermes-bridge.desktop")

router = APIRouter(tags=["Desktop"])


@router.get("/screenshot")
@limiter.limit("10/minute")
async def screenshot(request: Request):
    """Capture the full screen and return as base64 PNG.

    Uses mss (cross-platform screenshot) via X11/XWayland.
    Falls back to gnome-screenshot via systemd-run.
    """
    w, h = 1920, 1080

    # Method 1 — mss (cross-platform)
    try:
        import mss
        with mss.MSS() as sct:
            monitor = sct.monitors[0]
            im = sct.grab(monitor)
            w, h = im.size
            from PIL import Image
            pil_im = Image.frombytes("RGB", im.size, im.rgb)
            buf = io.BytesIO()
            pil_im.save(buf, format="PNG")
            img_b64 = base64.b64encode(buf.getvalue()).decode()
            return {"width": w, "height": h, "image": img_b64, "format": "png", "method": "mss"}
    except Exception as e:
        logger.warning(f"mss screenshot failed: {e}")

    # Method 2 — gnome-screenshot via systemd-run (Linux fallback)
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
    wid = window_id or get_guard_window_id()
    result = cua_call("zoom", {
        "window_id": wid,
        "x1": x1, "y1": y1,
        "x2": x2, "y2": y2,
    })
    return result
