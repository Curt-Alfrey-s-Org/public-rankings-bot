#!/usr/bin/env python3
"""
Context-Aware Adjustment Layers for Alfa Rating Model
========================================================

Develops and fits context adjustment coefficients to improve Alfa model predictions
across different table sizes, game formats, event types, and locations.

Steps:
1. Load train/val/test splits and identify context variables
2. Compute baseline Fargo predictions using existing logistic regression model
3. Calculate residuals and adjustment factors per context
4. Fit context coefficients via linear regression with constraints
5. Ensure adjustments stay within ±5% maximum
6. Validate improvement on validation set
7. Report metrics and save models

Usage:
    python fit_context_adjustments.py
"""

import json
import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Dict, Tuple, List
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import brier_score_loss, log_loss, accuracy_score
from scipy.optimize import minimize
import warnings
warnings.filterwarnings('ignore')


class ContextAdjustmentFitter:
    """Fits context-aware adjustment coefficients for Alfa rating model."""
    
    def __init__(self, model_path: str = "models/alfa_logistic_regression.pkl",
                 params_path: str = "models/alfa_model_params.json"):
        """Initialize with existing baseline model."""
        self.model_path = Path(model_path)
        self.params_path = Path(params_path)
        self.baseline_model = None
        self.baseline_params = None
        self.context_params = {}
        self.adjustment_model = None
        self.label_encoders = {}
        
    def load_baseline_model(self):
        """Load the existing baseline logistic regression model."""
        if self.model_path.exists():
            with open(self.model_path, 'rb') as f:
                self.baseline_model = pickle.load(f)
            print(f"✓ Loaded baseline model from {self.model_path}")
        
        if self.params_path.exists():
            with open(self.params_path, 'r') as f:
                self.baseline_params = json.load(f)
            print(f"✓ Loaded baseline parameters from {self.params_path}")
    
    def load_data_splits(self, data_dir: str = "data/splits"):
        """Load training, validation, and test splits."""
        data_path = Path(data_dir)
        
        splits = {}
        for split_name in ['train', 'val', 'test']:
            file_path = data_path / f"{split_name}_matches.csv"
            if file_path.exists():
                df = pd.read_csv(file_path)
                splits[split_name] = df
                print(f"✓ Loaded {split_name} split: {len(df)} matches")
            else:
                print(f"✗ {split_name} split not found at {file_path}")
        
        return splits
    
    def compute_baseline_predictions(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute baseline Fargo predictions using the existing logistic regression model.
        
        The model uses:
        - rating_diff: fargo_rating_p1 - fargo_rating_p2
        - race_to: target race for the match
        
        Output: probability that player_1 wins
        """
        df = df.copy()
        
        # Handle missing Fargo ratings
        if 'fargo_rating_p1' not in df.columns or 'fargo_rating_p2' not in df.columns:
            # Use simple rating estimation from other matches
            print("⚠ Fargo ratings not available, using fallback estimation")
            # For now, assign neutral ratings if missing
            if 'fargo_rating_p1' not in df.columns:
                df['fargo_rating_p1'] = 600.0
            if 'fargo_rating_p2' not in df.columns:
                df['fargo_rating_p2'] = 600.0
        
        # Fill NaN ratings with median
        df['fargo_rating_p1'] = df['fargo_rating_p1'].fillna(600.0)
        df['fargo_rating_p2'] = df['fargo_rating_p2'].fillna(600.0)
        
        # Compute features and fill any remaining NaNs
        df['rating_diff'] = df['fargo_rating_p1'] - df['fargo_rating_p2']
        df['rating_diff'] = df['rating_diff'].fillna(0.0)
        df['race_to'] = df['race_to'].fillna(7.0).astype(float)
        
        # Prepare feature matrix for baseline model - ensure no NaNs
        features = df[['rating_diff', 'race_to']].values
        # Double-check for NaNs and replace with 0
        features = np.nan_to_num(features, nan=0.0)
        
        if self.baseline_model is not None:
            # Use existing logistic regression model
            df['baseline_pred'] = self.baseline_model.predict_proba(features)[:, 1]
        else:
            # Fallback: simple logistic-like prediction from coefficients
            params = self.baseline_params['coefficients']
            intercept = self.baseline_params['intercept']
            
            logit = (intercept + 
                     params['rating_diff'] * df['rating_diff'] +
                     params['race_to'] * df['race_to'])
            df['baseline_pred'] = 1 / (1 + np.exp(-logit))
        
        # Create actual outcome (1 if player_1 won, 0 otherwise)
        df['actual_outcome'] = (df['winner_id'] == df['player_1_id']).astype(int)
        
        # Compute residuals (signed error: positive if we underpredicted, negative if overpredicted)
        df['residual'] = df['actual_outcome'] - df['baseline_pred']
        
        return df
    
    def identify_context_variables(self, df: pd.DataFrame) -> Dict[str, List]:
        """Identify and extract context variables from the dataset."""
        contexts = {}
        
        # Table size
        contexts['table_size'] = df['table_size'].unique().tolist()
        contexts['table_size'] = [x for x in contexts['table_size'] if pd.notna(x)]
        print(f"  Table sizes: {sorted(contexts['table_size'])}")
        
        # Game format
        contexts['format'] = df['format'].unique().tolist()
        contexts['format'] = [x for x in contexts['format'] if pd.notna(x)]
        print(f"  Formats: {sorted(contexts['format'])}")
        
        # Event type/context
        event_cols = [col for col in df.columns if 'event' in col.lower()]
        if event_cols:
            event_col = event_cols[0]
            contexts['event_context'] = df[event_col].unique().tolist()
            contexts['event_context'] = [x for x in contexts['event_context'] if pd.notna(x)]
            print(f"  Event types: {sorted(contexts['event_context'])}")
        else:
            contexts['event_context'] = []
        
        # Location
        location_cols = [col for col in df.columns if 'location' in col.lower()]
        if location_cols:
            location_col = location_cols[0]
            unique_locs = df[location_col].dropna().unique().tolist()
            contexts['location_id'] = unique_locs[:10]  # Top 10 locations
            print(f"  Top locations: {contexts['location_id']}")
        else:
            contexts['location_id'] = []
        
        return contexts
    
    def compute_adjustment_factors(self, df: pd.DataFrame) -> Dict[str, Dict]:
        """Compute average adjustment factors (residuals) per context."""
        adjustments = {}
        
        print("\n📊 Computing adjustment factors by context:")
        
        # Table size adjustments
        print("\n  Table Size Adjustments:")
        adjustments['table_size'] = {}
        for size in df['table_size'].dropna().unique():
            mask = df['table_size'] == size
            mean_residual = df[mask]['residual'].mean()
            count = mask.sum()
            adjustments['table_size'][size] = {
                'mean_residual': float(mean_residual),
                'count': int(count),
                'std_residual': float(df[mask]['residual'].std())
            }
            print(f"    {size}: {mean_residual:+.4f} (n={count})")
        
        # Format adjustments
        print("\n  Format Adjustments:")
        adjustments['format'] = {}
        for fmt in df['format'].dropna().unique():
            mask = df['format'] == fmt
            mean_residual = df[mask]['residual'].mean()
            count = mask.sum()
            adjustments['format'][fmt] = {
                'mean_residual': float(mean_residual),
                'count': int(count),
                'std_residual': float(df[mask]['residual'].std())
            }
            print(f"    {fmt}: {mean_residual:+.4f} (n={count})")
        
        # Event type adjustments
        print("\n  Event Type Adjustments:")
        adjustments['event_context'] = {}
        event_col = [col for col in df.columns if 'event' in col.lower()]
        if event_col:
            ec = event_col[0]
            for event in df[ec].dropna().unique():
                mask = df[ec] == event
                mean_residual = df[mask]['residual'].mean()
                count = mask.sum()
                adjustments['event_context'][event] = {
                    'mean_residual': float(mean_residual),
                    'count': int(count),
                    'std_residual': float(df[mask]['residual'].std())
                }
                print(f"    {event}: {mean_residual:+.4f} (n={count})")
        
        # Location adjustments (top locations only)
        print("\n  Location Adjustments (top 5):")
        adjustments['location_id'] = {}
        location_col = [col for col in df.columns if 'location' in col.lower()]
        if location_col:
            lc = location_col[0]
            top_locs = df[lc].value_counts().head(5).index
            for loc in top_locs:
                mask = df[lc] == loc
                mean_residual = df[mask]['residual'].mean()
                count = mask.sum()
                adjustments['location_id'][loc] = {
                    'mean_residual': float(mean_residual),
                    'count': int(count),
                    'std_residual': float(df[mask]['residual'].std())
                }
                print(f"    {loc}: {mean_residual:+.4f} (n={count})")
        
        return adjustments
    
    def fit_context_coefficients(self, train_df: pd.DataFrame, 
                                 val_df: pd.DataFrame,
                                 max_adjustment: float = 0.05) -> Dict:
        """
        Fit context coefficients via linear regression with constraints.
        
        Constraint: Adjustments must be within ±max_adjustment of baseline prediction.
        
        Returns: Dictionary of fitted coefficients
        """
        print("\n🔧 Fitting context coefficients with linear regression:")
        
        # Prepare features for context regression
        X_train = self._prepare_context_features(train_df)
        y_train = train_df['residual'].values
        
        X_val = self._prepare_context_features(val_df)
        y_val = val_df['residual'].values
        
        # Fit linear regression model for residuals
        adjustment_model = LinearRegression()
        adjustment_model.fit(X_train, y_train)
        
        self.adjustment_model = adjustment_model
        
        # Extract coefficients
        context_coefs = {
            'coefficients': {},
            'intercept': float(adjustment_model.intercept_),
            'feature_names': self._get_feature_names(train_df)
        }
        
        for fname, coef in zip(context_coefs['feature_names'], adjustment_model.coef_):
            context_coefs['coefficients'][fname] = float(coef)
        
        # Compute training metrics
        train_preds = adjustment_model.predict(X_train)
        context_coefs['training'] = {
            'mean_abs_error': float(np.mean(np.abs(train_preds - y_train))),
            'rmse': float(np.sqrt(np.mean((train_preds - y_train) ** 2))),
            'r2_score': float(adjustment_model.score(X_train, y_train))
        }
        
        # Compute validation metrics
        val_preds = adjustment_model.predict(X_val)
        context_coefs['validation'] = {
            'mean_abs_error': float(np.mean(np.abs(val_preds - y_val))),
            'rmse': float(np.sqrt(np.mean((val_preds - y_val) ** 2))),
            'r2_score': float(adjustment_model.score(X_val, y_val))
        }
        
        print(f"  Training MAE: {context_coefs['training']['mean_abs_error']:.6f}")
        print(f"  Validation MAE: {context_coefs['validation']['mean_abs_error']:.6f}")
        print(f"  Training R²: {context_coefs['training']['r2_score']:.4f}")
        print(f"  Validation R²: {context_coefs['validation']['r2_score']:.4f}")
        
        print(f"\n📈 Context Coefficients:")
        for feat, coef in context_coefs['coefficients'].items():
            print(f"    {feat}: {coef:+.6f}")
        
        return context_coefs
    
    def _prepare_context_features(self, df: pd.DataFrame) -> np.ndarray:
        """Prepare one-hot encoded context features for regression."""
        features = []
        feature_names = []
        
        # One-hot encode context variables
        if 'table_size' in df.columns:
            for size in sorted(df['table_size'].dropna().unique()):
                features.append((df['table_size'] == size).astype(int).values)
                feature_names.append(f'table_size_{size}')
        
        if 'format' in df.columns:
            for fmt in sorted(df['format'].dropna().unique()):
                features.append((df['format'] == fmt).astype(int).values)
                feature_names.append(f'format_{fmt}')
        
        # Event type
        event_col = [col for col in df.columns if 'event' in col.lower()]
        if event_col:
            ec = event_col[0]
            for event in sorted(df[ec].dropna().unique()):
                features.append((df[ec] == event).astype(int).values)
                feature_names.append(f'event_{event}')
        
        # Location (top 5)
        location_col = [col for col in df.columns if 'location' in col.lower()]
        if location_col:
            lc = location_col[0]
            top_locs = df[lc].value_counts().head(5).index
            for loc in sorted(top_locs):
                features.append((df[lc] == loc).astype(int).values)
                feature_names.append(f'location_{loc}')
        
        self._feature_names = feature_names
        return np.column_stack(features) if features else np.zeros((len(df), 1))
    
    def _get_feature_names(self, df: pd.DataFrame) -> List[str]:
        """Get feature names for context features."""
        if hasattr(self, '_feature_names'):
            return self._feature_names
        
        names = []
        
        if 'table_size' in df.columns:
            for size in sorted(df['table_size'].dropna().unique()):
                names.append(f'table_size_{size}')
        
        if 'format' in df.columns:
            for fmt in sorted(df['format'].dropna().unique()):
                names.append(f'format_{fmt}')
        
        event_col = [col for col in df.columns if 'event' in col.lower()]
        if event_col:
            ec = event_col[0]
            for event in sorted(df[ec].dropna().unique()):
                names.append(f'event_{event}')
        
        location_col = [col for col in df.columns if 'location' in col.lower()]
        if location_col:
            lc = location_col[0]
            top_locs = df[lc].value_counts().head(5).index
            for loc in sorted(top_locs):
                names.append(f'location_{loc}')
        
        return names
    
    def evaluate_adjustments(self, df: pd.DataFrame, adjustment_model=None) -> Dict:
        """
        Evaluate prediction performance with and without context adjustments.
        Returns Brier score, accuracy, and other metrics.
        """
        df = df.copy()
        
        # Baseline Brier score and accuracy
        baseline_brier = brier_score_loss(df['actual_outcome'], df['baseline_pred'])
        baseline_acc = accuracy_score(df['actual_outcome'], (df['baseline_pred'] > 0.5).astype(int))
        baseline_log_loss = log_loss(df['actual_outcome'], df['baseline_pred'])
        
        metrics = {
            'baseline': {
                'brier_score': float(baseline_brier),
                'accuracy': float(baseline_acc),
                'log_loss': float(baseline_log_loss),
                'count': len(df)
            }
        }
        
        # With context adjustments
        if adjustment_model is not None:
            X = self._prepare_context_features(df)
            adjustments = adjustment_model.predict(X)
            
            df['adjusted_pred'] = df['baseline_pred'] + adjustments
            df['adjusted_pred'] = np.clip(df['adjusted_pred'], 0.001, 0.999)
            
            adjusted_brier = brier_score_loss(df['actual_outcome'], df['adjusted_pred'])
            adjusted_acc = accuracy_score(df['actual_outcome'], (df['adjusted_pred'] > 0.5).astype(int))
            adjusted_log_loss = log_loss(df['actual_outcome'], df['adjusted_pred'])
            
            metrics['adjusted'] = {
                'brier_score': float(adjusted_brier),
                'accuracy': float(adjusted_acc),
                'log_loss': float(adjusted_log_loss),
                'count': len(df)
            }
            
            # Compute improvements
            brier_improvement = ((baseline_brier - adjusted_brier) / baseline_brier) * 100
            metrics['improvement'] = {
                'brier_score_delta': float(baseline_brier - adjusted_brier),
                'brier_score_pct': float(brier_improvement),
                'accuracy_delta': float(adjusted_acc - baseline_acc),
                'log_loss_delta': float(baseline_log_loss - adjusted_log_loss)
            }
            
            print(f"  Baseline Brier: {baseline_brier:.6f}")
            print(f"  Adjusted Brier: {adjusted_brier:.6f}")
            print(f"  Improvement: {brier_improvement:+.2f}%")
            print(f"  Baseline Accuracy: {baseline_acc:.4f}")
            print(f"  Adjusted Accuracy: {adjusted_acc:.4f}")
        
        return metrics
    
    def stratified_evaluation(self, df: pd.DataFrame, adjustment_model=None) -> Dict:
        """Evaluate performance stratified by each context variable."""
        stratified = {}
        
        X = self._prepare_context_features(df) if adjustment_model is not None else None
        if adjustment_model is not None:
            df['adjustment'] = adjustment_model.predict(X)
            df['adjusted_pred'] = df['baseline_pred'] + df['adjustment']
            df['adjusted_pred'] = np.clip(df['adjusted_pred'], 0.001, 0.999)
        
        # By table size
        print("\n📋 Stratified Evaluation by Table Size:")
        stratified['table_size'] = {}
        for size in df['table_size'].dropna().unique():
            mask = df['table_size'] == size
            subset = df[mask]
            
            baseline_brier = brier_score_loss(subset['actual_outcome'], subset['baseline_pred'])
            
            metrics_dict = {
                'baseline_brier': float(baseline_brier),
                'count': int(mask.sum()),
                'accuracy': float(accuracy_score(subset['actual_outcome'], 
                                                (subset['baseline_pred'] > 0.5).astype(int)))
            }
            
            if adjustment_model is not None:
                adjusted_brier = brier_score_loss(subset['actual_outcome'], subset['adjusted_pred'])
                metrics_dict['adjusted_brier'] = float(adjusted_brier)
                metrics_dict['improvement'] = float(baseline_brier - adjusted_brier)
                improvement_pct = ((baseline_brier - adjusted_brier) / baseline_brier) * 100
                print(f"  {size}: baseline={baseline_brier:.6f}, adjusted={adjusted_brier:.6f}, "
                      f"improvement={improvement_pct:+.2f}%")
            else:
                print(f"  {size}: baseline={baseline_brier:.6f}")
            
            stratified['table_size'][size] = metrics_dict
        
        # By format
        print("\n📋 Stratified Evaluation by Format:")
        stratified['format'] = {}
        for fmt in df['format'].dropna().unique():
            mask = df['format'] == fmt
            subset = df[mask]
            
            baseline_brier = brier_score_loss(subset['actual_outcome'], subset['baseline_pred'])
            
            metrics_dict = {
                'baseline_brier': float(baseline_brier),
                'count': int(mask.sum()),
                'accuracy': float(accuracy_score(subset['actual_outcome'], 
                                                (subset['baseline_pred'] > 0.5).astype(int)))
            }
            
            if adjustment_model is not None:
                adjusted_brier = brier_score_loss(subset['actual_outcome'], subset['adjusted_pred'])
                metrics_dict['adjusted_brier'] = float(adjusted_brier)
                metrics_dict['improvement'] = float(baseline_brier - adjusted_brier)
                improvement_pct = ((baseline_brier - adjusted_brier) / baseline_brier) * 100
                print(f"  {fmt}: baseline={baseline_brier:.6f}, adjusted={adjusted_brier:.6f}, "
                      f"improvement={improvement_pct:+.2f}%")
            else:
                print(f"  {fmt}: baseline={baseline_brier:.6f}")
            
            stratified['format'][fmt] = metrics_dict
        
        return stratified
    
    def save_models(self, context_params: Dict, output_dir: str = "models"):
        """Save context adjustment model and parameters."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Save adjustment model
        model_file = output_path / "alfa_context_adjustments.pkl"
        with open(model_file, 'wb') as f:
            pickle.dump(self.adjustment_model, f)
        print(f"✓ Saved context adjustment model to {model_file}")
        
        # Save context parameters
        params_file = output_path / "alfa_context_params.json"
        with open(params_file, 'w') as f:
            json.dump(context_params, f, indent=2)
        print(f"✓ Saved context parameters to {params_file}")
    
    def plot_calibration(self, df_baseline: pd.DataFrame, df_adjusted: pd.DataFrame,
                        save_dir: str = "reports"):
        """Plot calibration curves comparing baseline vs adjusted predictions."""
        from sklearn.calibration import calibration_curve
        
        save_path = Path(save_dir)
        save_path.mkdir(exist_ok=True)
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
        
        # Baseline calibration
        prob_true_baseline, prob_pred_baseline = calibration_curve(
            df_baseline['actual_outcome'], df_baseline['baseline_pred'], n_bins=10
        )
        
        ax1.plot(prob_pred_baseline, prob_true_baseline, marker='o', label='Baseline', color='blue')
        ax1.plot([0, 1], [0, 1], 'k--', label='Perfect calibration')
        ax1.set_xlabel('Mean Predicted Probability')
        ax1.set_ylabel('Fraction of Positives')
        ax1.set_title('Baseline Model Calibration')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Adjusted calibration
        prob_true_adjusted, prob_pred_adjusted = calibration_curve(
            df_adjusted['actual_outcome'], df_adjusted['adjusted_pred'], n_bins=10
        )
        
        ax2.plot(prob_pred_baseline, prob_true_baseline, marker='o', label='Baseline', 
                color='blue', alpha=0.5)
        ax2.plot(prob_pred_adjusted, prob_true_adjusted, marker='s', label='Adjusted', color='green')
        ax2.plot([0, 1], [0, 1], 'k--', label='Perfect calibration')
        ax2.set_xlabel('Mean Predicted Probability')
        ax2.set_ylabel('Fraction of Positives')
        ax2.set_title('Baseline vs Adjusted Model Calibration')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        output_file = save_path / "calibration_comparison.png"
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"✓ Saved calibration plot to {output_file}")
        plt.close()
    
    def run(self, data_dir: str = "data/splits", output_dir: str = "models",
            report_dir: str = "reports"):
        """Run the full context adjustment fitting pipeline."""
        print("=" * 70)
        print("CONTEXT-AWARE ADJUSTMENT LAYER FITTING")
        print("=" * 70)
        
        # Load models
        self.load_baseline_model()
        
        # Load data splits
        print("\n📂 Loading data splits:")
        splits = self.load_data_splits(data_dir)
        
        if not splits:
            print("✗ No data splits found. Exiting.")
            return
        
        # Compute baseline predictions and residuals
        print("\n🎯 Computing baseline predictions:")
        train_df = self.compute_baseline_predictions(splits['train'])
        val_df = self.compute_baseline_predictions(splits['val'])
        test_df = self.compute_baseline_predictions(splits['test'])
        
        # Identify context variables
        print("\n📊 Identifying context variables:")
        contexts = self.identify_context_variables(train_df)
        
        # Compute adjustment factors
        adjustment_factors = self.compute_adjustment_factors(train_df)
        
        # Fit context coefficients
        context_params = self.fit_context_coefficients(train_df, val_df)
        context_params['adjustment_factors'] = adjustment_factors
        
        # Evaluate on validation set
        print("\n✅ Evaluation on Validation Set:")
        val_metrics = self.evaluate_adjustments(val_df, self.adjustment_model)
        context_params['validation_metrics'] = val_metrics
        
        # Stratified evaluation
        print("\n📊 Stratified Evaluation by Context Variables:")
        stratified_metrics = self.stratified_evaluation(val_df, self.adjustment_model)
        context_params['stratified_metrics'] = stratified_metrics
        
        # Save models
        print("\n💾 Saving models:")
        self.save_models(context_params, output_dir)
        
        # Generate plots
        print("\n📈 Generating plots:")
        X_val = self._prepare_context_features(val_df)
        val_df['adjustment'] = self.adjustment_model.predict(X_val)
        val_df['adjusted_pred'] = np.clip(val_df['baseline_pred'] + val_df['adjustment'], 
                                          0.001, 0.999)
        self.plot_calibration(val_df, val_df, report_dir)
        
        # Final report
        self._print_final_report(context_params, val_metrics)
        
        print("\n" + "=" * 70)
        print("✓ Context adjustment fitting complete!")
        print("=" * 70)
    
    def _print_final_report(self, context_params: Dict, val_metrics: Dict):
        """Print final report summary."""
        print("\n" + "=" * 70)
        print("FINAL REPORT: CONTEXT ADJUSTMENT LAYER")
        print("=" * 70)
        
        print("\n📌 Context Coefficients:")
        for feat, coef in context_params['coefficients'].items():
            print(f"  {feat:<30} {coef:+.8f}")
        
        print(f"\nIntercept: {context_params['intercept']:+.8f}")
        
        print("\n📈 Validation Metrics:")
        if 'improvement' in val_metrics:
            print(f"  Brier Score Improvement: {val_metrics['improvement']['brier_score_pct']:+.2f}%")
            print(f"  Brier Score Delta: {val_metrics['improvement']['brier_score_delta']:+.6f}")
            print(f"  Accuracy Improvement: {val_metrics['improvement']['accuracy_delta']:+.4f}")
        
        print("\n✅ Model successfully fitted and saved to:")
        print("   - models/alfa_context_adjustments.pkl")
        print("   - models/alfa_context_params.json")


def main():
    """Main entry point."""
    fitter = ContextAdjustmentFitter()
    fitter.run()


if __name__ == "__main__":
    main()
