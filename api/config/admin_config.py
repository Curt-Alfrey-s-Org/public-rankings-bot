"""
Admin config: tier config and role capabilities.
Super admin can override via Settings > Admin. Stored in config/*.json.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
TIER_CONFIG_FILE = CONFIG_DIR / "tier_config.json"
ROLE_CAPABILITIES_FILE = CONFIG_DIR / "role_capabilities.json"

# Default role capabilities: [Player, Director, Admin, Super admin]
DEFAULT_ROLE_CAPABILITIES: List[Dict[str, Any]] = [
    {"id": "view_own_perf", "label": "View own performance", "roles": [True, True, True, True]},
    {"id": "view_all_perf", "label": "View all players' performance", "roles": [False, False, True, True]},
    {"id": "create_tournaments", "label": "Create / edit tournaments", "roles": [False, True, True, True]},
    {"id": "create_players", "label": "Create players", "roles": [False, True, True, True]},
    {"id": "data_input", "label": "Data input", "roles": [False, True, True, True]},
    {"id": "user_management", "label": "User management", "roles": [False, False, True, True]},
    {"id": "rebuild_website", "label": "Full deploy (website / images)", "roles": [False, False, True, True]},
    {"id": "covert_ops", "label": "Covert Ops", "roles": [False, False, True, True]},
    {"id": "create_super_admin", "label": "Create super_admin", "roles": [False, False, False, True]},
]


def _read_json(path: Path) -> dict | list | None:
    """Read JSON file; return None if missing or invalid."""
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to read %s: %s", path, e)
        return None


def _write_json(path: Path, data: dict | list) -> None:
    """Write JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_role_capabilities() -> List[Dict[str, Any]]:
    """Return role capabilities. Uses config file if present, else defaults."""
    data = _read_json(ROLE_CAPABILITIES_FILE)
    if data and isinstance(data, list) and len(data) > 0:
        return data
    return DEFAULT_ROLE_CAPABILITIES


def save_role_capabilities(capabilities: List[Dict[str, Any]]) -> None:
    """Save role capabilities. Super admin only."""
    # Validate structure
    validated = []
    for row in capabilities:
        if not isinstance(row, dict) or "id" not in row or "label" not in row or "roles" not in row:
            continue
        roles = row["roles"]
        if not isinstance(roles, list) or len(roles) != 4:
            continue
        validated.append({
            "id": str(row["id"]),
            "label": str(row["label"]),
            "roles": [bool(r) for r in roles[:4]],
        })
    if validated:
        _write_json(ROLE_CAPABILITIES_FILE, validated)


def get_tier_config() -> Dict[str, Any]:
    """
    Return tier config from config file; code defaults used when file is absent.
    Callers use api.models.ai_coach.TIER_CONFIG for default values when a key is missing.
    """
    data = _read_json(TIER_CONFIG_FILE)
    if data and isinstance(data, dict) and len(data) > 0:
        return data
    return {}


def save_tier_config(tiers: Dict[str, Any]) -> None:
    """Save tier config. Super admin only. Merges with defaults for missing keys."""
    if not isinstance(tiers, dict):
        return
    validated: Dict[str, Any] = {}
    for tier_key, tier_data in tiers.items():
        if not isinstance(tier_data, dict):
            continue
        validated[tier_key] = {
            "name": str(tier_data.get("name", tier_key)),
            "monthly_limit": tier_data.get("monthly_limit") if tier_data.get("monthly_limit") is not None else None,
            "lifetime_limit": tier_data.get("lifetime_limit") if tier_data.get("lifetime_limit") is not None else None,
            "max_video_duration": int(tier_data.get("max_video_duration", 30)),
            "price_monthly": float(tier_data.get("price_monthly", 0)),
            "features": list(tier_data.get("features", [])) if isinstance(tier_data.get("features"), list) else [],
        }
    if validated:
        _write_json(TIER_CONFIG_FILE, validated)


def get_effective_tier_config() -> Dict[str, Any]:
    """
    Return merged tier config: file overrides + code defaults.
    Used by ai_coach and db_service.
    """
    try:
        from api.models.ai_coach import TIER_CONFIG as CODE_TIER_CONFIG
    except ImportError:
        CODE_TIER_CONFIG = {}

    effective = dict(CODE_TIER_CONFIG)
    file_config = get_tier_config()
    for key, override in file_config.items():
        if isinstance(override, dict):
            if key in effective:
                effective[key] = {**effective[key], **override}
            else:
                effective[key] = override
    return effective
