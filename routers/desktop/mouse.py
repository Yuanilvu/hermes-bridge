"""
Mouse & scroll endpoints.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from routers.desktop.core import cua_call, desktop_context, get_desktop_pid, SESSION

router = APIRouter(tags=["Desktop"])


# ── Models ──────────────────────────────────────────────────────────

class ClickRequest(BaseModel):
    x: int
    y: int
    button: str = "left"
    pid: Optional[int] = None
    window_id: Optional[int] = None

class DoubleClickRequest(BaseModel):
    x: int
    y: int
    pid: Optional[int] = None
    window_id: Optional[int] = None

class RightClickRequest(BaseModel):
    x: int
    y: int
    pid: Optional[int] = None
    window_id: Optional[int] = None

class MouseDownRequest(BaseModel):
    x: int
    y: int
    button: str = "left"
    pid: Optional[int] = None
    window_id: Optional[int] = None

class MouseUpRequest(BaseModel):
    pid: Optional[int] = None
    window_id: Optional[int] = None

class MouseDragRequest(BaseModel):
    to_x: int
    to_y: int
    pid: Optional[int] = None
    window_id: Optional[int] = None

class DragRequest(BaseModel):
    from_x: int
    from_y: int
    to_x: int
    to_y: int
    pid: Optional[int] = None
    window_id: Optional[int] = None

class ParallelDragItem(BaseModel):
    from_x: Optional[float] = None
    from_y: Optional[float] = None
    to_x: Optional[float] = None
    to_y: Optional[float] = None
    fn: Optional[str] = None
    x_from: Optional[float] = None
    x_to: Optional[float] = None
    path: Optional[list[list[float]]] = None
    button: str = "left"
    duration_ms: int = 500
    samples: int = 80
    steps: Optional[int] = None

class ParallelDragRequest(BaseModel):
    drags: list[ParallelDragItem] = Field(..., min_length=2, description="2+ drag gestures to run concurrently")
    pid: Optional[int] = None
    window_id: Optional[int] = None

class ScrollRequest(BaseModel):
    direction: str = "down"
    amount: int = 3
    pid: Optional[int] = None


# ── Click ───────────────────────────────────────────────────────────

@router.post("/click")
async def click(req: ClickRequest):
    """Click at (x, y) coordinates. button: left|right|middle."""
    ctx = desktop_context()
    pid = req.pid or ctx["pid"]
    wid = req.window_id or ctx["window_id"]
    if req.button == "right":
        cua_call("right_click", {"pid": pid, "window_id": wid, "x": req.x, "y": req.y})
    elif req.button == "middle":
        cua_call("click", {"pid": pid, "window_id": wid, "x": req.x, "y": req.y, "button": "middle"})
    else:
        cua_call("click", {"pid": pid, "window_id": wid, "x": req.x, "y": req.y, "button": "left"})
    return {"status": "ok", "position": {"x": req.x, "y": req.y}, "button": req.button}


@router.post("/double-click")
async def double_click(req: DoubleClickRequest):
    """Double-click at (x, y)."""
    ctx = desktop_context()
    pid = req.pid or ctx["pid"]
    wid = req.window_id or ctx["window_id"]
    cua_call("double_click", {"pid": pid, "window_id": wid, "x": req.x, "y": req.y})
    return {"status": "ok", "position": {"x": req.x, "y": req.y}, "action": "double_click"}


@router.post("/right-click")
async def right_click(req: RightClickRequest):
    """Right-click at (x, y)."""
    ctx = desktop_context()
    pid = req.pid or ctx["pid"]
    wid = req.window_id or ctx["window_id"]
    cua_call("right_click", {"pid": pid, "window_id": wid, "x": req.x, "y": req.y})
    return {"status": "ok", "position": {"x": req.x, "y": req.y}, "action": "right_click"}


# ── Mouse button hold / release / drag ──────────────────────────────

@router.post("/mouse-down")
async def mouse_button_down(req: MouseDownRequest):
    """Press and hold a mouse button at (x,y) — for drag & gaming."""
    ctx = desktop_context()
    pid = req.pid or ctx["pid"]
    wid = req.window_id or ctx["window_id"]
    cua_call("mouse_button_down", {"pid": pid, "window_id": wid, "x": req.x, "y": req.y, "button": req.button, "session": SESSION})
    return {"status": "ok", "position": {"x": req.x, "y": req.y}, "button": req.button, "action": "down"}


@router.post("/mouse-up")
async def mouse_button_up(req: MouseUpRequest):
    """Release a previously-held mouse button."""
    ctx = desktop_context()
    pid = req.pid or ctx["pid"]
    wid = req.window_id or ctx["window_id"]
    cua_call("mouse_button_up", {"pid": pid, "window_id": wid, "session": SESSION})
    return {"status": "ok", "action": "up"}


@router.post("/mouse-drag")
async def mouse_drag(req: MouseDragRequest):
    """Move cursor while holding mouse button (after mouse-down)."""
    ctx = desktop_context()
    pid = req.pid or ctx["pid"]
    wid = req.window_id or ctx["window_id"]
    cua_call("mouse_drag", {"pid": pid, "window_id": wid, "x": req.to_x, "y": req.to_y, "session": SESSION})
    return {"status": "ok", "to": {"x": req.to_x, "y": req.to_y}}


@router.post("/drag")
async def drag(req: DragRequest):
    """Press-drag-release gesture from (from_x,from_y) to (to_x,to_y)."""
    ctx = desktop_context()
    pid = req.pid or ctx["pid"]
    wid = req.window_id or ctx["window_id"]
    cua_call("drag", {
        "pid": pid, "window_id": wid,
        "from_x": req.from_x, "from_y": req.from_y,
        "to_x": req.to_x, "to_y": req.to_y,
    })
    return {"status": "ok", "from": {"x": req.from_x, "y": req.from_y}, "to": {"x": req.to_x, "y": req.to_y}}


@router.post("/parallel-drag")
async def parallel_drag(req: ParallelDragRequest):
    """Run multiple mouse drag gestures concurrently via MPX/XI2 (gaming)."""
    ctx = desktop_context()
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

    cua_call("parallel_mouse_drag", {"drags": drag_items})
    return {"status": "ok", "drag_count": len(req.drags)}


# ── Scroll ──────────────────────────────────────────────────────────

@router.post("/scroll")
async def scroll(req: ScrollRequest):
    """Scroll the focused region. direction: up|down|left|right"""
    pid = req.pid or get_desktop_pid()
    cua_call("scroll", {"pid": pid, "direction": req.direction, "amount": req.amount})
    return {"status": "ok", "direction": req.direction, "amount": req.amount}
