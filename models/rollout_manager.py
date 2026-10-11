"""
Rollout Manager for Alfa Rating System
Manages gradual deployment, metrics collection, and decision logic.
"""

import hashlib
import logging
import random
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class RatingMethod(str, Enum):
    """Rating method enum."""
    ALFA = "alfa"
    FARGO = "fargo"
    BOTH = "both"


@dataclass
class RolloutMetrics:
    """Metrics for rollout evaluation."""
    rollout_percentage: int
    avg_brier_alfa: float
    avg_brier_fargo: float
    improvement_pct: float
    tournaments_completed: int
    matches_total: int
    errors_count: int
    error_rate: float
    anomalies_detected: int
    anomalies_false_positive_rate: float


class RolloutManager:
    """
    Manages Alfa rating rollout with feature flags and gradual deployment.
    
    Features:
    - Percentage-based deployment
    - Tournament-type stratification
    - User opt-in tracking
    - Metrics collection
    - Rollback decision support
    """
    
    # Tournament types for stratification
    TOURNAMENT_TYPES = ["league", "single_elimination", "round_robin", "cash_game", "online"]
    
    def __init__(self, feature_flag_manager):
        """Initialize rollout manager."""
        self.feature_flag_manager = feature_flag_manager
        self.user_preferences = {}  # Track user opt-in decisions
        self.tournament_assignments = {}  # Cache tournament→method assignments
    
    def get_ratings_method(
        self,
        tournament_id: str,
        user_id: Optional[str] = None,
        tournament_type: str = "league"
    ) -> RatingMethod:
        """
        Determine which rating method to use for a tournament.
        
        Decision tree:
        1. Feature flag must be enabled
        2. Check rollout percentage
        3. Apply stratification by tournament type
        4. Check user preferences (opt-in for early phases)
        
        Args:
            tournament_id: Tournament identifier
            user_id: User identifier (optional, for opt-in tracking)
            tournament_type: Type of tournament
            
        Returns:
            RatingMethod (ALFA, FARGO, or BOTH)
        """
        # Check if Alfa is enabled
        percentage = self.feature_flag_manager.get_percentage("alfa_rating_enabled")
        if percentage == 0:
            return RatingMethod.FARGO
        
        current_phase = self.feature_flag_manager.get_current_phase()
        
        # Check prerequisites for method
        if not self._check_prerequisites_met(current_phase):
            return RatingMethod.FARGO
        
        # Determine if this tournament should use Alfa
        should_use_alfa = self.should_use_alfa(
            tournament_id,
            tournament_type,
            percentage
        )
        
        if not should_use_alfa:
            return RatingMethod.FARGO
        
        # Check user preferences for early phases
        if current_phase <= 2 and user_id:  # Phase 1-2: opt-in available
            if user_id in self.user_preferences:
                if not self.user_preferences[user_id]:  # User opted out
                    return RatingMethod.FARGO
        
        # Phase 1: Return both but don't show UI
        if current_phase == 1:
            return RatingMethod.BOTH
        
        # Phase 2: Return both, user sees Alfa via optional query param
        if current_phase == 2:
            if self.feature_flag_manager.is_enabled("alfa_predictions_in_api"):
                return RatingMethod.BOTH
            return RatingMethod.FARGO
        
        # Phase 3+: Return both for comparison
        if current_phase >= 3:
            if self.feature_flag_manager.is_enabled("alfa_vs_fargo_comparison"):
                return RatingMethod.BOTH
        
        return RatingMethod.ALFA
    
    def should_use_alfa(
        self,
        tournament_id: str,
        tournament_type: str = "league",
        percentage: int = 0
    ) -> bool:
        """
        Determine if tournament should use Alfa based on stratified rollout.
        
        Stratification ensures even distribution across tournament types
        while respecting rollout percentage.
        
        Args:
            tournament_id: Tournament identifier
            tournament_type: Type of tournament
            percentage: Current rollout percentage (0-100)
            
        Returns:
            True if tournament should use Alfa
        """
        if percentage == 0:
            return False
        
        if percentage == 100:
            return True
        
        # Use tournament_id hash for consistent, stratified assignment
        # This ensures same tournament always gets same treatment
        hash_input = f"{tournament_id}:{tournament_type}".encode()
        hash_value = int(hashlib.md5(hash_input).hexdigest(), 16)
        
        # Normalize hash to 0-100
        decision_value = (hash_value % 100) + 1  # 1-100 instead of 0-99
        
        return decision_value <= percentage
    
    def record_rollout_metrics(
        self,
        match_id: str,
        tournament_id: str,
        predictions_dict: Dict[str, Any]
    ) -> bool:
        """
        Record metrics for a match during rollout.
        
        Called after match prediction to log comparison data.
        
        Args:
            match_id: Match identifier
            tournament_id: Tournament identifier
            predictions_dict: Dict with:
                - 'outcome_actual': actual match result
                - 'outcome_predicted_alfa': Alfa prediction
                - 'outcome_predicted_fargo': Fargo prediction
                - 'brier_alfa': Alfa Brier score
                - 'brier_fargo': Fargo Brier score
                
        Returns:
            True if recorded successfully
        """
        try:
            # This would normally write to database
            # For now, log the metrics
            logger.info(
                f"Rollout metrics - Match: {match_id}, "
                f"Alfa Brier: {predictions_dict.get('brier_alfa'):.4f}, "
                f"Fargo Brier: {predictions_dict.get('brier_fargo'):.4f}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to record rollout metrics: {e}")
            return False
    
    def set_user_preference(self, user_id: str, use_alfa: bool) -> None:
        """
        Record user's preference for Alfa (opt-in/out).
        
        Args:
            user_id: User identifier
            use_alfa: True to opt-in to Alfa, False to opt-out
        """
        self.user_preferences[user_id] = use_alfa
        logger.info(f"User {user_id} preference set to use_alfa={use_alfa}")
    
    def get_user_preference(self, user_id: str) -> Optional[bool]:
        """
        Get user's preference for Alfa.
        
        Returns:
            None if not set, True if opted in, False if opted out
        """
        return self.user_preferences.get(user_id)
    
    def calculate_rollout_percentage(self) -> int:
        """
        Calculate current rollout percentage from feature flag.
        
        Returns:
            Percentage (0-100)
        """
        return self.feature_flag_manager.get_percentage("alfa_rating_enabled")
    
    def get_rollout_metrics(
        self,
        db_session = None,
        weeks: int = 4
    ) -> Optional[RolloutMetrics]:
        """
        Get comparison metrics between Alfa and Fargo.
        
        Should query rollout_tracking table from database.
        This is a placeholder that would be implemented with actual DB queries.
        
        Args:
            db_session: SQLAlchemy session
            weeks: Number of weeks to look back
            
        Returns:
            RolloutMetrics or None if no data
        """
        try:
            # Placeholder implementation
            # In production, this queries rollout_tracking table
            
            cutoff_date = datetime.utcnow() - timedelta(weeks=weeks)
            
            # These would come from database
            mock_metrics = RolloutMetrics(
                rollout_percentage=self.calculate_rollout_percentage(),
                avg_brier_alfa=0.25,
                avg_brier_fargo=0.26,
                improvement_pct=3.8,
                tournaments_completed=50,
                matches_total=1250,
                errors_count=2,
                error_rate=0.0016,
                anomalies_detected=10,
                anomalies_false_positive_rate=0.15
            )
            
            logger.info(f"Retrieved rollout metrics for last {weeks} weeks")
            return mock_metrics
        
        except Exception as e:
            logger.error(f"Failed to get rollout metrics: {e}")
            return None
    
    def _check_prerequisites_met(self, phase: int) -> bool:
        """Check that prerequisites for a phase are met."""
        valid, msg = self.feature_flag_manager.validate_rollout_prerequisites(phase)
        if not valid:
            logger.warning(f"Phase {phase} prerequisites not met: {msg}")
        return valid
    
    def create_rollout_checkpoint(self) -> Dict[str, Any]:
        """
        Create a checkpoint of current rollout state for rollback purposes.
        
        Returns:
            Checkpoint dict with state snapshot
        """
        checkpoint = {
            "timestamp": datetime.utcnow().isoformat(),
            "phase": self.feature_flag_manager.get_current_phase(),
            "phase_name": self.feature_flag_manager.get_phase_name(
                self.feature_flag_manager.get_current_phase()
            ),
            "percentage": self.calculate_rollout_percentage(),
            "flags": self.feature_flag_manager.get_all_flags(),
            "user_preferences": dict(self.user_preferences)
        }
        logger.info(f"Created rollout checkpoint: {checkpoint['phase_name']} ({checkpoint['percentage']}%)")
        return checkpoint
    
    def should_trigger_auto_rollback(self, metrics: RolloutMetrics) -> Tuple[bool, str]:
        """
        Determine if automatic rollback should be triggered.
        
        Triggers:
        - Brier score > 0.32 (degradation from staging baseline ~0.26)
        - Error rate > 2%
        - Multiple consecutive failures
        
        Args:
            metrics: Current rollout metrics
            
        Returns:
            (should_rollback: bool, reason: str)
        """
        # Check Brier score deviation
        brier_threshold = self.feature_flag_manager.flags.get(
            "alfa_rollback_enabled", {}
        ).get("auto_rollback_triggers", {}).get("brier_threshold", 0.32)
        
        if metrics.avg_brier_alfa > brier_threshold:
            return True, f"Brier score {metrics.avg_brier_alfa:.4f} exceeds threshold {brier_threshold}"
        
        # Check error rate
        error_threshold = self.feature_flag_manager.flags.get(
            "alfa_rollback_enabled", {}
        ).get("auto_rollback_triggers", {}).get("error_rate_threshold", 0.02)
        
        if metrics.error_rate > error_threshold:
            return True, f"Error rate {metrics.error_rate:.4f} exceeds threshold {error_threshold}"
        
        return False, "No rollback triggers met"


def create_rollout_manager(feature_flag_manager) -> RolloutManager:
    """Factory function to create rollout manager."""
    return RolloutManager(feature_flag_manager)
