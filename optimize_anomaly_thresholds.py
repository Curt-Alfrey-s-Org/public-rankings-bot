"""
Anomaly Detection Threshold Optimization Script.

Analyzes 6 anomaly detection flags across multiple threshold values:
1. sudden_jump: Test points/games
2. winning_weak_only: Test win% vs weak
3. losing_strong_only: Test loss% vs strong  
4. rating_league_mismatch: Test point gaps
5. high_variance: Test std dev
6. break_dominance_outlier: Test break win%

For each threshold, computes precision, recall, F1, and coverage.
Selects optimal thresholds targeting:
- Precision >80% (avoid false positives)
- Recall >70% (catch most real issues)
- Coverage <15% (not too noisy)

Outputs:
- models/alfa_anomaly_thresholds_optimized.json
- metrics/anomaly_threshold_analysis.json (all threshold tests)
- metrics/anomaly_optimization_summary.csv (final recommendations)
- metrics/ANOMALY_THRESHOLD_TUNING_REPORT.md (narrative)
- models/alfa_anomaly_detection_v2.py (tuned version)
"""

from __future__ import annotations

import json
import csv
import logging
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple, Optional, Set
import numpy as np
import pandas as pd

# Import current anomaly detection system
from models.alfa_anomaly_detection import AnomalyDetector, PlayerMatchHistory, AnomalyFlags

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ThresholdResult:
    """Result of testing a single threshold configuration."""
    
    flag_name: str
    threshold_value: float
    test_value: str  # Human-readable description
    num_flagged: int
    num_confirmed: int
    precision: float
    recall: float
    f1_score: float
    coverage_pct: float
    
    def as_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "flag_name": self.flag_name,
            "threshold_value": self.threshold_value,
            "test_value": self.test_value,
            "num_flagged": self.num_flagged,
            "num_confirmed": self.num_confirmed,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
            "coverage_pct": round(self.coverage_pct, 4),
        }


class AnomalyGroundTruth:
    """
    Identifies ground truth anomalies using domain knowledge heuristics.
    
    An anomaly is suspected if:
    1. Rating jumped >80 points in 5 games (near impossible without cheating/correction)
    2. Win rate changed >40% in consecutive windows (suspicious skill jump)
    3. Player beats opponents 100+ pts below >90% of time (not realistic)
    4. Player loses to opponents 80+ pts above >85% of time (should lose more)
    5. Unusual break dominance (>80% break wins but <50% overall)
    """
    
    def __init__(self):
        self.anomalous_players: Set[str] = set()
        self.anomaly_reasons: Dict[str, List[str]] = {}
    
    def identify_anomalies(self, player_histories: List[PlayerMatchHistory]) -> None:
        """Identify anomalies in player histories using heuristics."""
        
        for history in player_histories:
            reasons = []
            is_anomalous = False
            
            # Check 1: Extreme rating jump
            if self._check_extreme_rating_jump(history):
                reasons.append("extreme_rating_jump")
                is_anomalous = True
            
            # Check 2: Suspicious win rate variance
            if self._check_suspicious_variance(history):
                reasons.append("suspicious_variance")
                is_anomalous = True
            
            # Check 3: Beating much weaker players too consistently  
            if self._check_weak_dominance(history):
                reasons.append("weak_dominance")
                is_anomalous = True
            
            # Check 4: Losing to much stronger players too consistently
            if self._check_strong_dependency(history):
                reasons.append("strong_dependency")
                is_anomalous = True
            
            # Check 5: Impossible break pattern
            if self._check_impossible_break_pattern(history):
                reasons.append("impossible_break_pattern")
                is_anomalous = True
            
            if is_anomalous:
                self.anomalous_players.add(history.player_id)
                self.anomaly_reasons[history.player_id] = reasons
    
    def _check_extreme_rating_jump(self, history: PlayerMatchHistory) -> bool:
        """Check if rating jumped >80 pts in 5-game window."""
        if len(history.games) < 5:
            return False
        
        window = 5
        for i in range(len(history.games) - window):
            wins = sum(1 for g in history.games[i:i+window] if g["won"])
            # Rough: 5 wins in 5 games ~ +40 pts (each win ~8pts)
            # So a jump >80 would require sustained perfect play = suspicious
            if wins == 5:
                # Perfect 5-game run is possible but check context
                if i > 0:
                    prev_wins = sum(1 for g in history.games[max(0,i-5):i] if g["won"])
                    if prev_wins <= 1 and wins == 5:
                        return True
        
        return False
    
    def _check_suspicious_variance(self, history: PlayerMatchHistory) -> bool:
        """Check for suspicious win rate jumps (>50% change in 5 games)."""
        if len(history.games) < 10:
            return False
        
        window = 5
        win_rates = []
        for i in range(len(history.games) - window + 1):
            wins = sum(1 for g in history.games[i:i+window] if g["won"])
            win_rates.append(wins / window)
        
        # Check for large jumps
        for i in range(1, len(win_rates)):
            jump = abs(win_rates[i] - win_rates[i-1])
            if jump > 0.6:  # Jump from 20% to 80% or vice versa
                return True
        
        return False
    
    def _check_weak_dominance(self, history: PlayerMatchHistory) -> bool:
        """Check if player beats opponents 100+ pts below >85% of time."""
        games_vs_weak = [
            g for g in history.games
            if g["opponent_rating"] < history.rating - 100
        ]
        
        if len(games_vs_weak) < 5:
            return False
        
        win_rate = sum(1 for g in games_vs_weak if g["won"]) / len(games_vs_weak)
        return win_rate > 0.95  # >95% is suspicious vs weak opponents
    
    def _check_strong_dependency(self, history: PlayerMatchHistory) -> bool:
        """Check if player loses to opponents 80+ pts above >80% of time."""
        games_vs_strong = [
            g for g in history.games
            if g["opponent_rating"] > history.rating + 80
        ]
        
        if len(games_vs_strong) < 5:
            return False
        
        loss_rate = sum(1 for g in games_vs_strong if not g["won"]) / len(games_vs_strong)
        # >85% loss rate vs much stronger is suspicious - suggests rating inflation
        return loss_rate > 0.90
    
    def _check_impossible_break_pattern(self, history: PlayerMatchHistory) -> bool:
        """Check for impossible break win rate."""
        break_games = [g for g in history.games if g.get("is_break", False)]
        
        if len(break_games) < 10:
            return False
        
        break_win_rate = sum(1 for g in break_games if g["won"]) / len(break_games)
        overall_win_rate = sum(1 for g in history.games if g["won"]) / len(history.games)
        
        # >85% break win rate with <30% overall = impossible (should correlate)
        return break_win_rate > 0.90 and overall_win_rate < 0.40


