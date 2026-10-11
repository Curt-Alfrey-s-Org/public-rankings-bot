"""
Public appearance: default avatar/background for users without custom.
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/appearance", tags=["appearance"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_APPEARANCE_FILE = PROJECT_ROOT / "config" / "default_appearance.json"


class DefaultAppearanceResponse(BaseModel):
    default_avatar_url: str = ""
    default_background_url: str = ""


def _read_default_appearance() -> dict:
    path = DEFAULT_APPEARANCE_FILE
    if path.is_file():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {
                    "default_avatar_url": data.get("default_avatar_url", "") or "",
                    "default_background_url": data.get("default_background_url", "") or "",
                }
        except Exception as e:
            logger.warning("Failed to read default appearance: %s", e)
    return {"default_avatar_url": "", "default_background_url": ""}


@router.get("/default", response_model=DefaultAppearanceResponse)
async def get_default_appearance():
    """Return default avatar and background URLs for users who don't have custom. No auth."""
    return DefaultAppearanceResponse(**_read_default_appearance())
