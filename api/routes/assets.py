"""
Assets API: list and upload pics/videos for appearance (avatar, background, splash).
Serves from a dedicated media directory so uploads don't touch frontend build output.
"""

import logging
import mimetypes
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from api.auth import get_current_user
from project_root import PROJECT_ROOT

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/assets", tags=["assets"])
MEDIA_DIR = PROJECT_ROOT / "media"
# Allow subdirs: video, image (optional)
MEDIA_VIDEO = MEDIA_DIR / "video"
MEDIA_IMAGE = MEDIA_DIR / "image"


def _ensure_media_dirs():
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    MEDIA_VIDEO.mkdir(exist_ok=True)
    MEDIA_IMAGE.mkdir(exist_ok=True)


def _path_to_serve_path(relative_path: Path) -> str:
    return f"/api/assets/serve/{relative_path.as_posix()}"


def _type_from_path(p: Path) -> str:
    ext = (p.suffix or "").lower()
    if ext in {".mp4", ".webm", ".mov", ".ogg", ".avi"}:
        return "video"
    return "image"


@router.get("/serve/{path:path}")
async def serve_asset(path: str):
    """Serve a single asset file by path under media/."""
    if ".." in path or path.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid path")
    full = (MEDIA_DIR / path).resolve()
    if not full.exists() or not full.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    if not str(full).startswith(str(MEDIA_DIR.resolve())):
        raise HTTPException(status_code=403, detail="Forbidden")
    media_type, _ = mimetypes.guess_type(str(full))
    from fastapi.responses import FileResponse
    return FileResponse(full, media_type=media_type or "application/octet-stream")


@router.post("/upload")
async def upload_assets(
    files: list[UploadFile] = File(...),
    _user: dict = Depends(get_current_user),
):
    """Upload one or more image/video files. Saves to media/ with unique names. Auth required."""
    _ensure_media_dirs()
    urls = []
    for f in files:
        if not f.filename:
            continue
        ext = Path(f.filename).suffix.lower()
        if ext in {".mp4", ".webm", ".mov", ".ogg", ".avi"}:
            subdir = MEDIA_VIDEO
        else:
            subdir = MEDIA_IMAGE
        safe_name = f"{uuid.uuid4().hex}{ext}" if ext else f"{uuid.uuid4().hex}"
        dest = subdir / safe_name
        try:
            content = await f.read()
            dest.write_bytes(content)
            rel = dest.relative_to(MEDIA_DIR)
            urls.append(_path_to_serve_path(rel))
        except Exception as e:
            logger.exception("Upload failed for %s: %s", f.filename, e)
            raise HTTPException(status_code=500, detail=f"Upload failed: {e}")
    return {"urls": urls}