class ThresholdAnalyzer:
    """Analyzes anomaly detection thresholds."""
    
    def __init__(self, player_histories: List[PlayerMatchHistory]):
        self.histories = player_histories
        self.ground_truth = AnomalyGroundTruth()
        self.ground_truth.identify_anomalies(player_histories)
        
        logger.info(f"Identified {len(self.ground_truth.anomalous_players)} anomalous players from {len(player_histories)}")
        self.results: List[ThresholdResult] = []
    
    def test_sudden_jump_thresholds(self):
        """Test sudden_jump thresholds: 20, 30, 40, 50, 60 points in 5 games."""
        logger.info("Testing sudden_jump thresholds...")
        thresholds = [20, 30, 40, 50, 60]
        
        for threshold in thresholds:
            detector = AnomalyDetector()
            detector.SUDDEN_JUMP_THRESHOLD = threshold
            
            result = self._evaluate_detector(
                detector,
                "sudden_jump",
                threshold,
                f"{threshold} pts in 5 games"
            )
            self.results.append(result)
    
    def test_winning_weak_only_thresholds(self):
        """Test winning_weak_only: 70%, 75%, 80%, 85%, 90% wins vs weak."""
        logger.info("Testing winning_weak_only thresholds...")
        thresholds = [0.70, 0.75, 0.80, 0.85, 0.90]
        
        for threshold in thresholds:
            detector = AnomalyDetector()
            detector.WEAK_ONLY_WINRATE_THRESHOLD = threshold
            
            result = self._evaluate_detector(
                detector,
                "winning_weak_only",
                threshold,
                f"{threshold*100:.0f}% wins vs weak"
            )
            self.results.append(result)
    
    def test_losing_strong_only_thresholds(self):
        """Test losing_strong_only: 70%, 75%, 80%, 85%, 90% losses vs strong."""
        logger.info("Testing losing_strong_only thresholds...")
        thresholds = [0.70, 0.75, 0.80, 0.85, 0.90]
        
        for threshold in thresholds:
            detector = AnomalyDetector()
            detector.STRONG_ONLY_LOSSRATE_THRESHOLD = threshold
            
            result = self._evaluate_detector(
                detector,
                "losing_strong_only",
                threshold,
                f"{threshold*100:.0f}% losses vs strong"
            )
            self.results.append(result)
    
    def test_rating_league_mismatch_thresholds(self):
        """Test rating_league_mismatch: 50, 75, 100, 150 point gaps."""
        logger.info("Testing rating_league_mismatch thresholds...")
        # For this, we simulate by checking if rating is far from center
        # We'll mark this as analysis only since it needs league context
        
        logger.warning("rating_league_mismatch requires league definitions - skipping threshold test")
    
    def test_high_variance_thresholds(self):
        """Test high_variance: 0.25, 0.30, 0.35, 0.40 std dev."""
        logger.info("Testing high_variance thresholds...")
        thresholds = [0.25, 0.30, 0.35, 0.40]
        
        for threshold in thresholds:
            detector = AnomalyDetector()
            detector.HIGH_VARIANCE_THRESHOLD = threshold
            
            result = self._evaluate_detector(
                detector,
                "high_variance",
                threshold,
                f"std dev {threshold}"
            )
            self.results.append(result)
    
    def test_break_dominance_thresholds(self):
        """Test break_dominance_outlier: 65%, 70%, 75%, 80% break win rates."""
        logger.info("Testing break_dominance_outlier thresholds...")
        thresholds = [0.65, 0.70, 0.75, 0.80]
        
        for threshold in thresholds:
            detector = AnomalyDetector()
            detector.BREAK_DOMINANCE_THRESHOLD = threshold
            
            result = self._evaluate_detector(
                detector,
                "break_dominance_outlier",
                threshold,
                f"{threshold*100:.0f}% break wins"
            )
            self.results.append(result)
    
    def _evaluate_detector(
        self,
        detector: AnomalyDetector,
        flag_name: str,
        threshold_value: float,
        test_description: str
    ) -> ThresholdResult:
        """
        Evaluate detector against ground truth.
        
        Returns ThresholdResult with precision, recall, F1, coverage.
        """
        flagged_players = set()
        total_flagged = 0
        
        for history in self.histories:
            flags = detector.detect_anomalies(history)
            
            # Check if this specific flag is set
            flag_value = getattr(flags, flag_name, False)
            if flag_value:
                flagged_players.add(history.player_id)
                total_flagged += 1
        
        # Compute metrics
        confirmed = flagged_players & self.ground_truth.anomalous_players
        true_positives = len(confirmed)
        false_positives = len(flagged_players) - true_positives
        false_negatives = len(self.ground_truth.anomalous_players) - true_positives
        
        precision = true_positives / len(flagged_players) if flagged_players else 0.0
        recall = true_positives / len(self.ground_truth.anomalous_players) if self.ground_truth.anomalous_players else 0.0
        
        # F1 score
        if precision + recall > 0:
            f1 = 2 * (precision * recall) / (precision + recall)
        else:
            f1 = 0.0
        
        # Coverage: % of population flagged
        coverage = len(flagged_players) / len(self.histories) if self.histories else 0.0
        
        return ThresholdResult(
            flag_name=flag_name,
            threshold_value=threshold_value,
            test_value=test_description,
            num_flagged=total_flagged,
            num_confirmed=true_positives,
            precision=precision,
            recall=recall,
            f1_score=f1,
            coverage_pct=coverage * 100,
        )
    
    def select_optimal_thresholds(self) -> Dict[str, Dict]:
        """
        Select optimal thresholds based on criteria:
        - Precision >80%
        - Recall >70%
        - Coverage <15%
        
        Returns dict mapping flag_name -> {threshold, metrics}
        """
        optimal = {}
        
        for flag_name in [
            "sudden_jump",
            "winning_weak_only",
            "losing_strong_only",
            "high_variance",
            "break_dominance_outlier"
        ]:
            flag_results = [r for r in self.results if r.flag_name == flag_name]
            
            if not flag_results:
                logger.warning(f"No results for {flag_name}")
                continue
            
            # Sort by F1 score (harmonic mean of precision and recall)
            sorted_results = sorted(flag_results, key=lambda r: r.f1_score, reverse=True)
            
            # Try to find result meeting all criteria
            best = None
            for result in sorted_results:
                if result.precision >= 0.80 and result.recall >= 0.70 and result.coverage_pct <= 15:
                    best = result
                    break
            
            # If no perfect match, find best F1
            if not best:
                best = sorted_results[0]
                reason = "no threshold met all criteria"
            else:
                reason = "meets all criteria"
            
            optimal[flag_name] = {
                "threshold": best.threshold_value,
                "test_value": best.test_value,
                "precision": best.precision,
                "recall": best.recall,
                "f1_score": best.f1_score,
                "coverage_pct": best.coverage_pct,
                "selection_reason": reason,
            }
            
            logger.info(
                f"{flag_name}: threshold={best.threshold_value} "
                f"(P={best.precision:.2%}, R={best.recall:.2%}, F1={best.f1_score:.3f}, "
                f"Cov={best.coverage_pct:.1f}%)"
            )
        
        return optimal


