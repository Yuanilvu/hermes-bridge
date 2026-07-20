"""Desktop control package — Hermes Bridge.

Composes sub-modules into a single router mounted at /api/desktop.
"""
from fastapi import APIRouter, Depends

from auth import verify_api_key
from routers.desktop import info, screenshot, mouse, keyboard, apps, management

router = APIRouter(
    prefix="/api/desktop",
    tags=["Desktop"],
    dependencies=[Depends(verify_api_key)],
)

# Sub-routers (each has no prefix; the main router provides /api/desktop)
router.include_router(info.router)
router.include_router(screenshot.router)
router.include_router(mouse.router)
router.include_router(keyboard.router)
router.include_router(apps.router)
router.include_router(management.router)
