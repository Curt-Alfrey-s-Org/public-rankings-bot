#!/usr/bin/env python3
"""
Comprehensive A/B Testing Framework: Alfa vs Fargo Baseline.

Compares three models:
  - Model A: Fargo baseline (rating-difference formula)
  - Model B: Logistic regression (simple optimized model)
  - Model C: Alfa full system (logistic + cold-start + anomaly + context)

Outputs:
  - models/ab_test_results.json (complete metrics)
  - metrics/ab_test_comparison.csv (side-by-side metrics)
  - metrics/AB_TEST_REPORT.md (detailed findings)
  - metrics/visualizations/ab_test_*.png (6 charts)
"""

import json
import pickle
import logging
import warnings
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import seaborn as sns
from scipy import stats
from sklearn.metrics import (
    brier_score_loss, accuracy_score, log_loss, roc_auc_score, roc_curve,
    auc, confusion_matrix, precision_recall_curve, f1_score
)

warnings.filterwarnings('ignore')

# Configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / 'data'
MODELS_DIR = PROJECT_ROOT / 'models'
METRICS_DIR = PROJECT_ROOT / 'metrics'
VIZ_DIR = METRICS_DIR / 'visualizations'

VIZ_DIR.mkdir(exist_ok=True)

# Constants
FARGO_FORMULA_K = 400.0  # K-factor for Fargo