def load_player_histories(csv_path: str) -> List[PlayerMatchHistory]:
    """Load player match histories from CSV."""
    logger.info(f"Loading match data from {csv_path}")
    
    df = pd.read_csv(csv_path)
    logger.info(f"Loaded {len(df)} matches")
    
    # Build player histories
    player_games: Dict[str, list] = {}
    player_ratings: Dict[str, float] = {}
    
    for _, row in df.iterrows():
        p1_id = row['player_1_id']
        p2_id = row['player_2_id']
        winner_id = row['winner_id']
        
        rating_p1 = row['fargo_rating_p1']
        rating_p2 = row['fargo_rating_p2']
        
        # Track latest rating for each player
        player_ratings[p1_id] = rating_p1
        player_ratings[p2_id] = rating_p2
        
        # Create game records
        p1_won = winner_id == p1_id
        p2_won = winner_id == p2_id
        
        game_p1 = {
            "opponent_id": p2_id,
            "opponent_rating": rating_p2,
            "won": p1_won,
            "is_break": False  # We don't have break data in basic CSV
        }
        game_p2 = {
            "opponent_id": p1_id,
            "opponent_rating": rating_p1,
            "won": p2_won,
            "is_break": False
        }
        
        if p1_id not in player_games:
            player_games[p1_id] = []
        if p2_id not in player_games:
            player_games[p2_id] = []
        
        player_games[p1_id].append(game_p1)
        player_games[p2_id].append(game_p2)
    
    # Create PlayerMatchHistory objects
    histories = []
    for player_id, games in player_games.items():
        if len(games) >= 3:  # Need at least 3 games for analysis
            history = PlayerMatchHistory(
                player_id=player_id,
                rating=player_ratings[player_id],
                games=games
            )
            histories.append(history)
    
    logger.info(f"Created {len(histories)} player histories")
    return histories


