"""
Network/Internet Access Control Routes
Allows users to allow/forbid bot internet connectivity
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import sys
from pathlib import Path

# Add parent directory to path to import internet_access_control
sys.path.insert(0, str(Path(__file__).parent.parent))
from internet_access_control import InternetAccessControl

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
# Use config/ (writable in Docker; same as login_features.json, etc.) — not repo root /app.
_INTERNET_ACCESS_DIR = _PROJECT_ROOT / "config"

router = APIRouter()
internet_control = InternetAccessControl(config_dir=str(_INTERNET_ACCESS_DIR))

class InternetAccessRequest(BaseModel):
    allowed: bool

class InternetAccessResponse(BaseModel):
    allowed: bool
    allowed_str: str
    updated_at: str = None
    message: str = None

@router.get("/network/access", response_model=InternetAccessResponse)
async def get_internet_access():
    """Get current internet access status
    
    Returns:
        Current internet access setting (ALLOWED or FORBIDDEN)
    """
    try:
        config = internet_control.get_internet_access()
        return InternetAccessResponse(
            allowed=config.get('allowed', True),
            allowed_str=config.get('allowed_str', 'UNKNOWN'),
            updated_at=config.get('updated_at'),
            message="Internet access is " + config.get('allowed_str', 'UNKNOWN')
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get internet access: {str(e)}")

@router.post("/network/access", response_model=InternetAccessResponse)
async def set_internet_access(request: InternetAccessRequest):
    """Set internet access status
    
    Args:
        request: {allowed: true|false}
        
    Returns:
        Updated internet access setting
    """
    try:
        config = internet_control.set_internet_access(request.allowed)
        action = "ALLOWED" if request.allowed else "FORBIDDEN"
        return InternetAccessResponse(
            allowed=config.get('allowed', True),
            allowed_str=config.get('allowed_str', 'UNKNOWN'),
            updated_at=config.get('updated_at'),
            message=f"Internet access is now {action}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set internet access: {str(e)}")

@router.get("/network/access/forbid", response_model=InternetAccessResponse)
async def forbid_internet():
    """Forbid internet access (convenience endpoint)
    
    Returns:
        Updated status with internet access FORBIDDEN
    """
    config = internet_control.set_internet_access(False)
    return InternetAccessResponse(
        allowed=False,
        allowed_str="FORBIDDEN",
        updated_at=config.get('updated_at'),
        message="Internet access is now FORBIDDEN"
    )

@router.get("/network/access/allow", response_model=InternetAccessResponse)
async def allow_internet():
    """Allow internet access (convenience endpoint)
    
    Returns:
        Updated status with internet access ALLOWED
    """
    config = internet_control.set_internet_access(True)
    return InternetAccessResponse(
        allowed=True,
        allowed_str="ALLOWED",
        updated_at=config.get('updated_at'),
        message="Internet access is now ALLOWED"
    )
