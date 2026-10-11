"""
Model Performance Tracking for Alfa Rating Production System

Tracks in-production performance of Alfa model:
- Daily metrics: Brier, accuracy, calibration RMSE, AUC-ROC
- Compares to training metrics (should be within ±5%)
- Anomaly detection validation: Precision, Recall, F1-score
- Cold-start tracking: New player rating convergence
- Stores predictions for later analysis

Outputs:
- Daily performance report
- Comparison to training baseline
- Alerts on performance degradation
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from statistics import mean, stdev
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class PredictionOutcome(str, Enum):
    """Outcome of a prediction."""
    CORRECT = "correct"
    INCORRECT = "incorrect"
    UNKNOWN = "unknown"


class PerformanceMetric(str, Enum):
    """Performance metrics tracked."""
    BRIER = "brier"
    ACCURACY = "accuracy"
    CALIBRATION_RMSE = "calibration_rmse"
    AUC_ROC = "auc_roc"
    ANOMALY_PRECISION = "anomaly_precision"
    ANOMALY_RECALL = "anomaly_recall"
    ANOMALY_F1 = "anomaly_f1"


class Prediction:
    """
    Recorded prediction for later analysis.
    
    Attributes:
        match_id: Unique match identifier
        timestamp: When prediction was made
        predicted_prob: Predicted win probability (0-1)
        predicted_class: Binary prediction (0 or 1)
        actual_outcome: Actual match outcome (0, 1, or None if not yet known)
        player_id: ID of rated player
        is_sandbagging_flagged: Whether flagged as sandbagging
        flagged_correct: Whether sandbagging flag was correct (based on actual outcome)
    """
    
    def __init__(
        self,
        match_id: str,
        timestamp: datetime,
        predicted_prob: float,
        player_id: Optional[str] = None,
    ):
        """Initialize prediction record."""
        self.match_id = match_id
        self.timestamp = timestamp
        self.predicted_prob = predicted_prob
        self.predicted_class = 1 if predicted_prob >= 0.5 else 0
        self.actual_outcome: Optional[int] = None
        self.player_id = player_id
        self.is_sandbagging_flagged = False
        self.flagged_correct: Optional[bool] = None
    
    def set_outcome(self, outcome: int, sandbagging_detected: bool = False) -> None:
        """
        Set actual outcome when known.
        
        Args:
            outcome: 0 or 1 (loss or win)
            sandbagging_detected: Whether sandbagging was detected in actual play
        """
        self.actual_outcome = outcome
        if self.is_sandbagging_flagged:
            self.flagged_correct = (self.is_sandbagging_flagged == sandbagging_detected)
    
    def get_brier_score(self) -> Optional[float]:
        """
        Calculate Brier score for this prediction.
        
        Returns:
            (predicted - actual)^2 or None if outcome not known
        """
        if self.actual_outcome is None:
            return None
        return (self.predicted_prob - self.actual_outcome) ** 2
    
    def is_correct(self) -> Optional[bool]:
        """
        Check if prediction was correct.
        
        Returns:
            True/False if outcome known, None otherwise
        """
        if self.actual_outcome is None:
            return None
        return self.predicted_class == self.actual_outcome


class DailyPerformance:
    """
    Daily performance metrics aggregated from predictions.
    """
    
    def __init__(self, date: str):
        """
        Initialize daily performance.
        
        Args:
            date: Date in YYYY-MM-DD format
        """
        self.date = date
        self.predictions: List[Prediction] = []
        self.metrics: Dict[PerformanceMetric, float] = {}
    
    def add_prediction(self, pred: Prediction) -> None:
        """Add a prediction to the day."""
        self.predictions.append(pred)
    
    def compute_metrics(self) -> Dict[PerformanceMetric, float]:
        """
        Compute all performance metrics for the day.
        
        Returns:
            Dict of metric name -> value
        """
        # Filter predictions with known outcomes
        completed = [p for p in self.predictions if p.actual_outcome is not None]
        
        if not completed:
            logger.warning(f"No completed predictions for {self.date}")
            return {}
        
        metrics = {}
        
        # Brier Score: mean of (pred - actual)^2
        brier_scores = [p.get_brier_score() for p in completed if p.get_brier_score() is not None]
        if brier_scores:
            metrics[PerformanceMetric.BRIER] = mean(brier_scores)
        
        # Accuracy: % correct predictions
        correct = sum(1 for p in completed if p.is_correct())
        metrics[PerformanceMetric.ACCURACY] = correct / len(completed) if completed else 0
        
        # Calibration RMSE: sqrt(mean((predicted_prob - accuracy_bin)^2))
        # Group predictions into probability bins and compare to actual accuracy
        calibration_errors = []
        for bin_size in [0.1]:  # 10% bins
            for bin_start in [i * bin_size for i in range(int(1 / bin_size) + 1)]:
                bin_end = bin_start + bin_size
                bin_preds = [p for p in completed if bin_start <= p.predicted_prob < bin_end]
                if bin_preds:
                    bin_accuracy = sum(1 for p in bin_preds if p.is_correct()) / len(bin_preds)
                    bin_predicted_prob = mean(p.predicted_prob for p in bin_preds)
                    error = (bin_predicted_prob - bin_accuracy) ** 2
                    calibration_errors.append(error)
        
        if calibration_errors:
            metrics[PerformanceMetric.CALIBRATION_RMSE] = (sum(calibration_errors) / len(calibration_errors)) ** 0.5
        
        # AUC-ROC: Approximation using Mann-Whitney U statistic
        # For simplicity, using threshold-based approximation
        metrics[PerformanceMetric.AUC_ROC] = self._compute_auc_approximation(completed)
        
        self.metrics = metrics
        return metrics
    
    def _compute_auc_approximation(self, predictions: List[Prediction]) -> float:
        """
        Approximate AUC-ROC from predictions.
        
        Uses ranking-based approximation:
        AUC ≈ (# correctly ranked pairs) / (# possible pairs)
        """
        positives = [p for p in predictions if p.actual_outcome == 1]
        negatives = [p for p in predictions if p.actual_outcome == 0]
        
        if not positives or not negatives:
            return 0.5  # Undefined, return baseline
        
        correct_pairs = 0
        total_pairs = len(positives) * len(negatives)
        
        for pos in positives:
            for neg in negatives:
                if pos.predicted_prob > neg.predicted_prob:
                    correct_pairs += 1
                elif pos.predicted_prob == neg.predicted_prob:
                    correct_pairs += 0.5
        
        return correct_pairs / total_pairs if total_pairs > 0 else 0.5
    
    def get_metric(self, metric: PerformanceMetric) -> Optional[float]:
        """Get a specific metric value."""
        return self.metrics.get(metric, None)


class AnomalyDetectionValidation:
    """
    Validation of anomaly detection (sandbagging flagging) in production.
    
    Tracks:
    - Predictions flagged as sandbagging
    - Whether flag was correct (based on actual outcome)
    - Precision: % of flags that predicted future bad behavior
    - Recall: % of actual sandbagging incidents that were flagged
    - F1-score: Harmonic mean of precision and recall
    """
    
    def __init__(self):
        """Initialize anomaly validation."""
        self.flagged_predictions: List[Prediction] = []
        self.ground_truth_sandbagging: List[Prediction] = []
    
    def add_flagged_prediction(self, pred: Prediction) -> None:
        """Record a prediction flagged as sandbagging."""
        self.flagged_predictions.append(pred)
    
    def add_ground_truth(self, pred: Prediction, is_sandbagging: bool) -> None:
        """
        Add ground truth for a player (detected sandbagging).
        
        Args:
            pred: Prediction that should have been flagged
            is_sandbagging: Whether sandbagging occurred
        """
        if is_sandbagging:
            self.ground_truth_sandbagging.append(pred)
    
    def compute_metrics(self) -> Dict[str, float]:
        """
        Compute precision, recall, F1 for anomaly detection.
        
        Returns:
            Dict with precision, recall, f1 scores
        """
        # Predictions with known outcomes
        flagged_completed = [p for p in self.flagged_predictions if p.flagged_correct is not None]
        ground_truth_completed = [p for p in self.ground_truth_sandbagging if p.actual_outcome is not None]
        
        if not flagged_completed and not ground_truth_completed:
            return {
                "precision": 0.5,
                "recall": 0.5,
                "f1": 0.5,
                "num_flagged": 0,
                "num_ground_truth": 0,
            }
        
        # True positives: flagged AND correct
        true_positives = sum(1 for p in flagged_completed if p.flagged_correct)
        
        # False positives: flagged BUT incorrect
        false_positives = sum(1 for p in flagged_completed if not p.flagged_correct)
        
        # False negatives: should have been flagged but weren't
        false_negatives = len(ground_truth_completed) - true_positives
        
        # Precision: TP / (TP + FP)
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        
        # Recall: TP / (TP + FN)
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        
        # F1: 2 * (precision * recall) / (precision + recall)
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        return {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "true_positives": true_positives,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "num_flagged": len(flagged_completed),
            "num_ground_truth": len(ground_truth_completed),
        }


class ColdStartTracking:
    """
    Track convergence of new player ratings.
    
    Monitors:
    - How quickly new player ratings converge to stable value
    - % of players converged within ±20, ±30, ±50 points by game N
    - Compares to training baseline (target: 52% within ±30 pts by game 20)
    """
    
    def __init__(self):
        """Initialize cold-start tracking."""
        self.new_players: Dict[str, Dict[str, Any]] = {}  # player_id -> data
    
    def track_new_player(
        self,
        player_id: str,
        initial_rating: float,
    ) -> None:
        """
        Start tracking a new player.
        
        Args:
            player_id: Unique player ID
            initial_rating: Initial rating (e.g., 1200)
        """
        self.new_players[player_id] = {
            "initial_rating": initial_rating,
            "ratings": [initial_rating],
            "games_played": 0,
            "converged_at": None,
            "final_rating": None,
        }
    
    def update_player_rating(
        self,
        player_id: str,
        new_rating: float,
        convergence_threshold: float = 30,
    ) -> None:
        """
        Update player rating and check for convergence.
        
        Args:
            player_id: Player ID
            new_rating: Updated rating
            convergence_threshold: Rating delta threshold for convergence
        """
        if player_id not in self.new_players:
            logger.warning(f"Player {player_id} not tracked for cold-start")
            return
        
        player = self.new_players[player_id]
        player["ratings"].append(new_rating)
        player["games_played"] += 1
        player["final_rating"] = new_rating
        
        # Check convergence: if last 5 games have small variance
        if len(player["ratings"]) >= 5:
            last_5 = player["ratings"][-5:]
            rating_variance = max(last_5) - min(last_5)
            
            if rating_variance < convergence_threshold and player["converged_at"] is None:
                player["converged_at"] = player["games_played"]
                logger.info(f"Player {player_id} converged after {player['games_played']} games")
    
    def get_convergence_stats(
        self,
        num_games: int = 20,
        thresholds: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Get convergence statistics for new players.
        
        Args:
            num_games: Number of games to check (default 20)
            thresholds: Point thresholds to check (default [20, 30, 50])
        
        Returns:
            Stats dict with convergence percentages
        """
        if thresholds is None:
            thresholds = [20, 30, 50]
        
        # Only look at players with at least num_games
        eligible = {
            pid: p for pid, p in self.new_players.items()
            if p["games_played"] >= num_games
        }
        
        if not eligible:
            return {
                "num_games": num_games,
                "num_players_tracked": len(self.new_players),
                "num_players_eligible": 0,
                "convergence_by_threshold": {},
            }
        
        results = {
            "num_games": num_games,
            "num_players_tracked": len(self.new_players),
            "num_players_eligible": len(eligible),
            "convergence_by_threshold": {},
            "avg_convergence_games": 0,
        }
        
        # Calculate convergence percentages
        for threshold in thresholds:
            converged = sum(
                1 for p in eligible.values()
                if p["converged_at"] is not None and p["converged_at"] <= num_games
                and abs(p["final_rating"] - p["initial_rating"]) <= threshold
            )
            percent = (converged / len(eligible) * 100) if eligible else 0
            results["convergence_by_threshold"][f"±{threshold}pts"] = round(percent, 1)
        
        # Average convergence games
        convergence_games = [
            p["converged_at"] for p in eligible.values()
            if p["converged_at"] is not None
        ]
        if convergence_games:
            results["avg_convergence_games"] = round(mean(convergence_games), 1)
        
        return results


class PerformanceTracker:
    """
    Main tracker for model performance in production.
    
    Aggregates daily performance, anomaly detection, and cold-start metrics.
    """
    
    def __init__(self, baseline_metrics: Optional[Dict[str, float]] = None):
        """
        Initialize tracker.
        
        Args:
            baseline_metrics: Baseline metrics from training
        """
        self.baseline_metrics = baseline_metrics or {}
        self.daily_performance: Dict[str, DailyPerformance] = {}
        self.anomaly_validation = AnomalyDetectionValidation()
        self.cold_start = ColdStartTracking()
        self.all_predictions: List[Prediction] = []
    
    def record_prediction(
        self,
        match_id: str,
        predicted_prob: float,
        player_id: Optional[str] = None,
        is_sandbagging_flagged: bool = False,
        timestamp: Optional[datetime] = None,
    ) -> Prediction:
        """
        Record a prediction.
        
        Args:
            match_id: Unique match ID
            predicted_prob: Predicted win probability
            player_id: ID of rated player (optional)
            is_sandbagging_flagged: Whether flagged as sandbagging
            timestamp: Prediction timestamp
        
        Returns:
            Prediction object
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        pred = Prediction(match_id, timestamp, predicted_prob, player_id)
        pred.is_sandbagging_flagged = is_sandbagging_flagged
        
        # Add to daily performance
        date_str = timestamp.strftime("%Y-%m-%d")
        if date_str not in self.daily_performance:
            self.daily_performance[date_str] = DailyPerformance(date_str)
        self.daily_performance[date_str].add_prediction(pred)
        
        # Track flagged predictions for anomaly validation
        if is_sandbagging_flagged:
            self.anomaly_validation.add_flagged_prediction(pred)
        
        self.all_predictions.append(pred)
        return pred
    
    def set_outcome(
        self,
        match_id: str,
        outcome: int,
        sandbagging_detected: bool = False,
    ) -> None:
        """
        Set outcome for a recorded prediction.
        
        Args:
            match_id: Match ID
            outcome: 0 or 1
            sandbagging_detected: Whether sandbagging occurred
        """
        # Find prediction
        pred = next((p for p in self.all_predictions if p.match_id == match_id), None)
        if not pred:
            logger.warning(f"Prediction {match_id} not found for outcome setting")
            return
        
        pred.set_outcome(outcome, sandbagging_detected)
    
    def get_daily_metrics(self, date: str) -> Dict[PerformanceMetric, float]:
        """
        Get metrics for a specific day.
        
        Args:
            date: Date in YYYY-MM-DD format
        
        Returns:
            Dict of metrics
        """
        if date not in self.daily_performance:
            return {}
        
        daily = self.daily_performance[date]
        return daily.compute_metrics()
    
    def compare_to_baseline(self) -> Dict[str, Any]:
        """
        Compare recent performance to training baseline.
        
        Returns:
            Comparison dict with deltas
        """
        # Get metrics from last 7 days
        recent_dates = sorted(self.daily_performance.keys())[-7:]
        all_recent_metrics = []
        
        for date in recent_dates:
            metrics = self.get_daily_metrics(date)
            all_recent_metrics.append(metrics)
        
        if not all_recent_metrics:
            return {"error": "No recent metrics"}
        
        # Aggregate
        aggregated = {}
        for metric in PerformanceMetric:
            values = [
                m[metric] for m in all_recent_metrics
                if metric in m and m[metric] is not None
            ]
            if values:
                aggregated[metric.value] = {
                    "mean": round(mean(values), 4),
                    "min": round(min(values), 4),
                    "max": round(max(values), 4),
                }
        
        # Compare to baseline
        comparison = {
            "current": aggregated,
            "baseline": self.baseline_metrics,
            "deltas": {},
            "alerts": [],
        }
        
        for metric_str, current in aggregated.items():
            baseline_val = self.baseline_metrics.get(metric_str)
            if baseline_val is None:
                continue
            
            current_mean = current["mean"]
            delta = current_mean - baseline_val
            delta_percent = (delta / baseline_val * 100) if baseline_val != 0 else 0
            
            comparison["deltas"][metric_str] = {
                "baseline": baseline_val,
                "current": current_mean,
                "delta": round(delta, 4),
                "delta_percent": round(delta_percent, 1),
            }
            
            # Alert if delta > 5%
            if abs(delta_percent) > 5:
                level = "WARNING" if abs(delta_percent) <= 10 else "CRITICAL"
                comparison["alerts"].append({
                    "level": level,
                    "metric": metric_str,
                    "message": f"{metric_str} drifted {delta_percent:+.1f}% from baseline",
                })
        
        return comparison


def get_performance_tracker(baseline_metrics: Optional[Dict[str, float]] = None) -> PerformanceTracker:
    """Get or create performance tracker."""
    return PerformanceTracker(baseline_metrics)