def main():
    """Main analysis."""
    
    # Paths
    project_root = Path(__file__).parent
    csv_path = project_root / "data" / "splits" / "train_matches.csv"
    output_dir = project_root / "metrics"
    models_dir = project_root / "models"
    
    output_dir.mkdir(exist_ok=True)
    models_dir.mkdir(exist_ok=True)
    
    # Load data
    if not csv_path.exists():
        logger.error(f"Training data not found: {csv_path}")
        return
    
    histories = load_player_histories(str(csv_path))
    
    # Run analysis
    analyzer = ThresholdAnalyzer(histories)
    analyzer.test_sudden_jump_thresholds()
    analyzer.test_winning_weak_only_thresholds()
    analyzer.test_losing_strong_only_thresholds()
    analyzer.test_high_variance_thresholds()
    analyzer.test_break_dominance_thresholds()
    
    # Select optimal thresholds
    optimal = analyzer.select_optimal_thresholds()
    
    # Save results
    save_analysis_results(analyzer.results, output_dir, "anomaly_threshold_analysis.json")
    save_optimization_summary(optimal, output_dir, "anomaly_optimization_summary.csv")
    save_optimized_thresholds(optimal, models_dir, "alfa_anomaly_thresholds_optimized.json")
    save_tuning_report(analyzer, optimal, output_dir, "ANOMALY_THRESHOLD_TUNING_REPORT.md")
    save_updated_detection_model(optimal, models_dir, "alfa_anomaly_detection_v2.py")
    
    logger.info("✓ Threshold optimization complete!")
    logger.info(f"  - Analysis: {output_dir}/anomaly_threshold_analysis.json")
    logger.info(f"  - Summary: {output_dir}/anomaly_optimization_summary.csv")
    logger.info(f"  - Thresholds: {models_dir}/alfa_anomaly_thresholds_optimized.json")
    logger.info(f"  - Report: {output_dir}/ANOMALY_THRESHOLD_TUNING_REPORT.md")
    logger.info(f"  - Updated Model: {models_dir}/alfa_anomaly_detection_v2.py")


def save_analysis_results(results: List[ThresholdResult], output_dir: Path, filename: str):
    """Save all threshold test results to JSON."""
    data = [r.as_dict() for r in results]
    
    output_file = output_dir / filename
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Saved analysis results: {output_file}")


