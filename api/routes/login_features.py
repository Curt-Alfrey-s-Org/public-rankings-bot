"""
Login and capabilities feature lists. Short list for splash; full list for capabilities page.
Editable by super_admin only. Stored in config/login_features.json.
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.auth import require_super_admin
from project_root import PROJECT_ROOT

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/login-features", tags=["login-features"])

CONFIG_FILE = PROJECT_ROOT / "config" / "login_features.json"

DEFAULT_SHORT = [
    {"title": "Rankings", "description": "WPBA & WPA rankings with search and filters."},
    {"title": "Live Est. Rating (PRO)", "description": "Live rating updates during play (PRO subscription required)."},
    {"title": "ALFa Rating (PRO)", "description": "ALFa replaces legacy Fargo-style ratings over time; ingests Fargo history and uses AI to validate accuracy (PRO subscription required)."},
    {"title": "Movement", "description": "See who moved up, down, and why."},
    {"title": "Tournaments", "description": "History, results, brackets, and standings."},
    {"title": "Brackets & leaderboards", "description": "Live brackets and leaderboard views."},
    {"title": "Head-to-Head", "description": "Compare two players side-by-side."},
    {"title": "Player performance", "description": "Track stats and key changes over time."},
    {"title": "AI Coach", "description": "Upload video for analysis and tips."},
    {"title": "Director tools", "description": "Run events, assign tables, enter scores."},
    {"title": "Scorekeeping tools", "description": "Score keeper mode and shot clock."},
]
DEFAULT_FULL = [
    {"title": "Rankings", "description": "Official-style WPBA & WPA rankings with search and filters; ratings alongside where available."},
    {"title": "Live Est. Rating (PRO)", "description": "Premium live rating updated rack-by-rack during active play for PRO subscribers."},
    {"title": "ALFa Rating (PRO)", "description": "Premium cross-format rating designed to replace Fargo as the primary signal; imports Fargo past history and uses AI to check whether legacy ratings still match real play; combines rank, points, and external context (PRO)."},
    {"title": "Movement", "description": "See who moved up or down, point changes, and trends over time."},
    {"title": "Tournament history", "description": "Browse past events, results, and standings in one place."},
    {"title": "Brackets & leaderboards", "description": "View brackets and live leaderboards; run events and enter scores."},
    {"title": "Upcoming events", "description": "See what's coming up in one feed."},
    {"title": "Head-to-Head", "description": "Compare any two players: rankings, ratings, and how they've fared against each other."},
    {"title": "Player performance", "description": "Track stats and get notified when things change that matter to you."},
    {"title": "AI Coach", "description": "Upload session video and get analysis and pointers to improve your game."},
    {"title": "Tournament Wizard", "description": "Create new tournaments step-by-step with guided setup."},
    {"title": "Director mode", "description": "Run brackets, assign tables, enter scores, and manage matches."},
    {"title": "Score keeper mode", "description": "Enter scores and run timers at your table."},
    {"title": "Timekeeper / shot clock", "description": "Full-screen shot clock for timekeepers at the table."},
    {"title": "Data input", "description": "Enter or upload rankings and tournament data; keep everything in sync."},
    {"title": "Player management", "description": "Manage rosters and tournament players."},
    {"title": "Anti-sandbagging", "description": "AI-assisted signals and tools to flag unfair play and keep competition honest when ratings may not match results."},
    {"title": "Covert Ops", "description": "Prep on opponents with recon-style insights (admin)."},
    {"title": "User management & roles", "description": "Create users and assign roles (player, director, admin, score keeper)."},
    {"title": "Refresh, export & backup", "description": "Pull latest from sources, export to CSV, download backup (admin)."},
    {"title": "Health & logs", "description": "Monitor system health and view logs (admin)."},
    {"title": "News & links", "description": "Quick access to feeds and resources you use most."},
    {"title": "Customizable", "description": "Appearance and layout options so it works your way."},
]


def _read_config() -> dict:
    if CONFIG_FILE.is_file():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                short = data.get("short")
                full = data.get("full")
                if isinstance(short, list) and isinstance(full, list):
                    return {"short": short, "full": full}
        except Exception as e:
            logger.warning("Failed to read login_features.json: %s", e)
    return {"short": DEFAULT_SHORT, "full": DEFAULT_FULL}


def _write_config(data: dict) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class FeatureItem(BaseModel):
    title: str
    description: str


class LoginFeaturesResponse(BaseModel):
    short: list[FeatureItem]
    full: list[FeatureItem]


class LoginFeaturesUpdate(BaseModel):
    short: list[FeatureItem] | None = None
    full: list[FeatureItem] | None = None


@router.get("")
async def get_login_features(variant: str = Query("short", description="Variant: 'short' or 'full'")):
    """Get login features list for splash or capabilities page"""
    config = _read_config()
    if variant == "full":
        return LoginFeaturesResponse(short=config["short"], full=config["full"])
    else:
        return {"features": config["short"]}


@router.put("")
async def update_login_features(update: LoginFeaturesUpdate, user=Depends(require_super_admin)):
    """Update login features (super_admin only)"""
    config = _read_config()
    if update.short is not None:
        config["short"] = [item.dict() for item in update.short]
    if update.full is not None:
        config["full"] = [item.dict() for item in update.full]
    _write_config(config)
    return {"message": "Login features updated", "data": config}

# Force reload trigger
