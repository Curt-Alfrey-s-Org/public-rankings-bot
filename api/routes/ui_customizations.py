"""
UI Customizations API Routes
Provides endpoints for managing dashboard UI customizations with live updates
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
import json
import logging

from sqlalchemy import text
from database import get_engine
from api.auth import require_admin, require_super_admin
from api.notifications import broadcast_live_update

router = APIRouter(prefix="/api/ui-customizations", tags=["ui-customizations"])
logger = logging.getLogger(__name__)


class UICustomizationUpdate(BaseModel):
    """Model for updating UI customizations"""
    scope: str
    data: Dict[str, Any]


class UICustomizationResponse(BaseModel):
    """Response model for UI customizations"""
    scope: str
    data: Dict[str, Any]
    created_at: str
    updated_at: str


@router.get("")
async def get_ui_customizations():
    """Get all UI customizations"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT scope, data, created_at, updated_at
            FROM ui_customizations
            ORDER BY scope
        """)).fetchall()

        customizations = []
        for row in result:
            customizations.append({
                "scope": row[0],
                "data": row[1],
                "created_at": str(row[2]),
                "updated_at": str(row[3])
            })

        return {"customizations": customizations}


@router.get("/global")
async def get_global_ui_customizations():
    """Get global UI customizations in the format expected by frontend"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT data FROM ui_customizations WHERE scope = 'global'
        """)).first()

        if result:
            # Return the stored global customizations
            return result[0]
        else:
            # Return defaults if no global customization exists
            return get_default_customization_data("global")


@router.get("", response_model=None)
async def get_ui_customization_global():
    """Get global UI customizations in flattened format (for frontend compatibility)"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT data
            FROM ui_customizations
            WHERE scope = 'global'
        """)).first()

        if not result:
            # Return default structure if no customizations exist
            return {
                "version": 1,
                "text": {},
                "buttons": {},
                "layouts": {}
            }

        # Return the data directly (flattened structure)
        data = result[0]
        # Ensure all required fields exist with defaults
        return {
            "version": data.get("version", 1),
            "text": data.get("text", {}),
            "buttons": data.get("buttons", {}),
            "layouts": data.get("layouts", {})
        }


@router.get("/{scope}")
async def get_ui_customization(scope: str):
    """Get UI customization by scope"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT scope, data, created_at, updated_at
            FROM ui_customizations
            WHERE scope = :scope
        """), {"scope": scope}).first()

        if not result:
            raise HTTPException(status_code=404, detail=f"UI customization '{scope}' not found")

        return {
            "scope": result[0],
            "data": result[1],
            "created_at": str(result[2]),
            "updated_at": str(result[3])
        }


@router.put("/{scope}", dependencies=[Depends(require_super_admin)])
async def update_ui_customization(scope: str, update: UICustomizationUpdate):
    """Update UI customization (super admin only)"""
    if update.scope != scope:
        raise HTTPException(status_code=400, detail="Scope mismatch")

    engine = get_engine()
    with engine.connect() as conn:
        # Update the customization
        result = conn.execute(text("""
            UPDATE ui_customizations
            SET data = :data, updated_at = CURRENT_TIMESTAMP
            WHERE scope = :scope
            RETURNING id
        """), {
            "scope": scope,
            "data": json.dumps(update.data)
        })

        if result.rowcount == 0:
            # Insert new customization if it doesn't exist
            conn.execute(text("""
                INSERT INTO ui_customizations (scope, data)
                VALUES (:scope, :data)
            """), {
                "scope": scope,
                "data": json.dumps(update.data)
            })

        conn.commit()

        # Broadcast live update to all connected clients
        await broadcast_live_update("ui_customization_updated", {
            "scope": scope,
            "data": update.data
        })

        return {"message": f"UI customization '{scope}' updated successfully"}


@router.put("/global", dependencies=[Depends(require_super_admin)])
async def update_global_ui_customizations(data: Dict[str, Any]):
    """Update global UI customizations (super admin only)"""
    engine = get_engine()
    with engine.connect() as conn:
        # Update the global customization
        result = conn.execute(text("""
            UPDATE ui_customizations
            SET data = :data, updated_at = CURRENT_TIMESTAMP
            WHERE scope = 'global'
            RETURNING id
        """), {
            "data": json.dumps(data)
        })

        if result.rowcount == 0:
            # Insert new global customization if it doesn't exist
            conn.execute(text("""
                INSERT INTO ui_customizations (scope, data)
                VALUES ('global', :data)
            """), {
                "data": json.dumps(data)
            })

        conn.commit()

        # Broadcast live update to all connected clients
        await broadcast_live_update("ui_customization_updated", {
            "scope": "global",
            "data": data
        })

        return data


@router.put("", dependencies=[Depends(require_super_admin)])
async def update_ui_customization_global(payload: Dict[str, Any]):
    """Update global UI customizations in flattened format (for frontend compatibility)"""
    engine = get_engine()
    with engine.connect() as conn:
        # Validate the payload structure
        required_fields = ["version", "text", "buttons", "layouts"]
        for field in required_fields:
            if field not in payload:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

        # Update the global customization
        result = conn.execute(text("""
            UPDATE ui_customizations
            SET data = :data, updated_at = CURRENT_TIMESTAMP
            WHERE scope = 'global'
            RETURNING id
        """), {
            "data": json.dumps(payload)
        })

        if result.rowcount == 0:
            # Insert new customization if it doesn't exist
            conn.execute(text("""
                INSERT INTO ui_customizations (scope, data)
                VALUES ('global', :data)
            """), {
                "data": json.dumps(payload)
            })

        conn.commit()

        # Broadcast live update to all connected clients
        await broadcast_live_update("ui_customization_updated", {
            "scope": "global",
            "data": payload
        })

        return payload


@router.delete("/{scope}", dependencies=[Depends(require_super_admin)])
async def delete_ui_customization(scope: str):
    """Delete UI customization (super admin only)"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            DELETE FROM ui_customizations
            WHERE scope = :scope
        """), {"scope": scope})

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"UI customization '{scope}' not found")

        conn.commit()

        # Broadcast live update
        await broadcast_live_update("ui_customization_deleted", {"scope": scope})

        return {"message": f"UI customization '{scope}' deleted successfully"}


@router.post("/reset/{scope}", dependencies=[Depends(require_super_admin)])
async def reset_ui_customization(scope: str):
    """Reset UI customization to defaults"""
    default_data = get_default_customization_data(scope)

    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE ui_customizations
            SET data = :data, updated_at = CURRENT_TIMESTAMP
            WHERE scope = :scope
        """), {
            "scope": scope,
            "data": json.dumps(default_data)
        })
        conn.commit()

        # Broadcast live update
        await broadcast_live_update("ui_customization_reset", {
            "scope": scope,
            "data": default_data
        })

        return {"message": f"UI customization '{scope}' reset to defaults"}


def get_default_customization_data(scope: str) -> Dict[str, Any]:
    """Get default customization data for a scope"""
    defaults = {
        "global": {
            "text": {
                "dashboard_title": "Rankings Dashboard",
                "dashboard_subtitle": "Professional Pool Rankings",
                "loading_message": "Loading...",
                "no_data_message": "No data available",
                "error_message": "An error occurred"
            },
            "buttons": {
                "refresh": "Refresh",
                "save": "Save",
                "cancel": "Cancel",
                "edit": "Edit",
                "delete": "Delete"
            },
            "layouts": {
                "sidebar_collapsed": False,
                "compact_mode": False,
                "show_breadcrumbs": True,
                "show_footer": True,
                "show_rankings_stats_cards": False,
                "show_competitors_card": False,
                "show_association_card": False,
                "show_displayed_card": False
            },
            "version": 1
        }
    }
    return defaults.get(scope, {})


@router.get("/defaults/{scope}")
async def get_ui_customization_defaults(scope: str):
    """Get default values for UI customization scope"""
    defaults = get_default_customization_data(scope)
    return {"scope": scope, "defaults": defaults}


# Live update WebSocket endpoint would be added here for real-time updates
# This would allow the frontend to receive live updates when customizations change