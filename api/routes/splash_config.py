"""
Splash screen config. Public GET; admin PATCH.
Stored in config/splash_config.json. Used by SplashLogin before login.

Single source of truth, no fallbacks. See docs/SPLASH_CONFIG.md.
"""

# Doc refs (AI / maintainers): docs/SPLASH_CONFIG.md (do not add silent fallbacks)

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from api.auth import require_admin
from project_root import PROJECT_ROOT

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/splash-config", tags=["splash-config"])

CONFIG_FILE = PROJECT_ROOT / "config" / "splash_config.json"

def _read_config() -> dict:
    """Read splash config. Raises HTTPException if config is missing or invalid."""
    if not CONFIG_FILE.is_file():
        logger.error("splash_config.json not found at %s", CONFIG_FILE)
        raise HTTPException(
            status_code=503,
            detail="Service configuration unavailable. Ensure config/splash_config.json exists and is mounted."
        )
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in splash_config.json: %s", e)
        raise HTTPException(
            status_code=503,
            detail="Invalid splash configuration. Fix config/splash_config.json."
        ) from e
    except OSError as e:
        logger.error("Failed to read splash_config.json: %s", e)
        raise HTTPException(
            status_code=503,
            detail="Cannot read splash configuration."
        ) from e


def _write_config(data: dict) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _coerce_splash_media_revision(config: dict) -> int:
    """Monotonic-ish revision for cache-busting splash media URLs (same path, new bytes)."""
    raw = config.get("splash_media_revision", 0)
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 0


def _with_revision_for_response(config: dict) -> dict:
    out = dict(config)
    out["splash_media_revision"] = _coerce_splash_media_revision(config)
    return out


class SplashConfigResponse(BaseModel):
    splash_url: str
    splash_type: str  # video | image | none
    splash_use_scraped_media: bool
    title: str
    splash_media_revision: int = 0


class SplashConfigUpdate(BaseModel):
    splash_url: str | None = None
    splash_type: str | None = None
    splash_use_scraped_media: bool | None = None
    title: str | None = None


@router.get("", response_model=SplashConfigResponse)
async def get_splash_config(response: Response):
    """
    Get splash screen configuration. Public endpoint.
    """
    # Splash should always reflect the latest admin update; prevent intermediary caching.
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    config = _read_config()
    return SplashConfigResponse(**_with_revision_for_response(config))


@router.patch("", response_model=SplashConfigResponse, dependencies=[Depends(require_admin)])
async def update_splash_config(update: SplashConfigUpdate, response: Response):
    """
    Update splash screen configuration. Admin only.
    """
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    current_config = _read_config()
    updated_config = current_config.copy()

    # Apply updates (client cannot set splash_media_revision; it is server-owned)
    for field, value in update.model_dump(exclude_unset=True).items():
        if value is not None:
            updated_config[field] = value

    # Validate splash_type
    if updated_config.get("splash_type") not in ["video", "image", "none"]:
        raise HTTPException(
            status_code=400,
            detail="splash_type must be 'video', 'image', or 'none'"
        )

    # Bust browser/CDN caches when media URL is unchanged but bytes on disk were replaced.
    updated_config["splash_media_revision"] = _coerce_splash_media_revision(updated_config) + 1

    _write_config(updated_config)
    logger.info("Splash config updated by admin")
    return SplashConfigResponse(**_with_revision_for_response(updated_config))

