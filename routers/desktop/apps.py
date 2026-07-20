"""
Application management endpoints — launch, kill, list, focus.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from routers.desktop.core import cua_call

router = APIRouter(tags=["Desktop"])


class LaunchRequest(BaseModel):
    name: Optional[str] = None
    launch_path: Optional[str] = None
    urls: list[str] = []

class KillRequest(BaseModel):
    pid: int

class FocusRequest(BaseModel):
    pid: Optional[int] = None
    window_id: Optional[int] = None


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
    result = cua_call("launch_app", args)
    return {"status": "ok", **args, "result": result}


@router.post("/kill")
async def kill_app(req: KillRequest):
    """Force-terminate a process by PID."""
    cua_call("kill_app", {"pid": req.pid})
    return {"status": "ok", "pid": req.pid, "action": "killed"}


@router.get("/apps")
async def list_apps():
    """List running + installed apps."""
    return cua_call("list_apps")


@router.post("/focus")
async def focus_window(req: FocusRequest):
    """Bring a window to front."""
    args = {}
    if req.pid:
        args["pid"] = req.pid
    if req.window_id:
        args["window_id"] = req.window_id
    if not args:
        raise HTTPException(400, "Provide 'pid' or 'window_id'")
    try:
        cua_call("bring_to_front", args)
        return {"status": "ok", **args}
    except HTTPException as e:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Window focus is not available on Linux (Wayland). "
                   f"Alternative: click on the window coordinates to activate it. "
                   f"Error: {e.detail}",
        )
