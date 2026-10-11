"""
Director-only routes: table clocks (shot clock, game clock, match clock, table time alert).
Settings stored in config/director_clock_settings.json.
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import require_director_or_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/director", tags=["director"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CLOCK_SETTINGS_FILE = PROJECT_ROOT / "config" / "director_clock_settings.json"

DEFAULT_SHOT_CLOCK_SECONDS = 40
DEFAULT_GAME_CLOCK_MINUTES = 0
DEFAULT_MATCH_CLOCK_MINUTES = 0
DEFAULT_TABLE_TIME_ALERT_MINUTES = 0


class DirectorClockSettings(BaseModel):
    """Director-set clocks. 0 = disabled. shot_clock_enabled=False means shot clock off (default)."""
    shot_clock_enabled: bool = Field(default=False, description="Shot clock on/off (default off)")
    shot_clock_seconds: int = Field(default=DEFAULT_SHOT_CLOCK_SECONDS, ge=10, le=120, description="Shot clock per player turn (seconds)")
    game_clock_minutes: int = Field(default=DEFAULT_GAME_CLOCK_MINUTES, ge=0, le=120, description="Game clock (0 = off)")
    match_clock_minutes: int = Field(default=DEFAULT_MATCH_CLOCK_MINUTES, ge=0, le=300, description="Match clock (0 = off)")
    table_time_alert_minutes: int = Field(default=DEFAULT_TABLE_TIME_ALERT_MINUTES, ge=0, le=180, description="Alert director when table runs over this many minutes (0 = off)")


DEFAULTS = {
    "shot_clock_enabled": False,
    "shot_clock_seconds": DEFAULT_SHOT_CLOCK_SECONDS,
    "game_clock_minutes": DEFAULT_GAME_CLOCK_MINUTES,
    "match_clock_minutes": DEFAULT_MATCH_CLOCK_MINUTES,
    "table_time_alert_minutes": DEFAULT_TABLE_TIME_ALERT_MINUTES,
}


def _read_clock_settings() -> dict:
    out = dict(DEFAULTS)
    if CLOCK_SETTINGS_FILE.is_file():
        try:
            with open(CLOCK_SETTINGS_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            out.update({k: v for k, v in loaded.items() if k in out})
        except Exception as e:
            logger.warning("Failed to read director clock settings: %s", e)
    return out


@router.get("/clock-settings", response_model=DirectorClockSettings)
async def get_clock_settings():
    """Get director clock settings (shot clock, game clock, match clock, table time alert). No auth so table display can read."""
    data = _read_clock_settings()
    return DirectorClockSettings(**data)


class DirectorClockSettingsPatch(BaseModel):
    """Partial update for clock settings."""

    shot_clock_enabled: bool | None = None
    shot_clock_seconds: int | None = None
    game_clock_minutes: int | None = None
    match_clock_minutes: int | None = None
    table_time_alert_minutes: int | None = None


@router.patch("/clock-settings", response_model=DirectorClockSettings)
async def update_clock_settings(
    body: DirectorClockSettingsPatch,
    _user: dict = Depends(require_director_or_admin),
):
    """Update director clock settings. Director or admin only."""
    current = _read_clock_settings()
    patch = body.model_dump(exclude_none=True)
    current.update(patch)
    merged = DirectorClockSettings(**current)
    CLOCK_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(CLOCK_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(merged.model_dump(), f, indent=2)
    except Exception as e:
        logger.exception("Failed to write director clock settings")
        raise HTTPException(status_code=500, detail=str(e))
    return merged
