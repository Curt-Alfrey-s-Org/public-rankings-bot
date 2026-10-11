"""
Settings Routes
Handles bot configuration and settings
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter()

class SettingsUpdate(BaseModel):
    """Settings update model"""
    settings: Dict[str, Any]

def _get_env_file_path():
    """Get the path to the .env file"""
    return Path(__file__).parent.parent.parent / '.env'

def _read_env_file():
    """Read .env file and return as dictionary"""
    env_file = _get_env_file_path()
    env_vars = {}
    
    if env_file.exists():
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue
                    # Parse KEY=VALUE
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        # Remove quotes if present
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        env_vars[key] = value
        except Exception as e:
            logger.warning(f"Error reading .env file: {e}")
    
    return env_vars

# Keys that the Settings GUI is allowed to persist.
# Rankings-bot only supports non-trading operational settings here.
USER_FACING_SETTING_KEYS = frozenset({
    "LOG_LEVEL",
    "DEBUG",
    "ALERT_EMAIL_ENABLED",
})

def _update_env_file(updates: Dict[str, Any]):
    """Update .env file with new settings (only user-facing keys are persisted)."""
    env_file = _get_env_file_path()
    
    if not env_file.exists():
        logger.warning(f".env file not found at {env_file}")
        return False
    
    # Only persist keys that are in the user-facing whitelist
    updates = {k: v for k, v in updates.items() if k in USER_FACING_SETTING_KEYS}
    if not updates:
        return False

    try:
        # Read existing .env file
        with open(env_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        updated = False
        new_lines = []
        settings_found = {key: False for key in updates.keys()}
        
        # Map frontend setting names to .env variable names
        setting_to_env_map = {
            "LOG_LEVEL": "LOG_LEVEL",
            "DEBUG": "DEBUG",
            "ALERT_EMAIL_ENABLED": "ALERT_EMAIL_ENABLED",
        }
        
        # Process each line
        for line in lines:
            line_stripped = line.strip()
            updated_line = False
            
            # Check if this line contains a setting we want to update
            for setting_key, setting_value in updates.items():
                env_key = setting_to_env_map.get(setting_key, setting_key)
                if line_stripped.startswith(f'{env_key}='):
                    # Update the value
                    new_lines.append(f"{env_key}={setting_value}\n")
                    settings_found[setting_key] = True
                    updated = True
                    updated_line = True
                    break
            
            if not updated_line:
                new_lines.append(line)
        
        # Add missing variables if they weren't in the file
        for setting_key, setting_value in updates.items():
            if not settings_found[setting_key]:
                env_key = setting_to_env_map.get(setting_key, setting_key)
                new_lines.append(f"{env_key}={setting_value}\n")
                updated = True
        
        # Write back to file
        if updated:
            with open(env_file, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            logger.info(f"Updated .env file with {len(updates)} settings")
            
            # Update environment variables in current process
            for setting_key, setting_value in updates.items():
                env_key = setting_to_env_map.get(setting_key, setting_key)
                os.environ[env_key] = str(setting_value)
        
        return updated
    except Exception as e:
        logger.error(f"Error updating .env file: {e}", exc_info=True)
        return False
