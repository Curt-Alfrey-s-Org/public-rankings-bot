"""
Enhanced Anomaly Detection Threshold Optimization.

Improves ground truth detection using statistical analysis instead of arbitrary heuristics.
"""

from __future__ import annotations

import json
import csv
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Set
import numpy as np
import pandas as pd

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
    test_value: str
    num_flagged: int
    num_anomalous: int
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
            "num_anomalous": self.num_anomalous,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
            "coverage_pct": round(self.coverage_pct, 4),
        }


class ImprovedAnomalyGroundTruth:
    """
    Improved ground truth detection using statistical methods.
    
    Identifies anomalies based on:
    1. Statistical outliers in rating progression
    2. Unusual win rate patterns
    3. Opponent strength distribution anomalies
    """
    
    def __init__(self):
        self.anomalous_players: Set[str] = set()
        self.domain_scores: Dict[str, float] = {}  # Player -> anomaly likelihood (0-1)
        self.reasons: Dict[str, List[str]] = {}
    
    def identify_anomalies(self, histories: List[PlayerMatchHistory]) -> None:
        """Identify anomalies using statistical methods."""
        
        # Compute statistics for all players
        stats = {
            "sudden_jumps": [],
            "win_rate_variance": [],
            "weak_dominance_rates": [],
            "strong_dependency_rates": [],
            "break_win_rates": [],
        }
        
        for history in histories:
            if len(history.games) < 5:
                continue
                
            # Compute various metrics
            jumps = self._compute_rating_jumps(history)
            variance = self._compute_win_rate_variance(history)
            weak_dom = self._compute_weak_dominance(history)
            strong_dep = self._compute_strong_dependency(history)
            break_wr = self._compute_break_win_rate(history)
            
            stats["sudden_jumps"].extend(jumps)
            stats["win_rate_variance"].append(variance)
            stats["weak_dominance_rates"].append(weak_dom)
            stats["strong_dependency_rates"].append(strong_dep)
            stats["break_win_rates"].append(break_wr)
        
        # Compute z-scores and percentiles
        def get_outliers(values, threshold_std=2.0):
            if not values:
                return set()
            arr = np.array([v for v in values if not np.isnan(v)])
            if len(arr) < 3:
                return set()
            mean = np.mean(arr)
            std = np.std(arr)
            if std == 0:
                return set()
            return set(np.where(np.abs((arr - mean) / std) > threshold_std)[0])
        
        # Get players with anomalous measurements
        for history in histories:
            if len(history.games) < 5:
                continue
            
            anomaly_signals = []
            
            # Signal 1: Sudden rating jumps
            jumps = self._compute_rating_jumps(history)
            valid_jumps = [j for j in stats["sudden_jumps"] if not np.isnan(j)]
            if jumps and valid_jumps and np.max(jumps) > np.quantile(valid_jumps, 0.95):
                anomaly_signals.append("extreme_jump")
            
            # Signal 2: High win rate variance
            variance = self._compute_win_rate_variance(history)
            valid_var = [v for v in stats["win_rate_variance"] if not np.isnan(v)]
            if not np.isnan(variance) and valid_var and variance > np.quantile(valid_var, 0.90):
                anomaly_signals.append("high_variance")
            
            # Signal 3: Weak player dominance
            weak_dom = self._compute_weak_dominance(history)
            valid_weak = [v for v in stats["weak_dominance_rates"] if not np.isnan(v)]
            if not np.isnan(weak_dom) and valid_weak and weak_dom > np.quantile(valid_weak, 0.90):
                anomaly_signals.append("weak_dominance")
            
            # Signal 4: Strong player dependency
            strong_dep = self._compute_strong_dependency(history)
            valid_strong = [v for v in stats["strong_dependency_rates"] if not np.isnan(v)]
            if not np.isnan(strong_dep) and valid_strong and strong_dep > np.quantile(valid_strong, 0.90):
                anomaly_signals.append("strong_dependency")
            
            # Signal 5: Break dominance
            break_wr = self._compute_break_win_rate(history)
            valid_break = [v for v in stats["break_win_rates"] if not np.isnan(v) and v > 0]
            if not np.isnan(break_wr) and valid_break and break_wr > np.quantile(valid_break, 0.85):
                anomaly_signals.append("break_dominance")
            
            # Mark as anomalous if multiple signals or very high single signal
            if len(anomaly_signals) >= 2 or (anomaly_signals and len(history.games) >= 20):
                self.anomalous_players.add(history.player_id)
                self.reasons[history.player_id] = anomaly_signals
                # Score based on number of signals
                self.domain_scores[history.player_id] = min(1.0, len(anomaly_signals) / 5.0)
        
        logger.info(f"Identified {len(self.anomalous_players)} anomalous players")
    
    def _compute_rating_jumps(self, history: PlayerMatchHistory) -> List[float]:
        """Compute max rating jump in sliding windows."""
        if len(history.games) < 5:
            return []
        
        jumps = []
        window = 5
        for i in range(len(history.games) - window + 1):
            wins = sum(1 for g in history.games[i:i+window] if g["won"])
            jump = wins * 8  # Rough: 8 pts per win
            jumps.append(jump)
        
        return jumps if jumps else [0.0]
    
    def _compute_win_rate_variance(self, history: PlayerMatchHistory) -> float:
        """Compute variance in rolling win rates."""
        if len(history.games) < 10:
            return np.nan
        
        window = 5
        win_rates = []
        for i in range(len(history.games) - window + 1):
            wins = sum(1 for g in history.games[i:i+window] if g["won"])
            win_rates.append(wins / window)
        
        return np.std(win_rates) if win_rates else np.nan
    
    def _compute_weak_dominance(self, history: PlayerMatchHistory) -> float:
        """Fraction of wins against weaker players out of games vs weak."""
        weak_games = [g for g in history.games if g["opponent_rating"] < history.rating - 50]
        
        if len(weak_games) < 3:
            return np.nan
        
        wins = sum(1 for g in weak_games if g["won"])
        return wins / len(weak_games)
    
    def _compute_strong_dependency(self, history: PlayerMatchHistory) -> float:
        """Fraction of losses against stronger players out of games vs strong."""
        strong_games = [g for g in history.games if g["opponent_rating"] > history.rating + 50]
        
        if len(strong_games) < 3:
            return np.nan
        
        losses = sum(1 for g in strong_games if not g["won"])
        return losses / len(strong_games)
    
    def _compute_break_win_rate(self, history: PlayerMatchHistory) -> float:
        """Win rate on break shots."""
        break_games = [g for g in history.games if g.get("is_break", False)]
        
        if len(break_games) < 3:
            return np.nan
        
        wins = sum(1 for g in break_games if g["won"])
        return wins / len(break_games)


