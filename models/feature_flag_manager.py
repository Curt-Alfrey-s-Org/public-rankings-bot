"""
Feature Flag Manager for Alfa Rating Rollout
Manages runtime feature flag configuration with persistence and validation
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from datetime import datetime
import threading

logger = logging.getLogger(__name__)


class FeatureFlagManager:
    """
    Manages feature flags for Alfa rating system rollout.
    
    Features:
    - Load and store feature flags from JSON
    - Runtime updates with validation
    - Thread-safe operations
    - Audit trail of changes
    - Phase transition validation
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize feature flag manager."""
        if config_path is None:
            config_path = Path(__file__).parent / "feature_flags.json"
        else:
            config_path = Path(config_path)
        
        self.config_path = config_path
        self.flags = {}
        self.lock = threading.RLock()
        self.change_log = []
        
        # Load initial flags
        self.reload()
    
    def reload(self) -> None:
        """Reload flags from file."""
        with self.lock:
            try:
                if self.config_path.exists():
                    with open(self.config_path, 'r') as f:
                        self.flags = json.load(f)
                    logger.info(f"Feature flags loaded from {self.config_path}")
                else:
                    logger.warning(f"Feature flags file not found: {self.config_path}")
                    self.flags = {}
            except Exception as e:
                logger.error(f"Failed to load feature flags: {e}")
                self.flags = {}
    
    def save(self) -> None:
        """Save flags to file."""
        with self.lock:
            try:
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.config_path, 'w') as f:
                    json.dump(self.flags, f, indent=2)
                logger.info(f"Feature flags saved to {self.config_path}")
            except Exception as e:
                logger.error(f"Failed to save feature flags: {e}")
    
    def is_enabled(self, flag_name: str) -> bool:
        """
        Check if a boolean flag is enabled.
        
        Args:
            flag_name: Name of the flag
            
        Returns:
            True if enabled, False otherwise
        """
        with self.lock:
            flag = self.flags.get(flag_name)
            if flag is None:
                logger.warning(f"Flag not found: {flag_name}")
                return False
            
            if flag.get("type") != "boolean":
                logger.warning(f"Flag {flag_name} is not boolean type")
                return False
            
            return flag.get("enabled", False)
    
    def get_percentage(self, flag_name: str) -> int:
        """
        Get percentage value for a percentage flag.
        
        Args:
            flag_name: Name of the flag
            
        Returns:
            Percentage value (0-100)
        """
        with self.lock:
            flag = self.flags.get(flag_name)
            if flag is None:
                logger.warning(f"Flag not found: {flag_name}")
                return 0
            
            if flag.get("type") != "percentage":
                logger.warning(f"Flag {flag_name} is not percentage type")
                return 0
            
            percentage = flag.get("percentage", 0)
            return max(0, min(100, percentage))  # Clamp to 0-100
    
    def get_flag(self, flag_name: str) -> Optional[Dict[str, Any]]:
        """
        Get full flag configuration.
        
        Args:
            flag_name: Name of the flag
            
        Returns:
            Flag configuration dict or None
        """
        with self.lock:
            return self.flags.get(flag_name)
    
    def get_all_flags(self) -> Dict[str, Any]:
        """Get all flags."""
        with self.lock:
            return json.loads(json.dumps(self.flags))  # Deep copy
    
    def update_flag(self, flag_name: str, value: Any) -> Tuple[bool, str]:
        """
        Update a flag at runtime.
        
        Args:
            flag_name: Name of the flag
            value: New value (boolean or percentage)
            
        Returns:
            (success: bool, message: str)
        """
        with self.lock:
            flag = self.flags.get(flag_name)
            if flag is None:
                msg = f"Flag not found: {flag_name}"
                logger.warning(msg)
                return False, msg
            
            # Validate based on type
            flag_type = flag.get("type")
            
            if flag_type == "boolean":
                if not isinstance(value, bool):
                    msg = f"Expected boolean for {flag_name}, got {type(value)}"
                    logger.warning(msg)
                    return False, msg
                
                old_value = flag.get("enabled")
                flag["enabled"] = value
                self._log_change(flag_name, "enabled", old_value, value)
                self.save()
                logger.info(f"Flag {flag_name} updated: {old_value} → {value}")
                return True, f"Flag {flag_name} updated successfully"
            
            elif flag_type == "percentage":
                if not isinstance(value, (int, float)):
                    msg = f"Expected number for {flag_name}, got {type(value)}"
                    logger.warning(msg)
                    return False, msg
                
                percentage = int(value)
                if not 0 <= percentage <= 100:
                    msg = f"Percentage must be 0-100, got {percentage}"
                    logger.warning(msg)
                    return False, msg
                
                old_value = flag.get("percentage")
                flag["percentage"] = percentage
                self._log_change(flag_name, "percentage", old_value, percentage)
                self.save()
                logger.info(f"Flag {flag_name} updated: {old_value}% → {percentage}%")
                return True, f"Flag {flag_name} updated to {percentage}%"
            
            else:
                msg = f"Unknown flag type: {flag_type}"
                logger.error(msg)
                return False, msg
    
    def validate_rollout_prerequisites(self, phase: int) -> Tuple[bool, str]:
        """
        Validate that prerequisites are met for a phase.
        
        Phases:
        - 0: Pre-launch
        - 1: 10% Silent Canary (Weeks 1-2)
        - 2: 25% Shadow Mode (Weeks 3-4)
        - 3: 50% Experimentation (Weeks 5-6)
        - 4: 75% Controlled Expansion (Weeks 7-8)
        - 5: 100% Full Production (Week 9+)
        
        Args:
            phase: Target phase number (0-5)
            
        Returns:
            (valid: bool, message: str)
        """
        with self.lock:
            if phase < 0 or phase > 5:
                return False, f"Invalid phase: {phase}"
            
            # Phase 0 has no prerequisites
            if phase == 0:
                return True, "Phase 0 (Pre-launch) has no prerequisites"
            
            # Phase 1: Basic rollout capability
            if phase == 1:
                if "alfa_rating_enabled" not in self.flags:
                    return False, "alfa_rating_enabled flag required"
                if not self.flags.get("alfa_rollback_enabled", {}).get("enabled", True):
                    return False, "Rollback must be enabled for Phase 1"
                return True, "Phase 1 prerequisites met"
            
            # Phase 2: API support required
            if phase == 2:
                if "alfa_predictions_in_api" not in self.flags:
                    return False, "alfa_predictions_in_api flag required"
                return True, "Phase 2 prerequisites met"
            
            # Phase 3: Anomaly detection option
            if phase == 3:
                if "alfa_vs_fargo_comparison" not in self.flags:
                    return False, "alfa_vs_fargo_comparison flag required"
                return True, "Phase 3 prerequisites met"
            
            # Phase 4: Admin dashboard and anomaly detection
            if phase == 4:
                if "alfa_anomaly_detection_enabled" not in self.flags:
                    return False, "alfa_anomaly_detection_enabled flag required"
                if "alfa_admin_dashboard_enabled" not in self.flags:
                    return False, "alfa_admin_dashboard_enabled flag required"
                return True, "Phase 4 prerequisites met"
            
            # Phase 5: All systems go
            if phase == 5:
                return True, "Phase 5 (Full Production) prerequisites met"
            
            return False, "Unknown phase validation error"
    
    def _log_change(self, flag_name: str, attribute: str, old_value: Any, new_value: Any) -> None:
        """Log a flag change for audit trail."""
        self.change_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "flag": flag_name,
            "attribute": attribute,
            "old_value": old_value,
            "new_value": new_value
        })
    
    def get_change_log(self, limit: Optional[int] = None) -> list:
        """Get audit trail of flag changes."""
        with self.lock:
            if limit:
                return self.change_log[-limit:]
            return list(self.change_log)
    
    def get_current_phase(self) -> int:
        """
        Determine current phase from alfa_rating_enabled percentage.
        
        Returns:
            Phase number (0-5)
        """
        percentage = self.get_percentage("alfa_rating_enabled")
        
        if percentage == 0:
            return 0
        elif percentage <= 10:
            return 1
        elif percentage <= 25:
            return 2
        elif percentage <= 50:
            return 3
        elif percentage <= 75:
            return 4
        else:
            return 5
    
    def get_phase_name(self, phase: int) -> str:
        """Get human-readable name for a phase."""
        names = {
            0: "Pre-launch (0%)",
            1: "Silent Canary (10%)",
            2: "Shadow Mode (25%)",
            3: "Experimentation (50%)",
            4: "Controlled Expansion (75%)",
            5: "Full Production (100%)"
        }
        return names.get(phase, "Unknown")


# Global instance
_global_manager: Optional[FeatureFlagManager] = None


def get_feature_flag_manager(config_path: Optional[str] = None) -> FeatureFlagManager:
    """Get or create global feature flag manager."""
    global _global_manager
    if _global_manager is None:
        _global_manager = FeatureFlagManager(config_path)
    return _global_manager


def reset_feature_flag_manager() -> None:
    """Reset global manager (useful for testing)."""
    global _global_manager
    _global_manager = None