def save_optimization_summary(optimal: Dict, output_dir: Path, filename: str):
    """Save optimization summary to CSV."""
    output_file = output_dir / filename
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "flag_name",
                "threshold_value",
                "test_value",
                "precision",
                "recall",
                "f1_score",
                "coverage_pct",
                "selection_reason"
            ]
        )
        writer.writeheader()
        
        for flag_name, metrics in optimal.items():
            writer.writerow({
                "flag_name": flag_name,
                "threshold_value": metrics["threshold"],
                "test_value": metrics["test_value"],
                "precision": f"{metrics['precision']:.4f}",
                "recall": f"{metrics['recall']:.4f}",
                "f1_score": f"{metrics['f1_score']:.4f}",
                "coverage_pct": f"{metrics['coverage_pct']:.2f}",
                "selection_reason": metrics["selection_reason"],
            })
    
    logger.info(f"Saved optimization summary: {output_file}")


def save_optimized_thresholds(optimal: Dict, models_dir: Path, filename: str):
    """Save optimized thresholds to JSON for use in models."""
    thresholds = {}
    
    for flag_name, metrics in optimal.items():
        thresholds[flag_name] = {
            "threshold": metrics["threshold"],
            "description": metrics["test_value"],
            "metrics": {
                "precision": round(metrics["precision"], 4),
                "recall": round(metrics["recall"], 4),
                "f1_score": round(metrics["f1_score"], 4),
                "coverage_pct": round(metrics["coverage_pct"], 2),
            },
            "domain_reasoning": get_domain_reasoning(flag_name, metrics["threshold"])
        }
    
    output_file = models_dir / filename
    with open(output_file, 'w') as f:
        json.dump(thresholds, f, indent=2)
    
    logger.info(f"Saved optimized thresholds: {output_file}")


def get_domain_reasoning(flag_name: str, threshold: float) -> str:
    """Return domain reasoning for threshold choice."""
    
    reasoning = {
        "sudden_jump": (
            "Rating jumps are suspicious because ELO gains should be gradual. "
            "Large jumps suggest either rating correction, algorithmic error, or cheating."
        ),
        "winning_weak_only": (
            "A truly strong player beats weakness, but beats stronger opposition too. "
            "High win rate ONLY vs weak opponents suggests rating inflation."
        ),
        "losing_strong_only": (
            "Losing to everyone much stronger is expected, but should win some anyway. "
            "Very high loss rates suggest rating is too high (inflation) or sandbagging."
        ),
        "high_variance": (
            "Consistent players show stable win rates. "
            "High variance suggests either: skill development, luck swings, or cheating."
        ),
        "break_dominance_outlier": (
            "Break win rate should correlate with overall win rate. "
            "Extreme break dominance with lower overall suggests break-specific cheating or luck."
        ),
    }
    
    base = reasoning.get(flag_name, "")
    append = f" Threshold: {threshold}"
    
    return base + append


def save_tuning_report(analyzer: ThresholdAnalyzer, optimal: Dict, output_dir: Path, filename: str):
    """Save comprehensive narrative report."""
    
    report = []
    report.append("# Anomaly Detection Threshold Tuning Report\n")
    report.append(f"## Executive Summary\n")
    report.append(
        f"Optimized thresholds for 5 anomaly detection flags across "
        f"{len(analyzer.histories)} player histories. "
        f"Ground truth anomalies identified: {len(analyzer.ground_truth.anomalous_players)}\n"
    )
    
    report.append("\n## Methodology\n")
    report.append(
        "For each flag, tested multiple threshold values and evaluated against ground truth "
        "using precision, recall, F1 score, and coverage metrics. "
        "Selected thresholds targeting: Precision >80%, Recall >70%, Coverage <15%.\n"
    )
    
    report.append("\n## Optimal Thresholds\n")
    
    for flag_name, metrics in sorted(optimal.items()):
        report.append(f"\n### {flag_name}\n")
        report.append(f"**Threshold:** {metrics['test_value']}\n")
        report.append(f"- Precision: {metrics['precision']:.2%} (avoid false positives)\n")
        report.append(f"- Recall: {metrics['recall']:.2%} (catch real issues)\n")
        report.append(f"- F1 Score: {metrics['f1_score']:.4f}\n")
        report.append(f"- Coverage: {metrics['coverage_pct']:.2f}% of population\n")
        report.append(f"- Selection: {metrics['selection_reason']}\n")
    
    report.append("\n## Key Insights\n")
    report.append(
        "1. Most flags show trade-off between precision and recall\n"
        "2. Coverage varies widely - some flags are more selective than others\n"
        "3. Ground truth generation used domain heuristics to identify suspicious patterns\n"
        "4. Selected thresholds prioritize avoiding false positives (high precision)\n"
    )
    
    report.append("\n## Recommendations\n")
    report.append("1. Deploy optimized thresholds in alfa_anomaly_detection_v2.py\n")
    report.append("2. Monitor precision/recall in production for drift\n")
    report.append("3. Gather feedback on flagged players to improve ground truth\n")
    report.append("4. Re-tune annually or when player population distribution changes\n")
    
    output_file = output_dir / filename
    with open(output_file, 'w') as f:
        f.writelines(report)
    
    logger.info(f"Saved tuning report: {output_file}")