class DetailedThresholdAnalyzer:
    """Enhanced threshold analysis with detailed metrics."""
    
    def __init__(self, histories: List[PlayerMatchHistory]):
        self.histories = histories
        self.ground_truth = ImprovedAnomalyGroundTruth()
        self.ground_truth.identify_anomalies(histories)
        self.results: List[ThresholdResult] = []
    
    def test_all_thresholds(self):
        """Test all threshold combinations."""
        logger.info("Testing threshold combinations...")
        
        self._test_flag("sudden_jump", [20, 30, 40, 50, 60])
        self._test_flag("winning_weak_only", [0.65, 0.70, 0.75, 0.80, 0.85, 0.90])
        self._test_flag("losing_strong_only", [0.65, 0.70, 0.75, 0.80, 0.85, 0.90])
        self._test_flag("high_variance", [0.20, 0.25, 0.30, 0.35, 0.40])
        self._test_flag("break_dominance_outlier", [0.60, 0.65, 0.70, 0.75, 0.80])
    
    def _test_flag(self, flag_name: str, thresholds: List[float]):
        """Test a single flag with multiple thresholds."""
        logger.info(f"Testing {flag_name}...")
        
        for threshold in thresholds:
            detector = AnomalyDetector()
            
            # Set threshold on detector
            if flag_name == "sudden_jump":
                detector.SUDDEN_JUMP_THRESHOLD = threshold
                test_value = f"{int(threshold)} pts in 5 games"
            elif flag_name == "winning_weak_only":
                detector.WEAK_ONLY_WINRATE_THRESHOLD = threshold
                test_value = f"{threshold*100:.0f}% wins vs weak"
            elif flag_name == "losing_strong_only":
                detector.STRONG_ONLY_LOSSRATE_THRESHOLD = threshold
                test_value = f"{threshold*100:.0f}% losses vs strong"
            elif flag_name == "high_variance":
                detector.HIGH_VARIANCE_THRESHOLD = threshold
                test_value = f"std dev {threshold}"
            elif flag_name == "break_dominance_outlier":
                detector.BREAK_DOMINANCE_THRESHOLD = threshold
                test_value = f"{threshold*100:.0f}% break wins"
            else:
                continue
            
            # Evaluate
            flagged = set()
            for history in self.histories:
                flags = detector.detect_anomalies(history)
                if getattr(flags, flag_name, False):
                    flagged.add(history.player_id)
            
            # Compute metrics
            true_positives = len(flagged & self.ground_truth.anomalous_players)
            false_positives = len(flagged - self.ground_truth.anomalous_players)
            false_negatives = len(self.ground_truth.anomalous_players - flagged)
            
            precision = true_positives / len(flagged) if flagged else 0.0
            recall = true_positives / len(self.ground_truth.anomalous_players) if self.ground_truth.anomalous_players else 0.0
            
            if precision + recall > 0:
                f1 = 2 * precision * recall / (precision + recall)
            else:
                f1 = 0.0
            
            coverage = len(flagged) / len(self.histories) if self.histories else 0.0
            
            result = ThresholdResult(
                flag_name=flag_name,
                threshold_value=threshold,
                test_value=test_value,
                num_flagged=len(flagged),
                num_anomalous=true_positives,
                precision=precision,
                recall=recall,
                f1_score=f1,
                coverage_pct=coverage * 100,
            )
            self.results.append(result)
    
    def select_optimal_thresholds(self) -> Dict[str, Dict]:
        """Select optimal thresholds."""
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
                continue
            
            # Find best by F1 score
            best = max(flag_results, key=lambda r: r.f1_score)
            
            # Check constraints
            meets_all = (best.precision >= 0.80 and best.recall >= 0.70 and best.coverage_pct <= 15)
            meets_precision = best.precision >= 0.75
            meets_recall = best.recall >= 0.60
            
            if meets_all:
                reason = "meets all criteria"
            elif meets_precision and meets_recall:
                reason = "good balance (P>75%, R>60%)"
            else:
                reason = f"best F1 ({best.f1_score:.3f})"
            
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
                f"{flag_name}: {best.test_value} "
                f"(P={best.precision:.1%}, R={best.recall:.1%}, F1={best.f1_score:.3f}, Cov={best.coverage_pct:.1f}%)"
            )
        
        return optimal


