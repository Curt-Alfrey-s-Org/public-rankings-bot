"""
Data Drift Detection for Alfa Rating Production System

Monitors input and output feature distributions for significant changes.
Detects drift when distributions shift >2 standard deviations from training.

Monitors:
- Input features: rating_diff, race_to distributions
- Output: Player win rates vs training distribution
- Convergence: New player rating convergence rate

Actions on drift:
- Auto-notify data science team
- Flag for retraining investigation
- Track drift_detection table for analysis
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from statistics import mean, stdev
from enum import Enum
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class DriftType(str, Enum):
    """Types of data drift."""
    INPUT_DRIFT = "input_drift"
    OUTPUT_DRIFT = "output_drift"
    CONVERGENCE_DRIFT = "convergence_drift"


class DriftSeverity(str, Enum):
    """Severity of drift detected."""
    MINOR = "minor"  # 1-2 std
    MODERATE = "moderate"  # 2-3 std
    SEVERE = "severe"  # >3 std


class FeatureStatistics:
    """Training baseline statistics for a feature."""
    
    def __init__(
        self,
        feature_name: str,
        mean: float,
        std: float,
        min_val: float,
        max_val: float,
        count: int,
    ):
        """Initialize feature statistics."""
        self.feature_name = feature_name
        self.mean = mean
        self.std = std
        self.min = min_val
        self.max = max_val
        self.count = count
    
    def _calculate_z_score(self, value: float) -> float:
        """Calculate z-score of a value."""
        if self.std == 0:
            return 0 if value == self.mean else float('inf')
        return abs((value - self.mean) / self.std)
    
    def check_drift(self, value: float, threshold_std: float = 2.0) -> Tuple[bool, float]:
        """
        Check if value exhibits drift.
        
        Returns:
            (is_drift, z_score)
        """
        z_score = self._calculate_z_score(value)
        is_drift = z_score > threshold_std
        return is_drift, z_score


class TrainingBaseline:
    """
    Training baseline statistics for Alfa model.
    
    Contains statistics for all input and output features
    used to detect drift in production.
    """
    
    def __init__(self):
        """Initialize baseline."""
        self.features: Dict[str, FeatureStatistics] = {}
        self.created_at = datetime.now(timezone.utc)
    
    def add_feature(self, feature_name: str, stats: Dict[str, float]) -> None:
        """
        Add feature statistics.
        
        Args:
            feature_name: Name of feature
            stats: Dict with keys: mean, std, min, max, count
        """
        self.features[feature_name] = FeatureStatistics(
            feature_name=feature_name,
            mean=stats["mean"],
            std=stats["std"],
            min_val=stats["min"],
            max_val=stats["max"],
            count=stats["count"],
        )
    
    def load_from_dict(self, data: Dict[str, Any]) -> None:
        """Load baseline from dictionary (e.g., from JSON)."""
        for feature_name, stats in data.items():
            self.add_feature(feature_name, stats)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            fname: {
                "mean": f.mean,
                "std": f.std,
                "min": f.min,
                "max": f.max,
                "count": f.count,
            }
            for fname, f in self.features.items()
        }


class ProductionStatistics:
    """Observed statistics from production data."""
    
    def __init__(self, window_hours: int = 24):
        """
        Initialize statistics tracker.
        
        Args:
            window_hours: Time window for statistics
        """
        self.window_hours = window_hours
        self.observations: Dict[str, List[float]] = {}
        self.timestamp = datetime.now(timezone.utc)
    
    def add_observation(self, feature_name: str, value: float) -> None:
        """Add an observation for a feature."""
        if feature_name not in self.observations:
            self.observations[feature_name] = []
        self.observations[feature_name].append(value)
    
    def get_statistics(self, feature_name: str) -> Optional[Dict[str, float]]:
        """
        Get statistics for a feature.
        
        Returns:
            Dict with mean, std, min, max or None if insufficient data
        """
        if feature_name not in self.observations:
            return None
        
        values = self.observations[feature_name]
        if len(values) < 2:
            return None
        
        return {
            "mean": mean(values),
            "std": stdev(values) if len(values) > 1 else 0,
            "min": min(values),
            "max": max(values),
            "count": len(values),
        }


class DriftDetector:
    """
    Detects data drift by comparing production to training baseline.
    
    Drift Detection Strategy:
    1. Input drift: Monitor rating_diff and race_to distributions
    2. Output drift: Track player win rate distribution changes
    3. Convergence drift: Monitor new player convergence speed
    """
    
    def __init__(self, baseline: Optional[TrainingBaseline] = None):
        """
        Initialize drift detector.
        
        Args:
            baseline: Training baseline statistics
        """
        self.baseline = baseline or TrainingBaseline()
        self.production_stats = ProductionStatistics()
        self.drift_events: List[Dict[str, Any]] = []
        self.drift_threshold_std = 2.0  # 2 standard deviations
    
    def load_baseline_from_file(self, file_path: str) -> None:
        """
        Load baseline from JSON file.
        
        File format:
        {
            "training_stats": {
                "feature_name": {"mean": X, "std": Y, "min": Z, "max": W, "count": N},
                ...
            }
        }
        """
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            training_stats = data.get("training_stats", {})
            self.baseline.load_from_dict(training_stats)
            logger.info(f"Baseline loaded from {file_path}: {len(self.baseline.features)} features")
        except Exception as e:
            logger.error(f"Failed to load baseline: {e}")
    
    def analyze_input_feature(self, feature_name: str, value: float) -> Optional[Dict[str, Any]]:
        """
        Analyze input feature for drift.
        
        Args:
            feature_name: Name of feature (e.g., "rating_diff", "race_to")
            value: Observed value
        
        Returns:
            Drift event dict if drift detected, None otherwise
        """
        # Record observation
        self.production_stats.add_observation(feature_name, value)
        
        # Check if feature in baseline
        if feature_name not in self.baseline.features:
            logger.debug(f"Feature {feature_name} not in baseline, skipping drift check")
            return None
        
        baseline_feature = self.baseline.features[feature_name]
        is_drift, z_score = baseline_feature.check_drift(value, self.drift_threshold_std)
        
        if not is_drift:
            return None
        
        # Determine severity
        if z_score > 3.0:
            severity = DriftSeverity.SEVERE
        elif z_score > 2.0:
            severity = DriftSeverity.MODERATE
        else:
            severity = DriftSeverity.MINOR
        
        # Log drift event
        drift_event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "drift_type": DriftType.INPUT_DRIFT.value,
            "feature": feature_name,
            "severity": severity.value,
            "z_score": round(z_score, 2),
            "value": value,
            "baseline_mean": baseline_feature.mean,
            "baseline_std": baseline_feature.std,
        }
        
        self.drift_events.append(drift_event)
        logger.warning(f"Input drift detected: {feature_name} (z={z_score:.2f}, severity={severity.value})")
        
        return drift_event
    
    def analyze_output_distribution(
        self,
        observed_win_rates: List[float],
        training_win_rate_mean: float,
        training_win_rate_std: float,
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze player win rate distribution for drift.
        
        Args:
            observed_win_rates: List of observed win rates in production
            training_win_rate_mean: Mean win rate from training
            training_win_rate_std: Std dev of win rate from training
        
        Returns:
            Drift event dict if drift detected, None otherwise
        """
        if len(observed_win_rates) < 10:
            logger.debug(f"Insufficient observations ({len(observed_win_rates)}) for output drift check")
            return None
        
        observed_mean = mean(observed_win_rates)
        observed_std = stdev(observed_win_rates) if len(observed_win_rates) > 1 else 0
        
        # Calculate z-score for mean shift
        if training_win_rate_std == 0:
            z_score = 0 if observed_mean == training_win_rate_mean else float('inf')
        else:
            z_score = abs((observed_mean - training_win_rate_mean) / training_win_rate_std)
        
        is_drift = z_score > self.drift_threshold_std
        if not is_drift:
            return None
        
        # Determine severity
        if z_score > 3.0:
            severity = DriftSeverity.SEVERE
        elif z_score > 2.0:
            severity = DriftSeverity.MODERATE
        else:
            severity = DriftSeverity.MINOR
        
        # Log drift event
        drift_event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "drift_type": DriftType.OUTPUT_DRIFT.value,
            "feature": "player_win_rates",
            "severity": severity.value,
            "z_score": round(z_score, 2),
            "observed_mean": round(observed_mean, 3),
            "observed_std": round(observed_std, 3),
            "training_mean": round(training_win_rate_mean, 3),
            "training_std": round(training_win_rate_std, 3),
            "num_samples": len(observed_win_rates),
        }
        
        self.drift_events.append(drift_event)
        logger.warning(f"Output drift detected: player_win_rates (z={z_score:.2f}, severity={severity.value})")
        
        return drift_event
    
    def analyze_convergence_drift(
        self,
        new_players_convergence_rate: float,
        training_convergence_rate: float,
        threshold_percent: float = 10.0,
    ) -> Optional[Dict[str, Any]]:
        """
        Detect degradation in new player rating convergence.
        
        Args:
            new_players_convergence_rate: % of new players converged in current window
            training_convergence_rate: Expected rate from training
            threshold_percent: Alert if drift >threshold_percent
        
        Returns:
            Drift event dict if drift detected, None otherwise
        """
        percent_change = abs(new_players_convergence_rate - training_convergence_rate)
        
        if percent_change <= threshold_percent:
            return None
        
        # Determine severity based on percent change
        if percent_change > 30:
            severity = DriftSeverity.SEVERE
        elif percent_change > 20:
            severity = DriftSeverity.MODERATE
        else:
            severity = DriftSeverity.MINOR
        
        drift_event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "drift_type": DriftType.CONVERGENCE_DRIFT.value,
            "feature": "new_player_convergence",
            "severity": severity.value,
            "percent_change": round(percent_change, 2),
            "observed_rate": round(new_players_convergence_rate, 2),
            "expected_rate": round(training_convergence_rate, 2),
            "message": f"Convergence degraded by {percent_change:.1f}%",
        }
        
        self.drift_events.append(drift_event)
        logger.warning(f"Convergence drift detected (change={percent_change:.1f}%, severity={severity.value})")
        
        return drift_event
    
    def get_recent_drift_events(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get drift events from the past N hours.
        
        Args:
            hours: Time window
        
        Returns:
            List of drift events
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return [
            e for e in self.drift_events
            if datetime.fromisoformat(e["timestamp"]) > cutoff
        ]
    
    def get_drift_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get summary of drift events.
        
        Args:
            hours: Time window
        
        Returns:
            Summary dict
        """
        recent = self.get_recent_drift_events(hours)
        
        summary = {
            "window_hours": hours,
            "total_events": len(recent),
            "by_type": {},
            "by_severity": {},
            "by_feature": {},
            "events": recent,
        }
        
        for event in recent:
            # By type
            dtype = event["drift_type"]
            if dtype not in summary["by_type"]:
                summary["by_type"][dtype] = 0
            summary["by_type"][dtype] += 1
            
            # By severity
            severity = event["severity"]
            if severity not in summary["by_severity"]:
                summary["by_severity"][severity] = 0
            summary["by_severity"][severity] += 1
            
            # By feature
            feature = event["feature"]
            if feature not in summary["by_feature"]:
                summary["by_feature"][feature] = 0
            summary["by_feature"][feature] += 1
        
        return summary
    
    def recommend_retraining(self) -> Tuple[bool, str]:
        """
        Recommend retraining based on drift severity.
        
        Returns:
            (should_retrain, reason)
        """
        recent_drift = self.get_recent_drift_events(hours=24)
        
        # Count by severity
        severe_count = sum(1 for e in recent_drift if e["severity"] == DriftSeverity.SEVERE.value)
        moderate_count = sum(1 for e in recent_drift if e["severity"] == DriftSeverity.MODERATE.value)
        
        if severe_count >= 3:
            return True, f"Multiple severe drift events ({severe_count})"
        
        if moderate_count >= 10:
            return True, f"High frequency moderate drift ({moderate_count})"
        
        # Check 7-day trending
        week_drift = self.get_recent_drift_events(hours=168)
        if len(week_drift) > 50:
            return True, f"Sustained drift over 7 days ({len(week_drift)} events)"
        
        return False, "No immediate retraining needed"


def get_drift_detector(baseline: Optional[TrainingBaseline] = None) -> DriftDetector:
    """Get or create drift detector instance."""
    return DriftDetector(baseline)
