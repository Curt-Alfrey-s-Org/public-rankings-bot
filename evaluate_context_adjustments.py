#!/usr/bin/env python3
"""
Comprehensive evaluation and analysis of context-aware adjustment layers.
Generates detailed metrics, visualizations, and reports.
"""

import json
import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.metrics import brier_score_loss, accuracy_score, log_loss
from sklearn.calibration import calibration_curve
import warnings
warnings.filterwarnings('ignore')


class ContextAdjustmentEvaluator:
    """Evaluate and analyze context adjustment layer performance."""
    
    def __init__(self, 
                 adjustment_model_path='models/alfa_context_adjustments.pkl',
                 context_params_path='models/alfa_context_params.json',
                 baseline_model_path='models/alfa_logistic_regression.pkl',
                 baseline_params_path='models/alfa_model_params.json'):
        """Initialize evaluator with models."""
        self.adjustment_model = None
        self.context_params = None
        self.baseline_model = None
        self.baseline_params = None
        
        # Load models
        self._load_models(adjustment_model_path, context_params_path, 
                         baseline_model_path, baseline_params_path)
    
    def _load_models(self, adj_model_path, context_params_path, 
                     base_model_path, base_params_path):
        """Load all required models."""
        # Load baseline model
        if Path(base_model_path).exists():
            with open(base_model_path, 'rb') as f:
                self.baseline_model = pickle.load(f)
        
        # Load baseline params
        if Path(base_params_path).exists():
            with open(base_params_path, 'r') as f:
                self.baseline_params = json.load(f)
        
        # Load context adjustment model
        if Path(adj_model_path).exists():
            with open(adj_model_path, 'rb') as f:
                self.adjustment_model = pickle.load(f)
        
        # Load context parameters
        if Path(context_params_path).exists():
            with open(context_params_path, 'r') as f:
                self.context_params = json.load(f)
    
    def evaluate_test_set(self, test_path='data/splits/test_matches.csv'):
        """Evaluate on the test set."""
        test_df = pd.read_csv(test_path)
        print(f"✓ Loaded test set: {len(test_df)} matches")
        
        # Compute baseline predictions
        test_df = self._compute_predictions(test_df, use_adjustment=False)
        
        # Compute adjusted predictions
        test_df = self._compute_predictions(test_df, use_adjustment=True)
        
        # Compute metrics
        metrics = {
            'baseline': {
                'brier_score': float(brier_score_loss(test_df['actual_outcome'], 
                                                       test_df['baseline_pred'])),
                'accuracy': float(accuracy_score(test_df['actual_outcome'], 
                                               (test_df['baseline_pred'] > 0.5).astype(int))),
                'log_loss': float(log_loss(test_df['actual_outcome'], test_df['baseline_pred']))
            }
        }
        
        if self.adjustment_model is not None:
            metrics['adjusted'] = {
                'brier_score': float(brier_score_loss(test_df['actual_outcome'], 
                                                       test_df['adjusted_pred'])),
                'accuracy': float(accuracy_score(test_df['actual_outcome'], 
                                               (test_df['adjusted_pred'] > 0.5).astype(int))),
                'log_loss': float(log_loss(test_df['actual_outcome'], test_df['adjusted_pred']))
            }
            
            # Compute improvements
            baseline_brier = metrics['baseline']['brier_score']
            adjusted_brier = metrics['adjusted']['brier_score']
            improvement_pct = ((baseline_brier - adjusted_brier) / baseline_brier) * 100
            
            metrics['improvement'] = {
                'brier_score_delta': adjusted_brier - baseline_brier,
                'brier_score_pct': improvement_pct,
                'accuracy_delta': metrics['adjusted']['accuracy'] - metrics['baseline']['accuracy']
            }
        
        return metrics, test_df
    
    def _compute_predictions(self, df, use_adjustment=False):
        """Compute baseline and optionally adjusted predictions."""
        df = df.copy()
        
        # Fill missing values
        df['fargo_rating_p1'] = df['fargo_rating_p1'].fillna(600.0)
        df['fargo_rating_p2'] = df['fargo_rating_p2'].fillna(600.0)
        df['race_to'] = df['race_to'].fillna(7.0).astype(float)
        
        # Compute features
        df['rating_diff'] = df['fargo_rating_p1'] - df['fargo_rating_p2']
        df['rating_diff'] = df['rating_diff'].fillna(0.0)
        
        # Get baseline predictions
        features = df[['rating_diff', 'race_to']].values
        features = np.nan_to_num(features, nan=0.0)
        
        if self.baseline_model is not None:
            df['baseline_pred'] = self.baseline_model.predict_proba(features)[:, 1]
        else:
            params = self.baseline_params['coefficients']
            intercept = self.baseline_params['intercept']
            logit = (intercept + params['rating_diff'] * df['rating_diff'] +
                     params['race_to'] * df['race_to'])
            df['baseline_pred'] = 1 / (1 + np.exp(-logit))
        
        # Add actual outcome
        df['actual_outcome'] = (df['winner_id'] == df['player_1_id']).astype(int)
        
        # Get adjusted predictions if model available
        if use_adjustment and self.adjustment_model is not None:
            X = self._prepare_context_features(df)
            adjustments = self.adjustment_model.predict(X)
            df['adjusted_pred'] = np.clip(df['baseline_pred'] + adjustments, 0.001, 0.999)
        
        return df
    
    def _prepare_context_features(self, df):
        """Prepare context features for adjustment model."""
        features = []
        
        # One-hot encode context variables
        if 'table_size' in df.columns:
            for size in sorted(df['table_size'].dropna().unique()):
                features.append((df['table_size'] == size).astype(int).values)
        
        if 'format' in df.columns:
            for fmt in sorted(df['format'].dropna().unique()):
                features.append((df['format'] == fmt).astype(int).values)
        
        # Event type
        event_col = [col for col in df.columns if 'event' in col.lower()]
        if event_col:
            ec = event_col[0]
            for event in sorted(df[ec].dropna().unique()):
                features.append((df[ec] == event).astype(int).values)
        
        # Location (top 5)
        location_col = [col for col in df.columns if 'location' in col.lower()]
        if location_col:
            lc = location_col[0]
            top_locs = df[lc].value_counts().head(5).index
            for loc in sorted(top_locs):
                features.append((df[lc] == loc).astype(int).values)
        
        return np.column_stack(features) if features else np.zeros((len(df), 1))
    
    def generate_context_report(self, output_path='reports/context_analysis.json'):
        """Generate detailed context analysis report."""
        report = {
            'context_coefficients': self.context_params.get('coefficients', {}),
            'intercept': self.context_params.get('intercept'),
            'feature_names': self.context_params.get('feature_names', []),
            'adjustment_factors': self.context_params.get('adjustment_factors', {}),
            'training_metrics': self.context_params.get('training', {}),
            'validation_metrics': self.context_params.get('validation_metrics', {}),
            'stratified_metrics': self.context_params.get('stratified_metrics', {})
        }
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        return report
    
    def plot_context_effects(self, output_dir='reports'):
        """Plot context coefficient effects."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        coefs = self.context_params['coefficients']
        
        # Group coefficients by type
        table_size_coefs = {k: v for k, v in coefs.items() if 'table_size' in k}
        format_coefs = {k: v for k, v in coefs.items() if 'format' in k}
        location_coefs = {k: v for k, v in coefs.items() if 'location' in k}
        
        fig, axes = plt.subplots(1, 3, figsize=(18, 5))
        
        # Table size effects
        if table_size_coefs:
            names = [k.replace('table_size_', '') for k in sorted(table_size_coefs.keys())]
            values = [table_size_coefs[k] for k in sorted(table_size_coefs.keys())]
            colors = ['green' if v > 0 else 'red' for v in values]
            axes[0].bar(names, values, color=colors, alpha=0.7)
            axes[0].set_title('Table Size Effects', fontsize=12, fontweight='bold')
            axes[0].set_ylabel('Adjustment Coefficient')
            axes[0].axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            axes[0].grid(True, alpha=0.3, axis='y')
        
        # Format effects
        if format_coefs:
            names = [k.replace('format_', '') for k in sorted(format_coefs.keys())]
            values = [format_coefs[k] for k in sorted(format_coefs.keys())]
            colors = ['green' if v > 0 else 'red' for v in values]
            axes[1].bar(names, values, color=colors, alpha=0.7)
            axes[1].set_title('Format Effects', fontsize=12, fontweight='bold')
            axes[1].set_ylabel('Adjustment Coefficient')
            axes[1].axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            axes[1].grid(True, alpha=0.3, axis='y')
        
        # Location effects
        if location_coefs:
            names = [k.replace('location_', '').replace('_', ' ').title()[:15] 
                    for k in sorted(location_coefs.keys(), 
                                  key=lambda x: location_coefs[x])]
            values = [location_coefs[k] for k in sorted(location_coefs.keys(),
                                                       key=lambda x: location_coefs[x])]
            colors = ['green' if v > 0 else 'red' for v in values]
            axes[2].barh(names, values, color=colors, alpha=0.7)
            axes[2].set_title('Location Effects (Top 5)', fontsize=12, fontweight='bold')
            axes[2].set_xlabel('Adjustment Coefficient')
            axes[2].axvline(x=0, color='black', linestyle='-', linewidth=0.5)
            axes[2].grid(True, alpha=0.3, axis='x')
        
        plt.tight_layout()
        output_file = output_path / 'context_coefficients_visualization.png'
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"✓ Saved context coefficients plot to {output_file}")
        plt.close()
    
    def plot_adjustment_distribution(self, df_with_adjustments, output_dir='reports'):
        """Plot distribution of adjustments applied."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        if 'adjustment' not in df_with_adjustments.columns:
            return
        
        adjustments = df_with_adjustments['adjustment'].values
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
        
        # Histogram of adjustments
        ax1.hist(adjustments, bins=50, edgecolor='black', alpha=0.7, color='skyblue')
        ax1.set_xlabel('Adjustment Value')
        ax1.set_ylabel('Frequency')
        ax1.set_title('Distribution of Context Adjustments')
        ax1.axvline(x=0, color='red', linestyle='--', linewidth=2, label='No adjustment')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # CDF of adjustments
        sorted_adj = np.sort(adjustments)
        cdf = np.arange(1, len(sorted_adj) + 1) / len(sorted_adj)
        ax2.plot(sorted_adj, cdf, linewidth=2, color='blue')
        ax2.set_xlabel('Adjustment Value')
        ax2.set_ylabel('Cumulative Probability')
        ax2.set_title('CDF of Context Adjustments')
        ax2.grid(True, alpha=0.3)
        ax2.axvline(x=-0.05, color='red', linestyle='--', alpha=0.5, label='±5% bounds')
        ax2.axvline(x=0.05, color='red', linestyle='--', alpha=0.5)
        ax2.legend()
        
        plt.tight_layout()
        output_file = output_path / 'adjustment_distribution.png'
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"✓ Saved adjustment distribution plot to {output_file}")
        plt.close()
    
    def plot_prediction_scatter(self, df_test, output_dir='reports'):
        """Plot baseline vs adjusted predictions."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        if 'adjusted_pred' not in df_test.columns:
            return
        
        fig, ax = plt.subplots(figsize=(10, 10))
        
        # Scatter baseline vs adjusted
        mask = df_test['actual_outcome'] == 1
        ax.scatter(df_test[mask]['baseline_pred'], df_test[mask]['adjusted_pred'],
                  alpha=0.3, s=10, color='green', label='Actual wins')
        ax.scatter(df_test[~mask]['baseline_pred'], df_test[~mask]['adjusted_pred'],
                  alpha=0.3, s=10, color='red', label='Actual losses')
        
        # Diagonal line (no adjustment)
        ax.plot([0, 1], [0, 1], 'k--', linewidth=2, label='No adjustment')
        
        ax.set_xlabel('Baseline Prediction', fontsize=12)
        ax.set_ylabel('Adjusted Prediction', fontsize=12)
        ax.set_title('Baseline vs Adjusted Predictions', fontsize=14, fontweight='bold')
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        output_file = output_path / 'baseline_vs_adjusted_predictions.png'
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"✓ Saved prediction scatter plot to {output_file}")
        plt.close()
    
    def run_full_evaluation(self):
        """Run complete evaluation pipeline."""
        print("=" * 70)
        print("CONTEXT ADJUSTMENT LAYER - COMPREHENSIVE EVALUATION")
        print("=" * 70)
        
        # Evaluate on test set
        print("\n📋 Evaluating on Test Set:")
        test_metrics, test_df = self.evaluate_test_set()
        
        print(f"\n✓ Test Set Results:")
        print(f"  Baseline Brier:  {test_metrics['baseline']['brier_score']:.6f}")
        print(f"  Baseline Accuracy: {test_metrics['baseline']['accuracy']:.4f}")
        
        if 'adjusted' in test_metrics:
            print(f"\n  Adjusted Brier:  {test_metrics['adjusted']['brier_score']:.6f}")
            print(f"  Adjusted Accuracy: {test_metrics['adjusted']['accuracy']:.4f}")
            print(f"\n  Brier Improvement: {test_metrics['improvement']['brier_score_pct']:+.2f}%")
            print(f"  Accuracy Improvement: {test_metrics['improvement']['accuracy_delta']:+.4f}")
        
        # Generate reports
        print("\n📊 Generating analysis reports:")
        context_report = self.generate_context_report()
        print(f"✓ Generated context analysis report")
        
        # Generate plots
        print("\n📈 Generating visualizations:")
        self.plot_context_effects()
        
        # Add adjustments to test data for visualization
        if self.adjustment_model is not None:
            X = self._prepare_context_features(test_df)
            test_df['adjustment'] = self.adjustment_model.predict(X)
            self.plot_adjustment_distribution(test_df)
            self.plot_prediction_scatter(test_df)
        
        # Print context coefficients summary
        print("\n" + "=" * 70)
        print("CONTEXT ADJUSTMENT COEFFICIENTS SUMMARY")
        print("=" * 70)
        
        coefs = self.context_params['coefficients']
        
        print("\n📌 Table Size Effects:")
        for k in sorted(coefs.keys()):
            if 'table_size' in k:
                size = k.replace('table_size_', '')
                print(f"  {size:5} → {coefs[k]:+.6f}")
        
        print("\n📌 Format Effects:")
        for k in sorted(coefs.keys()):
            if 'format' in k:
                fmt = k.replace('format_', '')
                print(f"  {fmt:8} → {coefs[k]:+.6f}")
        
        print("\n📌 Location Effects (Top 5):")
        location_coefs = {k: v for k, v in coefs.items() if 'location' in k}
        for k in sorted(location_coefs.keys(), key=lambda x: abs(location_coefs[x]), reverse=True):
            loc = k.replace('location_', '').replace('_', ' ').title()
            print(f"  {loc:25} → {location_coefs[k]:+.6f}")
        
        print("\n" + "=" * 70)
        print("EVALUATION COMPLETE")
        print("=" * 70)
        print("\nGenerated files:")
        print("  - models/alfa_context_adjustments.pkl")
        print("  - models/alfa_context_params.json")
        print("  - reports/context_analysis.json")
        print("  - reports/context_coefficients_visualization.png")
        print("  - reports/adjustment_distribution.png")
        print("  - reports/baseline_vs_adjusted_predictions.png")


def main():
    """Main entry point."""
    evaluator = ContextAdjustmentEvaluator()
    evaluator.run_full_evaluation()


if __name__ == '__main__':
    main()