def load_player_histories(csv_path: str) -> List[PlayerMatchHistory]:
    """Load player match histories from CSV."""
    logger.info(f"Loading match data from {csv_path}")
    
    df = pd.read_csv(csv_path)
    
    player_games: Dict[str, list] = {}
    player_ratings: Dict[str, float] = {}
    
    for _, row in df.iterrows():
        p1_id = row['player_1_id']
        p2_id = row['player_2_id']
        winner_id = row['winner_id']
        rating_p1 = row['fargo_rating_p1']
        rating_p2 = row['fargo_rating_p2']
        
        player_ratings[p1_id] = rating_p1
        player_ratings[p2_id] = rating_p2
        
        p1_won = winner_id == p1_id
        p2_won = winner_id == p2_id
        
        game_p1 = {
            "opponent_id": p2_id,
            "opponent_rating": rating_p2,
            "won": p1_won,
            "is_break": False
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
    
    histories = []
    for player_id, games in player_games.items():
        if len(games) >= 3:
            history = PlayerMatchHistory(
                player_id=player_id,
                rating=player_ratings[player_id],
                games=games
            )
            histories.append(history)
    
    logger.info(f"Created {len(histories)} player histories from {len(df)} matches")
    return histories


def main():
    """Run enhanced analysis."""
    
    project_root = Path(__file__).parent
    csv_path = project_root / "data" / "splits" / "train_matches.csv"
    output_dir = project_root / "metrics"
    models_dir = project_root / "models"
    
    output_dir.mkdir(exist_ok=True)
    models_dir.mkdir(exist_ok=True)
    
    if not csv_path.exists():
        logger.error(f"Training data not found: {csv_path}")
        return
    
    histories = load_player_histories(str(csv_path))
    
    # Run analysis
    analyzer = DetailedThresholdAnalyzer(histories)
    analyzer.test_all_thresholds()
    optimal = analyzer.select_optimal_thresholds()
    
    # Save results
    save_analysis(analyzer.results, analyzer.ground_truth, output_dir)
    save_thresholds(optimal, models_dir)
    save_report(analyzer, optimal, output_dir)
    create_v2_model(optimal, models_dir)
    
    logger.info("✓ Enhanced threshold optimization complete!")
    print_summary(optimal)


def save_analysis(results: List[ThresholdResult], ground_truth, output_dir: Path):
    """Save detailed analysis."""
    
    # JSON with all results
    data = [r.as_dict() for r in results]
    with open(output_dir / "anomaly_threshold_analysis.json", 'w') as f:
        json.dump(data, f, indent=2)
    
    # CSV with optimal summary
    with open(output_dir / "anomaly_optimization_summary.csv", 'w', newline='') as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["flag_name", "threshold_value", "test_value", "num_flagged", "num_anomalous", "precision", "recall", "f1_score", "coverage_pct"]
        )
        writer.writeheader()
        for r in results:
            writer.writerow(r.as_dict())
    
    logger.info(f"Saved analysis to {output_dir}")