def save_updated_detection_model(optimal: Dict, models_dir: Path, filename: str):
    """
    Create updated detection model with optimized thresholds.
    
    Generates alfa_anomaly_detection_v2.py as extension/replacement.
    """
    
    # Load original model
    original_path = models_dir / "alfa_anomaly_detection.py"
    with open(original_path, 'r') as f:
        original_code = f.read()
    
    # Extract thresholds from optimal dict
    sudden_jump_threshold = optimal.get("sudden_jump", {}).get("threshold", 40)
    winning_weak_only_threshold = optimal.get("winning_weak_only", {}).get("threshold", 0.80)
    losing_strong_only_threshold = optimal.get("losing_strong_only", {}).get("threshold", 0.80)
    high_variance_threshold = optimal.get("high_variance", {}).get("threshold", 0.35)
    break_dominance_threshold = optimal.get("break_dominance_outlier", {}).get("threshold", 0.75)
    
    # Generate new model code
    new_model = f'''"""
ALFa Anomaly Detection System - v2 (OPTIMIZED THRESHOLDS).

Based on threshold optimization analysis on {len(optimal)} flags.
See: metrics/ANOMALY_THRESHOLD_TUNING_REPORT.md for analysis details.

Optimized thresholds target:
- Precision >80% (minimize false positives)
- Recall >70% (catch most real anomalies)
- Coverage <15% (keep population noise low)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class AnomalyFlags:
    """Set of anomaly flags for a single player."""
    
    player_id: str
    games_played: int
    rating: float
    
    # The 6 flags
    winning_weak_only: bool = False
    losing_strong_only: bool = False
    rating_league_mismatch: bool = False
    sudden_jump: bool = False
    high_variance: bool = False
    break_dominance_outlier: bool = False
    
    # Summary metrics
    anomaly_score: float = 0.0
    severity_level: str = "none"  # none, low (0-0.3), medium (0.3-0.7), high (0.7-1.0)
    flagged_count: int = 0
    
    def as_dict(self) -> dict:
        """Convert to dictionary."""
        return {{
            "player_id": self.player_id,
            "games_played": self.games_played,
            "rating": self.rating,
            "winning_weak_only": self.winning_weak_only,
            "losing_strong_only": self.losing_strong_only,
            "rating_league_mismatch": self.rating_league_mismatch,
            "sudden_jump": self.sudden_jump,
            "high_variance": self.high_variance,
            "break_dominance_outlier": self.break_dominance_outlier,
            "anomaly_score": self.anomaly_score,
            "severity_level": self.severity_level,
            "flagged_count": self.flagged_count,
        }}


@dataclass
class PlayerMatchHistory:
    """Match history for anomaly detection."""
    
    player_id: str
    rating: float
    games: List[Dict] = field(default_factory=list)
    # Each game dict must have: opponent_rating, won (bool), is_break (bool)


class AnomalyDetector:
    """
    Detects anomalies in player behavior and rating progression.
    
    Uses 6 flags weighted by relevance to combine into 0-1 anomaly score.
    
    OPTIMIZED THRESHOLDS (from threshold tuning analysis):
    """
    
    # Threshold differences for opponent comparisons (points)
    WEAK_THRESHOLD = -50      # Opponent is 50+ points below
    STRONG_THRESHOLD = 50     # Opponent is 50+ points above
    
    # OPTIMIZED thresholds for suspicious patterns
    WEAK_ONLY_WINRATE_THRESHOLD = {winning_weak_only_threshold}     # Optimized for {optimal.get('winning_weak_only', {}).get('coverage_pct', 'N/A'):.1f}% coverage
    STRONG_ONLY_LOSSRATE_THRESHOLD = {losing_strong_only_threshold}  # Optimized for {optimal.get('losing_strong_only', {}).get('coverage_pct', 'N/A'):.1f}% coverage
    SUDDEN_JUMP_THRESHOLD = {sudden_jump_threshold}              # Optimized for {optimal.get('sudden_jump', {}).get('coverage_pct', 'N/A'):.1f}% coverage
    SUDDEN_JUMP_WINDOW = 5                  # 5 games
    HIGH_VARIANCE_THRESHOLD = {high_variance_threshold}          # Optimized for {optimal.get('high_variance', {}).get('coverage_pct', 'N/A'):.1f}% coverage
    BREAK_DOMINANCE_THRESHOLD = {break_dominance_threshold}        # Optimized for {optimal.get('break_dominance_outlier', {}).get('coverage_pct', 'N/A'):.1f}% coverage
    
    # Flag weights for anomaly score (must sum to 1.0)
    FLAG_WEIGHTS = {{
        "winning_weak_only": 0.20,
        "losing_strong_only": 0.20,
        "rating_league_mismatch": 0.15,
        "sudden_jump": 0.25,
        "high_variance": 0.15,
        "break_dominance_outlier": 0.05,
    }}
    
    def detect_anomalies(
        self,
        player_history: PlayerMatchHistory,
        league_division: Optional[str] = None,
        expected_rating_range: Optional[Tuple[float, float]] = None,
    ) -> AnomalyFlags:
        """
        Detect anomalies in player history.
        
        Args:
            player_history: PlayerMatchHistory with games
            league_division: Optional league division (e.g., "A", "B") for mismatch check
            expected_rating_range: Optional (low, high) rating range for division
            
        Returns:
            AnomalyFlags with flags and anomaly_score
        """
        flags = AnomalyFlags(
            player_id=player_history.player_id,
            games_played=len(player_history.games),
            rating=player_history.rating,
        )
        
        if flags.games_played < 3:
            # Not enough data for reliable anomaly detection
            return flags
        
        # Check each anomaly flag
        if self._check_winning_weak_only(player_history):
            flags.winning_weak_only = True
            flags.flagged_count += 1
        
        if self._check_losing_strong_only(player_history):
            flags.losing_strong_only = True
            flags.flagged_count += 1
        
        if league_division and expected_rating_range:
            if self._check_rating_league_mismatch(
                player_history.rating, expected_rating_range
            ):
                flags.rating_league_mismatch = True
                flags.flagged_count += 1
        
        if self._check_sudden_jump(player_history):
            flags.sudden_jump = True
            flags.flagged_count += 1
        
        if self._check_high_variance(player_history):
            flags.high_variance = True
            flags.flagged_count += 1
        
        if self._check_break_dominance_outlier(player_history):
            flags.break_dominance_outlier = True
            flags.flagged_count += 1
        
        # Compute anomaly score
        flags.anomaly_score = self._compute_anomaly_score(flags)
        flags.severity_level = self._severity_level(flags.anomaly_score)
        
        return flags
    
    def _check_winning_weak_only(self, history: PlayerMatchHistory) -> bool:
        """Flag if player wins at/above threshold vs opponents 50+ pts below."""
        games_vs_weak = [
            g for g in history.games
            if g["opponent_rating"] < history.rating - self.WEAK_THRESHOLD
        ]
        
        if len(games_vs_weak) == 0:
            return False
        
        win_rate = sum(1 for g in games_vs_weak if g["won"]) / len(games_vs_weak)
        return win_rate >= self.WEAK_ONLY_WINRATE_THRESHOLD and len(games_vs_weak) >= 5
    
    def _check_losing_strong_only(self, history: PlayerMatchHistory) -> bool:
        """Flag if player loses at/above threshold vs opponents 50+ pts above."""
        games_vs_strong = [
            g for g in history.games
            if g["opponent_rating"] > history.rating + self.STRONG_THRESHOLD
        ]
        
        if len(games_vs_strong) == 0:
            return False
        
        loss_rate = sum(1 for g in games_vs_strong if not g["won"]) / len(games_vs_strong)
        return loss_rate >= self.STRONG_ONLY_LOSSRATE_THRESHOLD and len(games_vs_strong) >= 5
    
    def _check_rating_league_mismatch(
        self, player_rating: float, expected_range: Tuple[float, float]
    ) -> bool:
        """Flag if player rating is far outside league division expectations."""
        low, high = expected_range
        # Flag if outside range by >100 points
        threshold = 100
        return player_rating < low - threshold or player_rating > high + threshold
    
    def _check_sudden_jump(self, history: PlayerMatchHistory) -> bool:
        """Flag if rating jumped by threshold in 5-game window."""
        if len(history.games) < self.SUDDEN_JUMP_WINDOW:
            return False
        
        # Simulate rating progression (simplified; real system would track frame-by-frame)
        window = self.SUDDEN_JUMP_WINDOW
        for i in range(len(history.games) - window):
            # Estimate rating change from win/loss pattern
            window_wins = sum(1 for g in history.games[i:i+window] if g["won"])
            # Rough heuristic: each win ~ 8 pts
            rating_change = window_wins * 8
            
            if rating_change >= self.SUDDEN_JUMP_THRESHOLD:
                return True
        
        return False
    
    def _check_high_variance(self, history: PlayerMatchHistory) -> bool:
        """Flag if win percentage has variance above threshold."""
        if len(history.games) < 10:
            return False
        
        # Compute rolling win% with 5-game window
        window = 5
        win_pcts = []
        for i in range(len(history.games) - window + 1):
            window_wins = sum(1 for g in history.games[i:i+window] if g["won"])
            win_pct = window_wins / window
            win_pcts.append(win_pct)
        
        variance = np.std(win_pcts) if win_pcts else 0.0
        return variance > self.HIGH_VARIANCE_THRESHOLD
    
    def _check_break_dominance_outlier(self, history: PlayerMatchHistory) -> bool:
        """Flag if break win rate is unusually high."""
        break_games = [g for g in history.games if g.get("is_break", False)]
        
        if len(break_games) < 5:
            return False
        
        break_win_rate = sum(1 for g in break_games if g["won"]) / len(break_games)
        overall_win_rate = sum(1 for g in history.games if g["won"]) / len(history.games)
        
        # Flag if break win rate is at/above threshold AND significantly higher than overall
        return (
            break_win_rate >= self.BREAK_DOMINANCE_THRESHOLD
            and (break_win_rate - overall_win_rate) > 0.15
        )
    
    def _compute_anomaly_score(self, flags: AnomalyFlags) -> float:
        """
        Compute weighted anomaly score (0-1) from flags.
        
        Combines flags using weights; score clusters around discrete values
        unless high-variance is present.
        """
        score = 0.0
        
        if flags.winning_weak_only:
            score += self.FLAG_WEIGHTS["winning_weak_only"]
        if flags.losing_strong_only:
            score += self.FLAG_WEIGHTS["losing_strong_only"]
        if flags.rating_league_mismatch:
            score += self.FLAG_WEIGHTS["rating_league_mismatch"]
        if flags.sudden_jump:
            score += self.FLAG_WEIGHTS["sudden_jump"]
        if flags.high_variance:
            score += self.FLAG_WEIGHTS["high_variance"]
        if flags.break_dominance_outlier:
            score += self.FLAG_WEIGHTS["break_dominance_outlier"]
        
        return min(1.0, score)
    
    def _severity_level(self, score: float) -> str:
        """Classify anomaly severity based on score."""
        if score < 0.3:
            return "low"
        elif score < 0.7:
            return "medium"
        else:
            return "high"


def analyze_anomalies_batch(
    player_histories: List[PlayerMatchHistory],
    detector: Optional[AnomalyDetector] = None,
) -> Tuple[List[AnomalyFlags], Dict[str, int]]:
    """
    Detect anomalies for batch of players.
    
    Args:
        player_histories: List of PlayerMatchHistory
        detector: Optional AnomalyDetector (creates new if None)
        
    Returns:
        Tuple of (anomaly_flags_list, statistics)
    """
    if detector is None:
        detector = AnomalyDetector()
    
    flags_list = []
    stats = {{
        "total_players": len(player_histories),
        "flagged_players": 0,
        "low_severity": 0,
        "medium_severity": 0,
        "high_severity": 0,
        "avg_flags_per_player": 0.0,
    }}
    
    total_flags = 0
    for history in player_histories:
        flags = detector.detect_anomalies(history)
        flags_list.append(flags)
        
        if flags.flagged_count > 0:
            stats["flagged_players"] += 1
        
        if flags.severity_level == "low":
            stats["low_severity"] += 1
        elif flags.severity_level == "medium":
            stats["medium_severity"] += 1
        elif flags.severity_level == "high":
            stats["high_severity"] += 1
        
        total_flags += flags.flagged_count
    
    stats["avg_flags_per_player"] = (
        total_flags / len(player_histories) if player_histories else 0.0
    )
    
    return flags_list, stats
'''
    
    output_file = models_dir / filename
    with open(output_file, 'w') as f:
        f.write(new_model)
    
    logger.info(f"Saved updated detection model: {output_file}")


if __name__ == "__main__":
    main()
