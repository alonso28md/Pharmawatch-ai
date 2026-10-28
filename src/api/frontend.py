"""Serves the built web interface (frontend/dist) under /app as a single-page app.

Hashed files under /app/assets are cached forever; every other path that is not a real
file falls back to index.html so client-side routes (/app/review/INC-...) survive a reload.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

MOUNT = "/app"
_IMMUTABLE = "public, max-age=31536000, immutable"
_NO_CACHE = "no-cache"


def frontend_router(dist_dir: Path) -> APIRouter:
    """Router for MOUNT backed by a Vite build in `dist_dir` (must contain index.html)."""
    root = dist_dir.resolve()
    index = root / "index.html"
    router = APIRouter(include_in_schema=False)

    @router.get(MOUNT)
    async def app_root() -> RedirectResponse:
        return RedirectResponse(url=f"{MOUNT}/", status_code=308)

    @router.get(MOUNT + "/{path:path}")
    async def app_file(path: str) -> FileResponse:
        candidate = (root / path).resolve()
        if not candidate.is_relative_to(root):
            raise HTTPException(status_code=404)
        if path and candidate.is_file():
            cache = _IMMUTABLE if path.startswith("assets/") else _NO_CACHE
            return FileResponse(candidate, headers={"Cache-Control": cache})
        if path.startswith("assets/") or Path(path).suffix:
            # A missing asset is a real 404, not the app shell.
            raise HTTPException(status_code=404)
        return FileResponse(index, headers={"Cache-Control": _NO_CACHE})

    return router