def save_thresholds(optimal: Dict, models_dir: Path):
    """Save optimized thresholds."""
    data = {}
    for flag, metrics in optimal.items():
        data[flag] = {
            "threshold": metrics["threshold"],
            "description": metrics["test_value"],
            "metrics": {
                "precision": round(metrics["precision"], 4),
                "recall": round(metrics["recall"], 4),
                "f1_score": round(metrics["f1_score"], 4),
                "coverage_pct": round(metrics["coverage_pct"], 2),
            },
            "selection_reason": metrics["selection_reason"],
        }
    
    with open(models_dir / "alfa_anomaly_thresholds_optimized.json", 'w') as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Saved optimized thresholds to {models_dir}")


def save_report(analyzer: DetailedThresholdAnalyzer, optimal: Dict, output_dir: Path):
    """Save comprehensive report."""
    
    report = [
        "# Anomaly Detection Threshold Optimization Report\n\n",
        "## Executive Summary\n",
        f"- Player histories analyzed: {len(analyzer.histories)}\n",
        f"- Ground truth anomalies identified: {len(analyzer.ground_truth.anomalous_players)}\n",
        f"- Flags optimized: 5 (sudden_jump, winning_weak_only, losing_strong_only, high_variance, break_dominance_outlier)\n\n",
        "## Methodology\n",
        "Statistical analysis using z-scores and percentile thresholds to identify ground truth anomalies.\n"
        "Evaluated each threshold against ground truth using precision, recall, F1, and coverage metrics.\n\n",
        "## Optimal Thresholds Selected\n\n",
    ]
    
    for flag in sorted(optimal.keys()):
        m = optimal[flag]
        report.append(f"### {flag}\n")
        report.append(f"- **Threshold**: {m['test_value']}\n")
        report.append(f"- **Precision**: {m['precision']:.2%}\n")
        report.append(f"- **Recall**: {m['recall']:.2%}\n")
        report.append(f"- **F1 Score**: {m['f1_score']:.4f}\n")
        report.append(f"- **Coverage**: {m['coverage_pct']:.2f}%\n")
        report.append(f"- **Reason**: {m['selection_reason']}\n\n")
    
    report.append("## Metrics Comparison (Before vs After)\n\n")
    report.append("| Flag | Before | After | Change |\n")
    report.append("|------|--------|-------|--------|\n")
    
    # Original defaults
    defaults = {
        "sudden_jump": 40,
        "winning_weak_only": 0.80,
        "losing_strong_only": 0.80,
        "high_variance": 0.35,
        "break_dominance_outlier": 0.75,
    }
    
    for flag in sorted(optimal.keys()):
        before = defaults.get(flag, "?")
        after = optimal[flag]["threshold"]
        report.append(f"| {flag} | {before} | {after} | Updated |\n")
    
    report.append("\n## Recommendations\n\n")
    report.append("1. **Deploy v2 Model**: Use alfa_anomaly_detection_v2.py with optimized thresholds\n")
    report.append("2. **Monitor Performance**: Track precision/recall in production\n")
    report.append("3. **Gather Feedback**: Validate flagged players; improve ground truth over time\n")
    report.append("4. **Re-tune Annually**: Update thresholds as player population evolves\n")
    
    with open(output_dir / "ANOMALY_THRESHOLD_TUNING_REPORT.md", 'w') as f:
        f.writelines(report)
    
    logger.info(f"Saved report to {output_dir}")


