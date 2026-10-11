#!/usr/bin/env python3
"""
Generate comprehensive context adjustment analysis report.
Produces:
  - metrics/context_adjustment_analysis.json (detailed results)
  - metrics/brier_improvement_summary.csv (before/after comparison)
"""

import json
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.metrics import brier_score_loss, accuracy_score, log_loss
from typing import Dict, Tuple


class ContextAdjustmentAnalyzer:
    """Generate comprehensive analysis of context adjustments."""
    
    def __init__(self):
        """Initialize analyzer."""
        self.baseline_model = None
        self.baseline_params = None
        self.adjustment_model = None
        self.context_params = None
        self._load_models()
    
    def _load_models(self):
        """Load all required models."""
        # Load baseline model
        baseline_path = Path("models/alfa_logistic_regression.pkl")
        if baseline_path.exists():
            with open(baseline_path, 'rb') as f:
                self.baseline_model = pickle.load(f)
        
        # Load baseline params
        baseline_params_path = Path("models/alfa_model_params.json")
        if baseline_params_path.exists():
            with open(baseline_params_path, 'r') as f:
                self.baseline_params = json.load(f)
        
        # Load adjustment model
        adjustment_path = Path("models/alfa_context_adjustments.pkl")
        if adjustment_path.exists():
            with open(adjustment_path, 'rb') as f:
                self.adjustment_model = pickle.load(f)
        
        # Load context params
        context_params_path = Path("models/alfa_context_params.json")
        if context_params_path.exists():
            with open(context_params_path, 'r') as f:
                self.context_params = json.load(f)
    
    def _compute_baseline_predictions(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute baseline predictions."""
        df = df.copy()
        
        # Fill missing ratings
        df['fargo_rating_p1'] = df['fargo_rating_p1'].fillna(600.0)
        df['fargo_rating_p2'] = df['fargo_rating_p2'].fillna(600.0)
        
        # Compute features
        df['rating_diff'] = df['fargo_rating_p1'] - df['fargo_rating_p2']
        df['rating_diff'] = df['rating_diff'].fillna(0.0)
        df['race_to'] = df['race_to'].fillna(7.0).astype(float)
        
        # Get predictions
        features = df[['rating_diff', 'race_to']].values
        features = np.nan_to_num(features, nan=0.0)
        
        if self.baseline_model is not None:
            df['baseline_pred'] = self.baseline_model.predict_proba(features)[:, 1]
        else:
            # Fallback
            params = self.baseline_params['coefficients']
            intercept = self.baseline_params['intercept']
            logit = (intercept + 
                     params['rating_diff'] * df['rating_diff'] +
                     params['race_to'] * df['race_to'])
            df['baseline_pred'] = 1 / (1 + np.exp(-logit))
        
        # Actual outcome
        df['actual_outcome'] = (df['winner_id'] == df['player_1_id']).astype(int)
        return df
    
    def _prepare_context_features(self, df: pd.DataFrame) -> np.ndarray:
        """Prepare context features."""
        features = []
        
        if 'table_size' in df.columns:
            for size in sorted(df['table_size'].dropna().unique()):
                features.append((df['table_size'] == size).astype(int).values)
        
        if 'format' in df.columns:
            for fmt in sorted(df['format'].dropna().unique()):
                features.append((df['format'] == fmt).astype(int).values)
        
        event_col = [col for col in df.columns if 'event' in col.lower()]
        if event_col:
            ec = event_col[0]
            for event in sorted(df[ec].dropna().unique()):
                features.append((df[ec] == event).astype(int).values)
        
        location_col = [col for col in df.columns if 'location' in col.lower()]
        if location_col:
            lc = location_col[0]
            top_locs = df[lc].value_counts().head(5).index
            for loc in sorted(top_locs):
                features.append((df[lc] == loc).astype(int).values)
        
        return np.column_stack(features) if features else np.zeros((len(df), 1))
    
    def evaluate_all_splits(self) -> Dict:
        """Evaluate on train, val, and test splits."""
        all_metrics = {}
        
        for split_name in ['train', 'val', 'test']:
            split_path = Path(f"data/splits/{split_name}_matches.csv")
            if not split_path.exists():
                print(f"⚠ {split_name} split not found")
                continue
            
            df = pd.read_csv(split_path)
            df = self._compute_baseline_predictions(df)
            
            # Get adjusted predictions if model exists
            if self.adjustment_model is not None:
                X = self._prepare_context_features(df)
                adjustments = self.adjustment_model.predict(X)
                df['adjusted_pred'] = df['baseline_pred'] + adjustments
                df['adjusted_pred'] = np.clip(df['adjusted_pred'], 0.001, 0.999)
            
            # Compute metrics
            metrics = self._compute_split_metrics(df, split_name)
            all_metrics[split_name] = metrics
        
        return all_metrics
    
    def _compute_split_metrics(self, df: pd.DataFrame, split_name: str) -> Dict:
        """Compute metrics for a split."""
        metrics = {
            'split': split_name,
            'num_samples': len(df),
            'baseline': {
                'brier_score': float(brier_score_loss(df['actual_outcome'], df['baseline_pred'])),
                'accuracy': float(accuracy_score(df['actual_outcome'], 
                                               (df['baseline_pred'] > 0.5).astype(int))),
                'log_loss': float(log_loss(df['actual_outcome'], df['baseline_pred']))
            }
        }
        
        if 'adjusted_pred' in df.columns:
            metrics['adjusted'] = {
                'brier_score': float(brier_score_loss(df['actual_outcome'], df['adjusted_pred'])),
                'accuracy': float(accuracy_score(df['actual_outcome'], 
                                               (df['adjusted_pred'] > 0.5).astype(int))),
                'log_loss': float(log_loss(df['actual_outcome'], df['adjusted_pred']))
            }
            
            baseline_brier = metrics['baseline']['brier_score']
            adjusted_brier = metrics['adjusted']['brier_score']
            brier_improvement_pct = ((baseline_brier - adjusted_brier) / baseline_brier) * 100
            
            metrics['improvement'] = {
                'brier_score_delta': float(adjusted_brier - baseline_brier),
                'brier_score_pct': float(brier_improvement_pct),
                'accuracy_delta': float(metrics['adjusted']['accuracy'] - metrics['baseline']['accuracy']),
                'log_loss_delta': float(metrics['adjusted']['log_loss'] - metrics['baseline']['log_loss'])
            }
        
        return metrics
    
    def generate_stratified_analysis(self) -> Dict:
        """Generate stratified analysis by context."""
        analysis = {}
        
        # Load splits
        splits = {}
        for split_name in ['val', 'test']:
            split_path = Path(f"data/splits/{split_name}_matches.csv")
            if split_path.exists():
                df = pd.read_csv(split_path)
                df = self._compute_baseline_predictions(df)
                
                if self.adjustment_model is not None:
                    X = self._prepare_context_features(df)
                    adjustments = self.adjustment_model.predict(X)
                    df['adjusted_pred'] = df['baseline_pred'] + adjustments
                    df['adjusted_pred'] = np.clip(df['adjusted_pred'], 0.001, 0.999)
                
                splits[split_name] = df
        
        # Analyze by table size
        analysis['by_table_size'] = {}
        for split_name, df in splits.items():
            analysis['by_table_size'][split_name] = {}
            for size in sorted(df['table_size'].dropna().unique()):
                mask = df['table_size'] == size
                subset = df[mask]
                metrics = self._compute_subset_metrics(subset)
                analysis['by_table_size'][split_name][size] = metrics
        
        # Analyze by format
        analysis['by_format'] = {}
        for split_name, df in splits.items():
            analysis['by_format'][split_name] = {}
            for fmt in sorted(df['format'].dropna().unique()):
                mask = df['format'] == fmt
                subset = df[mask]
                metrics = self._compute_subset_metrics(subset)
                analysis['by_format'][split_name][fmt] = metrics
        
        # Analyze by event type
        analysis['by_event'] = {}
        for split_name, df in splits.items():
            analysis['by_event'][split_name] = {}
            event_col = [col for col in df.columns if 'event' in col.lower()]
            if event_col:
                ec = event_col[0]
                for event in sorted(df[ec].dropna().unique()):
                    mask = df[ec] == event
                    subset = df[mask]
                    metrics = self._compute_subset_metrics(subset)
                    analysis['by_event'][split_name][event] = metrics
        
        # Analyze by location (top 5)
        analysis['by_location'] = {}
        for split_name, df in splits.items():
            analysis['by_location'][split_name] = {}
            location_col = [col for col in df.columns if 'location' in col.lower()]
            if location_col:
                lc = location_col[0]
                top_locs = df[lc].value_counts().head(5).index
                for loc in sorted(top_locs):
                    mask = df[lc] == loc
                    subset = df[mask]
                    metrics = self._compute_subset_metrics(subset)
                    analysis['by_location'][split_name][loc] = metrics
        
        return analysis
    
    def _compute_subset_metrics(self, df: pd.DataFrame) -> Dict:
        """Compute metrics for a subset."""
        metrics = {
            'num_samples': len(df),
            'baseline': {
                'brier_score': float(brier_score_loss(df['actual_outcome'], df['baseline_pred'])),
                'accuracy': float(accuracy_score(df['actual_outcome'], 
                                               (df['baseline_pred'] > 0.5).astype(int)))
            }
        }
        
        if 'adjusted_pred' in df.columns:
            metrics['adjusted'] = {
                'brier_score': float(brier_score_loss(df['actual_outcome'], df['adjusted_pred'])),
                'accuracy': float(accuracy_score(df['actual_outcome'], 
                                               (df['adjusted_pred'] > 0.5).astype(int)))
            }
            
            baseline_brier = metrics['baseline']['brier_score']
            adjusted_brier = metrics['adjusted']['brier_score']
            if baseline_brier > 0:
                improvement_pct = ((baseline_brier - adjusted_brier) / baseline_brier) * 100
            else:
                improvement_pct = 0
            
            metrics['improvement'] = {
                'brier_score_delta': float(adjusted_brier - baseline_brier),
                'brier_score_pct': float(improvement_pct)
            }
        
        return metrics
    
    def generate_context_coefficients_summary(self) -> Dict:
        """Generate summary of context coefficients."""
        summary = {
            'intercept': self.context_params['intercept'],
            'coefficients_by_context': {}
        }
        
        # Group coefficients by context type
        for feature_name, coef_value in self.context_params['coefficients'].items():
            # Extract context type
            if 'table_size' in feature_name:
                context_type = 'table_size'
                context_value = feature_name.split('table_size_')[1]
            elif 'format' in feature_name:
                context_type = 'format'
                context_value = feature_name.split('format_')[1]
            elif 'event' in feature_name:
                context_type = 'event'
                context_value = feature_name.split('event_')[1]
            elif 'location' in feature_name:
                context_type = 'location'
                context_value = feature_name.split('location_')[1]
            else:
                continue
            
            if context_type not in summary['coefficients_by_context']:
                summary['coefficients_by_context'][context_type] = {}
            
            summary['coefficients_by_context'][context_type][context_value] = float(coef_value)
        
        return summary
    
    def generate_full_report(self) -> Dict:
        """Generate complete analysis report."""
        print("📊 Evaluating all splits...")
        split_metrics = self.evaluate_all_splits()
        
        print("📊 Generating stratified analysis...")
        stratified = self.generate_stratified_analysis()
        
        print("📊 Summarizing context coefficients...")
        coefficients = self.generate_context_coefficients_summary()
        
        report = {
            'timestamp': pd.Timestamp.now().isoformat(),
            'model_info': {
                'baseline_model': 'alfa_logistic_regression',
                'adjustment_model': 'linear_regression',
                'training_data': 'data/splits/train_matches.csv',
                'validation_data': 'data/splits/val_matches.csv',
                'test_data': 'data/splits/test_matches.csv'
            },
            'split_metrics': split_metrics,
            'stratified_analysis': stratified,
            'context_coefficients': coefficients,
            'adjustment_constraints': {
                'max_adjustment': 0.05,
                'units': 'prediction probability'
            }
        }
        
        return report
    
    def generate_brier_improvement_csv(self, split_metrics: Dict) -> pd.DataFrame:
        """Generate Brier improvement summary CSV."""
        rows = []
        
        for split_name, metrics in split_metrics.items():
            row = {
                'split': split_name,
                'num_samples': metrics['num_samples'],
                'baseline_brier_score': metrics['baseline']['brier_score'],
                'baseline_accuracy': metrics['baseline']['accuracy'],
                'baseline_log_loss': metrics['baseline']['log_loss']
            }
            
            if 'adjusted' in metrics:
                row['adjusted_brier_score'] = metrics['adjusted']['brier_score']
                row['adjusted_accuracy'] = metrics['adjusted']['accuracy']
                row['adjusted_log_loss'] = metrics['adjusted']['log_loss']
                row['brier_improvement_delta'] = metrics['improvement']['brier_score_delta']
                row['brier_improvement_pct'] = metrics['improvement']['brier_score_pct']
                row['accuracy_improvement'] = metrics['improvement']['accuracy_delta']
                row['log_loss_improvement'] = metrics['improvement']['log_loss_delta']
            
            rows.append(row)
        
        df = pd.DataFrame(rows)
        
        # Add stratified rows for validation set if available
        if 'val' in split_metrics:
            # Add table size rows
            rows_by_context = []
            
            for size in ['7ft', '8ft', '9ft']:
                if 'table_size' in split_metrics['val'] and size in split_metrics['val']['table_size']:
                    metrics = split_metrics['val']['table_size'][size]
                    row = {
                        'split': f'val_table_size_{size}',
                        'num_samples': metrics['num_samples'],
                        'baseline_brier_score': metrics['baseline']['brier_score'],
                        'baseline_accuracy': metrics['baseline']['accuracy']
                    }
                    if 'adjusted' in metrics:
                        row['adjusted_brier_score'] = metrics['adjusted']['brier_score']
                        row['adjusted_accuracy'] = metrics['adjusted']['accuracy']
                        row['brier_improvement_delta'] = metrics['improvement']['brier_score_delta']
                        row['brier_improvement_pct'] = metrics['improvement']['brier_score_pct']
                    rows_by_context.append(row)
            
            if rows_by_context:
                df_context = pd.DataFrame(rows_by_context)
                df = pd.concat([df, df_context], ignore_index=True)
        
        return df
    
    def run(self):
        """Run the analysis and save outputs."""
        print("=" * 70)
        print("CONTEXT ADJUSTMENT ANALYSIS REPORT GENERATION")
        print("=" * 70)
        
        # Generate full report
        report = self.generate_full_report()
        
        # Save detailed analysis JSON
        print("\n💾 Saving detailed analysis...")
        metrics_dir = Path("metrics")
        metrics_dir.mkdir(exist_ok=True)
        
        analysis_file = metrics_dir / "context_adjustment_analysis.json"
        with open(analysis_file, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"✓ Saved context_adjustment_analysis.json")
        
        # Generate and save Brier improvement CSV
        print("\n💾 Saving Brier improvement summary...")
        split_metrics = report['split_metrics']
        
        # First, we need to add stratified metrics to split_metrics for the CSV
        val_metrics = split_metrics.get('val', {})
        if val_metrics:
            val_metrics['table_size'] = report['stratified_analysis'].get('by_table_size', {}).get('val', {})
            val_metrics['format'] = report['stratified_analysis'].get('by_format', {}).get('val', {})
        
        csv_df = self.generate_brier_improvement_csv(split_metrics)
        csv_file = metrics_dir / "brier_improvement_summary.csv"
        csv_df.to_csv(csv_file, index=False)
        print(f"✓ Saved brier_improvement_summary.csv")
        
        # Print summary
        self._print_summary(report)
        
        print("\n" + "=" * 70)
        print("✓ Analysis complete! Output files:")
        print("  - metrics/context_adjustment_analysis.json")
        print("  - metrics/brier_improvement_summary.csv")
        print("=" * 70)
    
    def _print_summary(self, report: Dict):
        """Print summary of report."""
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        
        print("\n📊 Overall Brier Score Performance:")
        for split_name, metrics in report['split_metrics'].items():
            baseline = metrics['baseline']['brier_score']
            print(f"\n  {split_name.upper()}:")
            print(f"    Baseline: {baseline:.6f}")
            if 'adjusted' in metrics:
                adjusted = metrics['adjusted']['brier_score']
                improvement = metrics['improvement']['brier_score_pct']
                print(f"    Adjusted: {adjusted:.6f}")
                print(f"    Improvement: {improvement:+.2f}%")
        
        print("\n📈 Context Coefficients (Top Effects):")
        coefs = report['context_coefficients']['coefficients_by_context']
        
        # Find largest positive and negative effects
        all_effects = []
        for context_type, values in coefs.items():
            for context_value, coef in values.items():
                all_effects.append({
                    'context': f"{context_type}={context_value}",
                    'coefficient': coef
                })
        
        all_effects.sort(key=lambda x: abs(x['coefficient']), reverse=True)
        
        print("\n  Top 5 Positive Effects (boost predictions):")
        positive = [e for e in all_effects if e['coefficient'] > 0][:5]
        for i, effect in enumerate(positive, 1):
            print(f"    {i}. {effect['context']:<30} {effect['coefficient']:+.6f}")
        
        print("\n  Top 5 Negative Effects (reduce predictions):")
        negative = [e for e in all_effects if e['coefficient'] < 0][:5]
        for i, effect in enumerate(negative, 1):
            print(f"    {i}. {effect['context']:<30} {effect['coefficient']:+.6f}")


def main():
    """Main entry point."""
    analyzer = ContextAdjustmentAnalyzer()
    analyzer.run()


if __name__ == "__main__":
    main()