@dataclass
class ModelMetrics:
    """Metrics for a single model on test set."""
    model_name: str
    brier_score: float
    brier_score_std: Optional[float]
    accuracy: float
    log_loss: float
    auc_roc: float
    precision: float
    recall: float
    f1: float
    calibration_rmse: Optional[float] = None
    
    def to_dict(self):
        """Convert to dict, excluding None values."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class StratifiedMetrics:
    """Metrics for a model stratified by category."""
    category_name: str
    segment: str
    n_matches: int
    brier_score: float
    accuracy: float
    log_loss: float
    auc_roc: float
    
    def to_dict(self):
        return asdict(self)


class FargoBaseline:
    """Fargo baseline: P(p1_wins) = 1 / (1 + 10^(-(r1 - r2)/400))"""
    
    def predict_proba(self, rating_diff: np.ndarray) -> np.ndarray:
        """
        Predict win probability for player 1 given rating difference.
        
        Args:
            rating_diff: Array of (player_1_rating - player_2_rating) differences
            
        Returns:
            Array of shape (n, 2) with [P(p2_wins), P(p1_wins)]
        """
        p1_win_prob = 1.0 / (1.0 + 10.0 ** (-rating_diff / FARGO_FORMULA_K))
        p2_win_prob = 1.0 - p1_win_prob
        return np.column_stack([p2_win_prob, p1_win_prob])


class ColdStartAdjustment:
    """Cold-start Bayesian adjustment using pre-fitted model."""
    
    def __init__(self, model_path: Path):
        """Load saved cold-start model."""
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)
    
    def adjust_rating(self, rating: float, game_count: int, 
                     opponent_rating: float) -> float:
        """
        Adjust player rating using Bayesian blending based on game count.
        
        Blend schedule:
        - < 10 games: 80% starter, 20% measured
        - 10-50: 50/50
        - 50-200: 10% starter, 90% measured
        - 200+: 100% measured (no adjustment)
        """
        # Determine blending weights
        if game_count < 10:
            starter_wt, measured_wt = 0.80, 0.20
        elif game_count < 50:
            starter_wt, measured_wt = 0.50, 0.50
        elif game_count < 200:
            starter_wt, measured_wt = 0.10, 0.90
        else:
            return rating  # No adjustment for experienced players
        
        # For simplicity, starter = opponent_rating
        # (In production, would use prior distribution)
        starter = (opponent_rating + 400) / 2  # Rough midpoint
        adjusted = starter_wt * starter + measured_wt * rating
        return adjusted


class AnomalyDetector:
    """Detects sandbagging and other anomalies."""
    
    # Thresholds
    SUDDEN_JUMP = 40
    WEAK_WINRATE = 0.65
    STRONG_LOSSRATE = 0.65
    
    def detect_anomaly(self, player_recent_results: List[bool],
                      player_rating: float,
                      opponent_rating: float) -> bool:
        """
        Simple anomaly detection based on recent win rate.
        Returns True if anomaly detected (sandbagging likely).
        """
        if len(player_recent_results) < 5:
            return False
        
        recent_wins = sum(player_recent_results[-5:])
        win_rate = recent_wins / 5.0
        
        # If lower-rated player has high win rate vs higher-rated
        if player_rating < opponent_rating:
            return win_rate > self.WEAK_WINRATE
        
        # If higher-rated player has high loss rate vs lower-rated
        if player_rating > opponent_rating:
            return win_rate < (1 - self.STRONG_LOSSRATE)
        
        return False


class ABTestFramework:
    """Comprehensive A/B testing framework."""
    
    def __init__(self):
        """Initialize framework and load data."""
        self.test_df = None
        self.fargo_baseline = FargoBaseline()
        self.lr_model = None
        self.context_model = None
        self.predictions = {}
        self.metrics = {}
        
    def load_data(self):
        """Load test set."""
        logger.info("Loading test set...")
        self.test_df = pd.read_csv(DATA_DIR / 'splits' / 'test_matches.csv')
        
        # Create outcome variable (1 if player_1 wins)
        self.test_df['outcome'] = (
            self.test_df['winner_id'] == self.test_df['player_1_id']
        ).astype(int)
        
        # Precompute useful features
        self.test_df['rating_diff'] = self.test_df['fargo_rating_p1'] - self.test_df['fargo_rating_p2']
        self.test_df['rating_avg'] = (self.test_df['fargo_rating_p1'] + self.test_df['fargo_rating_p2']) / 2
        self.test_df['rating_ratio'] = (self.test_df['fargo_rating_p1'] + 1) / (self.test_df['fargo_rating_p2'] + 1)
        
        logger.info(f"Loaded {len(self.test_df)} test matches")
        logger.info(f"Outcome distribution: {self.test_df['outcome'].value_counts().to_dict()}")
    
    def load_models(self):
        """Load trained models."""
        logger.info("Loading trained models...")
        
        # Load logistic regression
        with open(MODELS_DIR / 'alfa_logistic_regression_optimized.pkl', 'rb') as f:
            self.lr_model = pickle.load(f)
        logger.info("✓ Loaded logistic regression model")
        
        # Load context adjustments
        with open(MODELS_DIR / 'alfa_context_adjustments.pkl', 'rb') as f:
            self.context_model = pickle.load(f)
        logger.info("✓ Loaded context adjustments model")
    
    def prepare_context_features(self, df: pd.DataFrame) -> np.ndarray:
        """Prepare one-hot encoded context features for context model."""
        features_list = []
        
        # Table size one-hot (7ft, 8ft, 9ft)
        table_size = df['table_size'].fillna('unknown')
        for size in ['7ft', '8ft', '9ft']:
            features_list.append((table_size == size).astype(int).values)
        
        # Format one-hot (10ball, 8ball, 9ball)
        fmt = df['format'].fillna('unknown')
        for f in ['10ball', '8ball', '9ball']:
            features_list.append((fmt == f).astype(int).values)
        
        # Event one-hot (tournament)
        event = df['event_type'].fillna('unknown') if 'event_type' in df.columns else 'tournament'
        features_list.append((event == 'tournament').astype(int).values)
        
        # Location one-hot (boston_classic, chicago_nationals, las_vegas_open, phoenix_open, seattle_invitational)
        location = df['location_id'].fillna('unknown') if 'location_id' in df.columns else 'unknown'
        for loc in ['boston_classic', 'chicago_nationals', 'las_vegas_open', 'phoenix_open', 'seattle_invitational']:
            features_list.append((location == loc).astype(int).values)
        
        return np.column_stack(features_list)
    
    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare features for logistic regression."""
        features = df.copy()
        
        # Basic features
        features['rating_diff'] = features['fargo_rating_p1'] - features['fargo_rating_p2']
        features['rating_avg'] = (features['fargo_rating_p1'] + features['fargo_rating_p2']) / 2
        features['rating_sum'] = features['fargo_rating_p1'] + features['fargo_rating_p2']
        features['rating_ratio'] = (features['fargo_rating_p1'] + 1) / (features['fargo_rating_p2'] + 1)
        
        # Race features
        features['race_to_numeric'] = features['race_to'].astype(float)
        
        # Table size encoding
        table_map = {'7ft': 0.0, '8ft': 0.5, '9ft': 1.0}
        features['table_size_code'] = features['table_size'].map(table_map).fillna(0.5)
        
        # Format encoding
        format_map = {'8ball': 0.0, '9ball': 1.0}
        features['format_code'] = features['format'].map(format_map).fillna(0.5)
        
        return features
    
    def predict_fargo_baseline(self) -> np.ndarray:
        """Generate Fargo baseline predictions."""
        logger.info("\n=== Model A: Fargo Baseline ===")
        
        test_features = self.prepare_features(self.test_df)
        rating_diff = test_features['rating_diff'].values
        probs = self.fargo_baseline.predict_proba(rating_diff)
        
        # Extract P(player_1 wins)
        p_wins = probs[:, 1]
        
        logger.info(f"Predictions: mean={p_wins.mean():.4f}, std={p_wins.std():.4f}")
        logger.info(f"Predictions: min={p_wins.min():.4f}, max={p_wins.max():.4f}")
        
        return p_wins
    
    def predict_logistic_regression(self) -> np.ndarray:
        """Generate logistic regression predictions."""
        logger.info("\n=== Model B: Logistic Regression ===")
        
        test_features = self.prepare_features(self.test_df)
        
        # Select features used in training (rating_diff and race_to_numeric only)
        feature_cols = ['rating_diff', 'race_to_numeric']
        X_test = test_features[feature_cols].values
        
        # Predict
        p_wins = self.lr_model.predict_proba(X_test)[:, 1]
        
        logger.info(f"Predictions: mean={p_wins.mean():.4f}, std={p_wins.std():.4f}")
        logger.info(f"Predictions: min={p_wins.min():.4f}, max={p_wins.max():.4f}")
        
        return p_wins
    
    def predict_alfa_full_system(self) -> np.ndarray:
        """Generate full Alfa system predictions (LR + cold-start + anomaly + context)."""
        logger.info("\n=== Model C: Alfa Full System ===")
        
        test_features = self.prepare_features(self.test_df)
        feature_cols = ['rating_diff', 'race_to_numeric']
        X_test = test_features[feature_cols].values
        
        # Start with logistic regression
        p_wins = self.lr_model.predict_proba(X_test)[:, 1].copy()
        
        # Apply cold-start adjustment (for players with estimated <100 games)
        # Use rating magnitude as proxy for experience
        game_count_est = test_features['rating_avg'].values / 10.0
        low_confidence = game_count_est < 100
        # Increase uncertainty for less experienced players (pull toward 0.5)
        p_wins[low_confidence] = 0.5 + 0.85 * (p_wins[low_confidence] - 0.5)
        
        # Apply anomaly detection penalty for suspected sandbagging
        # Heuristic: if lower-rated player has extreme advantage (ratio > 2.0)
        rating_diff = test_features['rating_diff'].values
        rating_ratio = test_features['rating_ratio'].values
        
        extreme_underdog = (rating_diff > 200) & (rating_ratio > 2.0)
        p_wins[extreme_underdog] = np.clip(p_wins[extreme_underdog] - 0.08, 0.0, 1.0)
        
        extreme_favorite = (rating_diff < -200) & (rating_ratio < 0.5)
        p_wins[extreme_favorite] = np.clip(p_wins[extreme_favorite] + 0.05, 0.0, 1.0)
        
        # Apply context-based adjustments using one-hot encoded categorical features
        context_features = self.prepare_context_features(self.test_df)
        
        # Get predicted adjustments from context model (expects 12 features)
        try:
            context_adjustment = self.context_model.predict(context_features).flatten()
            # Apply adjustment (bounded to [-0.15, +0.15] for safety)
            context_adjustment = np.clip(context_adjustment, -0.15, 0.15)
            p_wins = np.clip(p_wins + 0.7 * context_adjustment, 0.0, 1.0)
            logger.info(f"Context adjustment applied (mean={context_adjustment.mean():.6f}, std={context_adjustment.std():.6f})")
        except Exception as e:
            logger.warning(f"Could not apply context adjustment: {e}")
        
        logger.info(f"Predictions: mean={p_wins.mean():.4f}, std={p_wins.std():.4f}")
        logger.info(f"Predictions: min={p_wins.min():.4f}, max={p_wins.max():.4f}")
        
        return p_wins
    
    def compute_metrics(self, y_true: np.ndarray, y_pred: np.ndarray,
                       model_name: str) -> ModelMetrics:
        """Compute all metrics for a model."""
        logger.info(f"\nComputing metrics for {model_name}...")
        
        # Brier score
        brier = brier_score_loss(y_true, y_pred)
        
        # Accuracy
        y_pred_binary = (y_pred >= 0.5).astype(int)
        acc = accuracy_score(y_true, y_pred_binary)
        
        # Log loss
        y_pred_clipped = np.clip(y_pred, 1e-10, 1 - 1e-10)
        ll = log_loss(y_true, y_pred)
        
        # AUC-ROC
        auc_score = roc_auc_score(y_true, y_pred)
        
        # Precision & recall
        precision, recall, _ = precision_recall_curve(y_true, y_pred)
        f1 = f1_score(y_true, y_pred_binary)
        
        # Calibration
        calib_rmse = self._compute_calibration_rmse(y_true, y_pred)
        
        metrics = ModelMetrics(
            model_name=model_name,
            brier_score=brier,
            brier_score_std=None,  # Computed in bootstrap later
            accuracy=acc,
            log_loss=ll,
            auc_roc=auc_score,
            precision=precision[-1] if len(precision) > 0 else 0.0,
            recall=recall[-1] if len(recall) > 0 else 0.0,
            f1=f1,
            calibration_rmse=calib_rmse
        )
        
        logger.info(f"  Brier Score:      {brier:.6f}")
        logger.info(f"  Accuracy:         {acc:.6f}")
        logger.info(f"  Log Loss:         {ll:.6f}")
        logger.info(f"  AUC-ROC:          {auc_score:.6f}")
        logger.info(f"  Calibration RMSE: {calib_rmse:.6f}")
        
        return metrics
    
    def _compute_calibration_rmse(self, y_true: np.ndarray, 
                                  y_pred: np.ndarray, n_bins: int = 10) -> float:
        """Compute calibration RMSE (0 = perfect calibration)."""
        bins = np.linspace(0, 1, n_bins + 1)
        bin_centers = (bins[:-1] + bins[1:]) / 2
        
        rmse = 0.0
        count = 0
        for i in range(n_bins):
            mask = (y_pred >= bins[i]) & (y_pred < bins[i + 1])
            if mask.sum() > 0:
                observed = y_true[mask].mean()
                expected = bin_centers[i]
                rmse += (observed - expected) ** 2
                count += 1
        
        if count == 0:
            return 0.0
        return np.sqrt(rmse / count)
    
    def stratified_analysis(self):
        """Perform stratified analysis by rating gap, race length, player type."""
        logger.info("\n=== Stratified Analysis ===")
        
        results = {
            'rating_gap': [],
            'race_length': [],
            'player_experience': []
        }
        
        # Rating gap stratification
        rating_gaps = [(0, 100), (100, 200), (200, 300), (300, 1000)]
        for low, high in rating_gaps:
            mask = (self.test_df['rating_diff'].abs() >= low) & \
                   (self.test_df['rating_diff'].abs() < high)
            if mask.sum() > 0:
                for model_name in ['fargo', 'logistic', 'alfa']:
                    y_true = self.test_df[mask]['outcome'].values
                    y_pred = self.predictions[model_name][mask]
                    
                    metrics = StratifiedMetrics(
                        category_name='rating_gap',
                        segment=f'{low}-{high} pts',
                        n_matches=int(mask.sum()),
                        brier_score=float(brier_score_loss(y_true, y_pred)),
                        accuracy=float(accuracy_score(y_true, (y_pred >= 0.5).astype(int))),
                        log_loss=float(log_loss(y_true, y_pred)),
                        auc_roc=float(roc_auc_score(y_true, y_pred))
                    )
                    results['rating_gap'].append((model_name, metrics))
        
        # Race length stratification
        race_lengths = [7, 8, 9, 11]
        for race in race_lengths:
            mask = self.test_df['race_to'] == race
            if mask.sum() > 0:
                for model_name in ['fargo', 'logistic', 'alfa']:
                    y_true = self.test_df[mask]['outcome'].values
                    y_pred = self.predictions[model_name][mask]
                    
                    metrics = StratifiedMetrics(
                        category_name='race_length',
                        segment=f'Best-of-{race}',
                        n_matches=int(mask.sum()),
                        brier_score=float(brier_score_loss(y_true, y_pred)),
                        accuracy=float(accuracy_score(y_true, (y_pred >= 0.5).astype(int))),
                        log_loss=float(log_loss(y_true, y_pred)),
                        auc_roc=float(roc_auc_score(y_true, y_pred))
                    )
                    results['race_length'].append((model_name, metrics))
        
        # Player experience stratification
        # Estimate as rating magnitude
        player_types = {
            'new (<50 games)': (0, 200),
            'intermediate (50-200)': (200, 500),
            'experienced (>200)': (500, 1000)
        }
        for player_type, (low, high) in player_types.items():
            mask = (self.test_df['fargo_rating_p1'] >= low) & \
                   (self.test_df['fargo_rating_p1'] < high)
            if mask.sum() > 0:
                for model_name in ['fargo', 'logistic', 'alfa']:
                    y_true = self.test_df[mask]['outcome'].values
                    y_pred = self.predictions[model_name][mask]
                    
                    metrics = StratifiedMetrics(
                        category_name='player_experience',
                        segment=player_type,
                        n_matches=int(mask.sum()),
                        brier_score=float(brier_score_loss(y_true, y_pred)),
                        accuracy=float(accuracy_score(y_true, (y_pred >= 0.5).astype(int))),
                        log_loss=float(log_loss(y_true, y_pred)),
                        auc_roc=float(roc_auc_score(y_true, y_pred))
                    )
                    results['player_experience'].append((model_name, metrics))
        
        return results
    
    def statistical_testing(self):
        """Perform McNemar and signed-rank tests."""
        logger.info("\n=== Statistical Testing ===")
        
        y_true = self.test_df['outcome'].values
        
        # McNemar test for accuracy
        logger.info("\n--- McNemar Test (Accuracy Differences) ---")
        
        y_pred_fargo_binary = (self.predictions['fargo'] >= 0.5).astype(int)
        y_pred_lr_binary = (self.predictions['logistic'] >= 0.5).astype(int)
        y_pred_alfa_binary = (self.predictions['alfa'] >= 0.5).astype(int)
        
        # Fargo vs Logistic
        mcnemar_lr = self._mcnemar_test(y_true, y_pred_fargo_binary, y_pred_lr_binary)
        logger.info(f"Fargo vs Logistic: statistic={mcnemar_lr['statistic']:.4f}, "
                   f"p-value={mcnemar_lr['p_value']:.6f}")
        
        # Fargo vs Alfa
        mcnemar_alfa = self._mcnemar_test(y_true, y_pred_fargo_binary, y_pred_alfa_binary)
        logger.info(f"Fargo vs Alfa: statistic={mcnemar_alfa['statistic']:.4f}, "
                   f"p-value={mcnemar_alfa['p_value']:.6f}")
        
        # Logistic vs Alfa
        mcnemar_lr_alfa = self._mcnemar_test(y_true, y_pred_lr_binary, y_pred_alfa_binary)
        logger.info(f"Logistic vs Alfa: statistic={mcnemar_lr_alfa['statistic']:.4f}, "
                   f"p-value={mcnemar_lr_alfa['p_value']:.6f}")
        
        # Signed-rank test for Brier scores
        logger.info("\n--- Wilcoxon Signed-Rank Test (Brier Score Differences) ---")
        
        brier_fargo = np.square(y_true - self.predictions['fargo'])
        brier_lr = np.square(y_true - self.predictions['logistic'])
        brier_alfa = np.square(y_true - self.predictions['alfa'])
        
        wilcoxon_lr = stats.wilcoxon(brier_fargo, brier_lr)
        logger.info(f"Fargo vs Logistic: statistic={wilcoxon_lr.statistic:.4f}, "
                   f"p-value={wilcoxon_lr.pvalue:.6f}")
        
        wilcoxon_alfa = stats.wilcoxon(brier_fargo, brier_alfa)
        logger.info(f"Fargo vs Alfa: statistic={wilcoxon_alfa.statistic:.4f}, "
                   f"p-value={wilcoxon_alfa.pvalue:.6f}")
        
        wilcoxon_lr_alfa = stats.wilcoxon(brier_lr, brier_alfa)
        logger.info(f"Logistic vs Alfa: statistic={wilcoxon_lr_alfa.statistic:.4f}, "
                   f"p-value={wilcoxon_lr_alfa.pvalue:.6f}")
        
        return {
            'mcnemar': {
                'fargo_vs_logistic': mcnemar_lr,
                'fargo_vs_alfa': mcnemar_alfa,
                'logistic_vs_alfa': mcnemar_lr_alfa
            },
            'wilcoxon': {
                'fargo_vs_logistic': {'statistic': wilcoxon_lr.statistic, 'p_value': wilcoxon_lr.pvalue},
                'fargo_vs_alfa': {'statistic': wilcoxon_alfa.statistic, 'p_value': wilcoxon_alfa.pvalue},
                'logistic_vs_alfa': {'statistic': wilcoxon_lr_alfa.statistic, 'p_value': wilcoxon_lr_alfa.pvalue}
            }
        }
    
    def _mcnemar_test(self, y_true: np.ndarray, y_pred1: np.ndarray,
                     y_pred2: np.ndarray) -> Dict:
        """Compute McNemar test."""
        correct1 = y_true == y_pred1
        correct2 = y_true == y_pred2
        
        # Contingency table
        b = np.sum((~correct1) & correct2)  # Wrong vs right
        c = np.sum(correct1 & (~correct2))  # Right vs wrong
        
        # McNemar statistic
        if (b + c) == 0:
            return {'statistic': 0.0, 'p_value': 1.0}
        
        stat = (b - c) ** 2 / (b + c)
        p_value = 1 - stats.chi2.cdf(stat, df=1)
        
        return {'statistic': stat, 'p_value': p_value}
    
    def run(self):
        """Run complete A/B test."""
        logger.info("=" * 80)
        logger.info("COMPREHENSIVE A/B TEST: ALFA vs FARGO BASELINE")
        logger.info("=" * 80)
        
        # Load and prepare data
        self.load_data()
        self.load_models()
        
        # Generate predictions
        y_true = self.test_df['outcome'].values
        
        self.predictions['fargo'] = self.predict_fargo_baseline()
        self.predictions['logistic'] = self.predict_logistic_regression()
        self.predictions['alfa'] = self.predict_alfa_full_system()
        
        # Compute metrics
        self.metrics['fargo'] = self.compute_metrics(y_true, self.predictions['fargo'], 'Fargo Baseline')
        self.metrics['logistic'] = self.compute_metrics(y_true, self.predictions['logistic'], 'Logistic Regression')
        self.metrics['alfa'] = self.compute_metrics(y_true, self.predictions['alfa'], 'Alfa Full System')
        
        # Stratified analysis
        stratified = self.stratified_analysis()
        
        # Statistical testing
        statistical_tests = self.statistical_testing()
        
        # Generate visualizations
        logger.info("\n=== Generating Visualizations ===")
        self.create_visualizations()
        
        # Save results
        logger.info("\n=== Saving Results ===")
        self.save_results(stratified, statistical_tests)
        
        logger.info("\n" + "=" * 80)
        logger.info("A/B TEST COMPLETE")
        logger.info("=" * 80)
    
    def create_visualizations(self):
        """Create 6 comprehensive visualization charts."""
        sns.set_style("whitegrid")
        plt.rcParams['figure.facecolor'] = 'white'
        plt.rcParams['font.size'] = 10
        
        # 1. Brier score comparison
        self._plot_brier_score_comparison()
        
        # 2. ROC curves
        self._plot_roc_curves()
        
        # 3. Calibration curves
        self._plot_calibration_curves()
        
        # 4. Performance by rating gap
        self._plot_performance_by_rating_gap()
        
        # 5. Performance by race length
        self._plot_performance_by_race_length()
        
        # 6. Performance by player experience
        self._plot_performance_by_experience()
    
    def _plot_brier_score_comparison(self):
        """Brier score comparison with error bars."""
        fig, ax = plt.subplots(figsize=(10, 6))
        
        models = ['Fargo\nBaseline', 'Logistic\nRegression', 'Alfa Full\nSystem']
        brier_scores = [
            self.metrics['fargo'].brier_score,
            self.metrics['logistic'].brier_score,
            self.metrics['alfa'].brier_score
        ]
        colors = ['#f43f5a', '#3b82f6', '#10b981']
        
        bars = ax.bar(models, brier_scores, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)
        
        # Add value labels
        for bar, score in zip(bars, brier_scores):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2., height,
                   f'{score:.4f}', ha='center', va='bottom', fontweight='bold', fontsize=11)
        
        ax.axhline(y=0.25, color='gray', linestyle='--', alpha=0.5, label='Random baseline (0.25)')
        ax.set_ylabel('Brier Score  (lower is better)', fontsize=11, fontweight='bold')
        ax.set_title('A/B Test: Brier Score Comparison', fontsize=13, fontweight='bold', pad=20)
        ax.set_ylim(0, max(brier_scores) * 1.15)
        ax.legend(loc='upper right')
        ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(VIZ_DIR / 'ab_test_01_brier_score.png', dpi=300, bbox_inches='tight')
        logger.info("✓ Saved: ab_test_01_brier_score.png")
        plt.close()
    
    def _plot_roc_curves(self):
        """ROC curves for all three models."""
        fig, ax = plt.subplots(figsize=(10, 8))
        
        y_true = self.test_df['outcome'].values
        colors = {'fargo': '#f43f5a', 'logistic': '#3b82f6', 'alfa': '#10b981'}
        
        for model_name, model_key in [('Fargo Baseline', 'fargo'),
                                       ('Logistic Regression', 'logistic'),
                                       ('Alfa Full System', 'alfa')]:
            y_pred = self.predictions[model_key]
            fpr, tpr, _ = roc_curve(y_true, y_pred)
            auc_score = roc_auc_score(y_true, y_pred)
            
            ax.plot(fpr, tpr, color=colors[model_key], linewidth=2.5,
                   label=f'{model_name} (AUC={auc_score:.4f})')
        
        # Random baseline
        ax.plot([0, 1], [0, 1], 'k--', linewidth=1.5, alpha=0.5, label='Random (AUC=0.5000)')
        
        ax.set_xlabel('False Positive Rate', fontsize=11, fontweight='bold')
        ax.set_ylabel('True Positive Rate', fontsize=11, fontweight='bold')
        ax.set_title('A/B Test: ROC Curves', fontsize=13, fontweight='bold', pad=20)
        ax.legend(loc='lower right', fontsize=10)
        ax.grid(alpha=0.3)
        ax.set_aspect('equal')
        
        plt.tight_layout()
        plt.savefig(VIZ_DIR / 'ab_test_02_roc_curves.png', dpi=300, bbox_inches='tight')
        logger.info("✓ Saved: ab_test_02_roc_curves.png")
        plt.close()
    
    def _plot_calibration_curves(self):
        """Calibration curves showing predicted vs actual probabilities."""
        fig, axes = plt.subplots(1, 3, figsize=(16, 5))
        
        y_true = self.test_df['outcome'].values
        
        for ax, (model_name, model_key) in zip(
            axes,
            [('Fargo Baseline', 'fargo'),
             ('Logistic Regression', 'logistic'),
             ('Alfa Full System', 'alfa')]
        ):
            y_pred = self.predictions[model_key]
            
            # Calibration curve
            n_bins = 10
            bin_edges = np.linspace(0, 1, n_bins + 1)
            bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
            
            pred_means = []
            actual_means = []
            bin_sizes = []
            
            for i in range(n_bins):
                mask = (y_pred >= bin_edges[i]) & (y_pred < bin_edges[i + 1])
                if mask.sum() > 0:
                    pred_means.append(y_pred[mask].mean())
                    actual_means.append(y_true[mask].mean())
                    bin_sizes.append(mask.sum())
                else:
                    pred_means.append(np.nan)
                    actual_means.append(np.nan)
                    bin_sizes.append(0)
            
            # Plot
            ax.scatter(pred_means, actual_means, s=[max(s/10, 20) for s in bin_sizes],
                      alpha=0.6, edgecolors='black', linewidth=1)
            ax.plot([0, 1], [0, 1], 'k--', linewidth=1, alpha=0.5)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.set_xlabel('Predicted Probability', fontsize=10, fontweight='bold')
            ax.set_ylabel('Actual Frequency', fontsize=10, fontweight='bold')
            ax.set_title(model_name, fontsize=11, fontweight='bold')
            ax.grid(alpha=0.3)
            ax.set_aspect('equal')
        
        fig.suptitle('A/B Test: Calibration Curves', fontsize=13, fontweight='bold', y=1.02)
        plt.tight_layout()
        plt.savefig(VIZ_DIR / 'ab_test_03_calibration.png', dpi=300, bbox_inches='tight')
        logger.info("✓ Saved: ab_test_03_calibration.png")
        plt.close()
    
    def _plot_performance_by_rating_gap(self):
        """Performance stratified by rating gap."""
        fig, ax = plt.subplots(figsize=(12, 6))
        
        rating_gaps = ['0-100 pts', '100-200 pts', '200-300 pts', '300+ pts']
        x = np.arange(len(rating_gaps))
        width = 0.25
        
        brier_by_model = {
            'fargo': [],
            'logistic': [],
            'alfa': []
        }
        
        for low, high in [(0, 100), (100, 200), (200, 300), (300, 1000)]:
            mask = (self.test_df['rating_diff'].abs() >= low) & \
                   (self.test_df['rating_diff'].abs() < high)
            if mask.sum() == 0:
                for model_key in ['fargo', 'logistic', 'alfa']:
                    brier_by_model[model_key].append(np.nan)
                continue
            
            y_true = self.test_df[mask]['outcome'].values
            
            for model_key in ['fargo', 'logistic', 'alfa']:
                y_pred = self.predictions[model_key][mask]
                brier = brier_score_loss(y_true, y_pred)
                brier_by_model[model_key].append(brier)
        
        colors = {'fargo': '#f43f5a', 'logistic': '#3b82f6', 'alfa': '#10b981'}
        for i, (model_key, label) in enumerate([('fargo', 'Fargo'),
                                                ('logistic', 'Logistic'),
                                                ('alfa', 'Alfa')]):
            valid_indices = [j for j, v in enumerate(brier_by_model[model_key]) if not np.isnan(v)]
            valid_x = x[valid_indices]
            valid_scores = [brier_by_model[model_key][j] for j in valid_indices]
            
            ax.bar(valid_x + i*width, valid_scores, width,
                  label=label, color=colors[model_key], alpha=0.8, edgecolor='black')
        
        ax.set_ylabel('Brier Score', fontsize=11, fontweight='bold')
        ax.set_xlabel('Rating Gap', fontsize=11, fontweight='bold')
        ax.set_title('Performance by Rating Gap', fontsize=13, fontweight='bold', pad=20)
        ax.set_xticks(x + width)
        ax.set_xticklabels(rating_gaps)
        ax.legend()
        ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(VIZ_DIR / 'ab_test_04_by_rating_gap.png', dpi=300, bbox_inches='tight')
        logger.info("✓ Saved: ab_test_04_by_rating_gap.png")
        plt.close()
    
    def _plot_performance_by_race_length(self):
        """Performance stratified by race length."""
        fig, ax = plt.subplots(figsize=(12, 6))
        
        race_lengths = ['Best-of-7', 'Best-of-8', 'Best-of-9', 'Best-of-11+']
        x = np.arange(len(race_lengths))
        width = 0.25
        
        brier_by_model = {
            'fargo': [],
            'logistic': [],
            'alfa': []
        }
        
        for i, race in enumerate([7, 8, 9, 11]):
            if i < 3:
                mask = self.test_df['race_to'] == race
            else:
                mask = self.test_df['race_to'] >= race
            
            if mask.sum() == 0:
                logger.warning(f"No matches for race_to >= {race}")
                for model_key in ['fargo', 'logistic', 'alfa']:
                    brier_by_model[model_key].append(np.nan)
                continue
            
            y_true = self.test_df[mask]['outcome'].values
            
            for model_key in ['fargo', 'logistic', 'alfa']:
                y_pred = self.predictions[model_key][mask]
                brier = brier_score_loss(y_true, y_pred)
                brier_by_model[model_key].append(brier)
        
        colors = {'fargo': '#f43f5a', 'logistic': '#3b82f6', 'alfa': '#10b981'}
        for i, (model_key, label) in enumerate([('fargo', 'Fargo'),
                                                ('logistic', 'Logistic'),
                                                ('alfa', 'Alfa')]):
            valid_indices = [j for j, v in enumerate(brier_by_model[model_key]) if not np.isnan(v)]
            valid_x = x[valid_indices]
            valid_scores = [brier_by_model[model_key][j] for j in valid_indices]
            
            ax.bar(valid_x + i*width, valid_scores, width,
                  label=label, color=colors[model_key], alpha=0.8, edgecolor='black')
        
        ax.set_ylabel('Brier Score', fontsize=11, fontweight='bold')
        ax.set_xlabel('Race Length', fontsize=11, fontweight='bold')
        ax.set_title('Performance by Race Length', fontsize=13, fontweight='bold', pad=20)
        ax.set_xticks(x + width)
        ax.set_xticklabels(race_lengths)
        ax.legend()
        ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(VIZ_DIR / 'ab_test_05_by_race_length.png', dpi=300, bbox_inches='tight')
        logger.info("✓ Saved: ab_test_05_by_race_length.png")
        plt.close()
    
    def _plot_performance_by_experience(self):
        """Performance stratified by player experience level."""
        fig, ax = plt.subplots(figsize=(12, 6))
        
        experience_levels = ['New\n(<50 games)', 'Intermediate\n(50-200)', 'Experienced\n(>200)']
        x = np.arange(len(experience_levels))
        width = 0.25
        
        brier_by_model = {
            'fargo': [],
            'logistic': [],
            'alfa': []
        }
        
        for low, high in [(0, 200), (200, 500), (500, 1000)]:
            mask = (self.test_df['fargo_rating_p1'] >= low) & \
                   (self.test_df['fargo_rating_p1'] < high)
            if mask.sum() == 0:
                for model_key in ['fargo', 'logistic', 'alfa']:
                    brier_by_model[model_key].append(np.nan)
                continue
            
            y_true = self.test_df[mask]['outcome'].values
            
            for model_key in ['fargo', 'logistic', 'alfa']:
                y_pred = self.predictions[model_key][mask]
                brier = brier_score_loss(y_true, y_pred)
                brier_by_model[model_key].append(brier)
        
        colors = {'fargo': '#f43f5a', 'logistic': '#3b82f6', 'alfa': '#10b981'}
        for i, (model_key, label) in enumerate([('fargo', 'Fargo'),
                                                ('logistic', 'Logistic'),
                                                ('alfa', 'Alfa')]):
            valid_indices = [j for j, v in enumerate(brier_by_model[model_key]) if not np.isnan(v)]
            valid_x = x[valid_indices]
            valid_scores = [brier_by_model[model_key][j] for j in valid_indices]
            
            ax.bar(valid_x + i*width, valid_scores, width,
                  label=label, color=colors[model_key], alpha=0.8, edgecolor='black')
        
        ax.set_ylabel('Brier Score', fontsize=11, fontweight='bold')
        ax.set_xlabel('Player Experience Level', fontsize=11, fontweight='bold')
        ax.set_title('Performance by Player Experience', fontsize=13, fontweight='bold', pad=20)
        ax.set_xticks(x + width)
        ax.set_xticklabels(experience_levels)
        ax.legend()
        ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(VIZ_DIR / 'ab_test_06_by_experience.png', dpi=300, bbox_inches='tight')
        logger.info("✓ Saved: ab_test_06_by_experience.png")
        plt.close()
    
    def save_results(self, stratified, statistical_tests):
        """Save results to JSON, CSV, and markdown."""
        
        # Prepare result data
        result_data = {
            'test_date': pd.Timestamp.now().isoformat(),
            'test_set_size': len(self.test_df),
            'test_set_outcome_distribution': self.test_df['outcome'].value_counts().to_dict(),
            'models': {
                'fargo': self.metrics['fargo'].to_dict(),
                'logistic': self.metrics['logistic'].to_dict(),
                'alfa': self.metrics['alfa'].to_dict()
            },
            'statistical_tests': statistical_tests,
            'stratified_analysis': {
                'rating_gap': [
                    {'model': m, 'metrics': asdict(met)}
                    for m, met in stratified['rating_gap']
                ],
                'race_length': [
                    {'model': m, 'metrics': asdict(met)}
                    for m, met in stratified['race_length']
                ],
                'player_experience': [
                    {'model': m, 'metrics': asdict(met)}
                    for m, met in stratified['player_experience']
                ]
            }
        }
        
        # Save JSON
        with open(MODELS_DIR / 'ab_test_results.json', 'w') as f:
            json.dump(result_data, f, indent=2)
        logger.info("✓ Saved: models/ab_test_results.json")
        
        # Save CSV comparison
        comparison_data = []
        for model_key, model_name in [('fargo', 'Fargo Baseline'),
                                      ('logistic', 'Logistic Regression'),
                                      ('alfa', 'Alfa Full System')]:
            row = {
                'Model': model_name,
                'Brier Score': f"{self.metrics[model_key].brier_score:.6f}",
                'Accuracy': f"{self.metrics[model_key].accuracy:.6f}",
                'Log Loss': f"{self.metrics[model_key].log_loss:.6f}",
                'AUC-ROC': f"{self.metrics[model_key].auc_roc:.6f}",
                'Precision': f"{self.metrics[model_key].precision:.6f}",
                'Recall': f"{self.metrics[model_key].recall:.6f}",
                'F1 Score': f"{self.metrics[model_key].f1:.6f}",
                'Calibration RMSE': f"{self.metrics[model_key].calibration_rmse:.6f}"
            }
            comparison_data.append(row)
        
        pd.DataFrame(comparison_data).to_csv(
            METRICS_DIR / 'ab_test_comparison.csv', index=False
        )
        logger.info("✓ Saved: metrics/ab_test_comparison.csv")
        
        # Generate markdown report
        self._generate_report(result_data)
    
    def _generate_report(self, result_data):
        """Generate comprehensive markdown report."""
        report = []
        report.append("# A/B Test Report: Alfa Rating Model vs Fargo Baseline\n")
        report.append(f"**Test Date:** {result_data['test_date']}\n")
        report.append(f"**Test Set Size:** {result_data['test_set_size']} matches\n")
        report.append(f"**Test Set Distribution:** Player 1 wins {result_data['test_set_outcome_distribution'][1]}, "
                     f"Player 2 wins {result_data['test_set_outcome_distribution'][0]}\n\n")
        
        # Summary table
        report.append("## Summary Metrics\n\n")
        report.append("| Model | Brier Score | Accuracy | Log Loss | AUC-ROC | Calibration RMSE |\n")
        report.append("|-------|-------------|----------|----------|---------|------------------|\n")
        
        for model_key, model_name in [('fargo', 'Fargo Baseline'),
                                      ('logistic', 'Logistic Regression'),
                                      ('alfa', 'Alfa Full System')]:
            metrics = self.metrics[model_key]
            report.append(f"| {model_name} | {metrics.brier_score:.6f} | {metrics.accuracy:.6f} | "
                         f"{metrics.log_loss:.6f} | {metrics.auc_roc:.6f} | {metrics.calibration_rmse:.6f} |\n")
        
        report.append("\n### Key Findings\n\n")
        
        # Determine winner
        brier_scores = {
            'Fargo': self.metrics['fargo'].brier_score,
            'Logistic': self.metrics['logistic'].brier_score,
            'Alfa': self.metrics['alfa'].brier_score
        }
        winner = min(brier_scores, key=brier_scores.get)
        
        report.append(f"- **Best Brier Score:** {winner} ({brier_scores[winner]:.6f})\n")
        report.append(f"- **Fargo vs Logistic Improvement:** {(brier_scores['Fargo'] - brier_scores['Logistic']) / brier_scores['Fargo'] * 100:.2f}%\n")
        report.append(f"- **Fargo vs Alfa Improvement:** {(brier_scores['Fargo'] - brier_scores['Alfa']) / brier_scores['Fargo'] * 100:.2f}%\n\n")
        
        # Statistical significance
        report.append("## Statistical Significance\n\n")
        report.append("### McNemar Test (Accuracy Differences)\n\n")
        
        tests = result_data['statistical_tests']['mcnemar']
        report.append(f"- **Fargo vs Logistic:** p-value = {tests['fargo_vs_logistic']['p_value']:.6f} "
                     f"('significant' if p < 0.05 else 'not significant')\n")
        report.append(f"- **Fargo vs Alfa:** p-value = {tests['fargo_vs_alfa']['p_value']:.6f} "
                     f"('significant' if p < 0.05 else 'not significant')\n")
        report.append(f"- **Logistic vs Alfa:** p-value = {tests['logistic_vs_alfa']['p_value']:.6f} "
                     f"('significant' if p < 0.05 else 'not significant')\n\n")
        
        # Visualizations
        report.append("## Visualizations\n\n")
        report.append("The following charts are included in the metrics/visualizations directory:\n\n")
        report.append("1. **ab_test_01_brier_score.png** - Brier score comparison (lower is better)\n")
        report.append("2. **ab_test_02_roc_curves.png** - ROC curves for all three models\n")
        report.append("3. **ab_test_03_calibration.png** - Calibration curves (predicted vs actual)\n")
        report.append("4. **ab_test_04_by_rating_gap.png** - Performance stratified by rating difference\n")
        report.append("5. **ab_test_05_by_race_length.png** - Performance stratified by race length\n")
        report.append("6. **ab_test_06_by_experience.png** - Performance by player experience level\n\n")
        
        # Recommendations
        report.append("## Recommendations\n\n")
        
        if winner == 'Alfa':
            report.append(f"✓ **Deploy Alfa Rating System:** The Alfa full system achieves the lowest Brier score "
                         f"({brier_scores['Alfa']:.6f}), demonstrating superior calibration and predictive accuracy.\n\n")
        elif winner == 'Logistic':
            report.append(f"⚠ **Evaluate Logistic Regression:** The simple logistic regression outperforms Fargo but is "
                         f"significantly simpler than the Alfa system. Consider trade-offs between accuracy and model complexity.\n\n")
        else:
            report.append(f"⚠ **Investigate Fargo Baseline:** All models show room for improvement. Consider:\n")
            report.append(f"  - Collecting more training data (especially for new/intermediate players)\n")
            report.append(f"  - Incorporating additional features (tournament format, venue, player head-to-head history)\n")
            report.append(f"  - Exploring advanced architectures (ensemble methods, neural networks)\n\n")
        
        # Save report
        with open(METRICS_DIR / 'AB_TEST_REPORT.md', 'w') as f:
            f.write(''.join(report))
        logger.info("✓ Saved: metrics/AB_TEST_REPORT.md")


if __name__ == '__main__':
    framework = ABTestFramework()
    framework.run()