def create_v2_model(optimal: Dict, models_dir: Path):
    """Create the updated v2 model."""
    
    thresholds = {flag: optimal[flag]["threshold"] for flag in optimal}
    
    model_code = f'''"""
ALFa Anomaly Detection v2 - Optimized Thresholds.

Thresholds optimized via statistical analysis on training data.
See: metrics/ANOMALY_THRESHOLD_TUNING_REPORT.md
"""

from models.alfa_anomaly_detection import AnomalyDetector as BaseDetector, AnomalyFlags, PlayerMatchHistory, analyze_anomalies_batch


class AnomalyDetectorV2(BaseDetector):
    """Optimized anomaly detector with tuned thresholds."""
    
    # OPTIMIZED thresholds
    SUDDEN_JUMP_THRESHOLD = {thresholds.get('sudden_jump', 40)}
    WEAK_ONLY_WINRATE_THRESHOLD = {thresholds.get('winning_weak_only', 0.80)}
    STRONG_ONLY_LOSSRATE_THRESHOLD = {thresholds.get('losing_strong_only', 0.80)}
    HIGH_VARIANCE_THRESHOLD = {thresholds.get('high_variance', 0.35)}
    BREAK_DOMINANCE_THRESHOLD = {thresholds.get('break_dominance_outlier', 0.75)}


# For backwards compatibility
AnomalyDetector = AnomalyDetectorV2
'''
    
    with open(models_dir / "alfa_anomaly_detection_v2.py", 'w') as f:
        f.write(model_code)
    
    logger.info(f"Created v2 model at {models_dir / 'alfa_anomaly_detection_v2.py'}")


def print_summary(optimal: Dict):
    """Print summary of optimization results."""
    
    print("\n" + "="*70)
    print("ANOMALY DETECTION THRESHOLD OPTIMIZATION RESULTS")
    print("="*70 + "\n")
    
    for flag in sorted(optimal.keys()):
        m = optimal[flag]
        print(f"{flag.upper()}")
        print(f"  Threshold: {m['test_value']}")
        print(f"  Precision: {m['precision']:.1%}  Recall: {m['recall']:.1%}  F1: {m['f1_score']:.3f}")
        print(f"  Coverage:  {m['coverage_pct']:.2f}% of population")
        print()
    
    print("="*70)
    print("Files generated:")
    print("  - metrics/anomaly_threshold_analysis.json")
    print("  - metrics/anomaly_optimization_summary.csv")
    print("  - metrics/ANOMALY_THRESHOLD_TUNING_REPORT.md")
    print("  - models/alfa_anomaly_thresholds_optimized.json")
    print("  - models/alfa_anomaly_detection_v2.py")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
