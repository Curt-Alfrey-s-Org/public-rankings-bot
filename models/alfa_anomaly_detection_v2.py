"""
ALFa Anomaly Detection v2 - Optimized Thresholds.

Thresholds optimized via statistical analysis on training data.
See: metrics/ANOMALY_THRESHOLD_TUNING_REPORT.md
"""

from models.alfa_anomaly_detection import AnomalyDetector as BaseDetector, AnomalyFlags, PlayerMatchHistory, analyze_anomalies_batch


class AnomalyDetectorV2(BaseDetector):
    """Optimized anomaly detector with tuned thresholds."""
    
    # OPTIMIZED thresholds
    SUDDEN_JUMP_THRESHOLD = 40
    WEAK_ONLY_WINRATE_THRESHOLD = 0.65
    STRONG_ONLY_LOSSRATE_THRESHOLD = 0.65
    HIGH_VARIANCE_THRESHOLD = 0.25
    BREAK_DOMINANCE_THRESHOLD = 0.6


# For backwards compatibility
AnomalyDetector = AnomalyDetectorV2
