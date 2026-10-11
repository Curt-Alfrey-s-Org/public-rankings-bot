"""
Example analysis scripts for match explainability data.

This module provides ready-to-use functions for analyzing per-match explanations.
Copy and run these examples in your own analysis notebooks.
"""

import pandas as pd
import json
import numpy as np
from typing import List, Dict, Tuple


# ============================================================================
# LOADING DATA
# ============================================================================

def load_explainability_data() -> Tuple[pd.DataFrame, Dict]:
    """Load CSV and JSON explainability data."""
    df_csv = pd.read_csv('metrics/alfa_match_explainers.csv')
    
    with open('metrics/alfa_match_explainers.json') as f:
        data_json = json.load(f)
    
    return df_csv, data_json


def load_feature_stats() -> Dict:
    """Load feature importance statistics."""
    with open('metrics/feature_importance_stats.json') as f:
        return json.load(f)


# ============================================================================
# BASIC QUERIES
# ============================================================================

def find_match_explanation(match_id: str, data_json: Dict) -> Dict:
    """Find explanation for a specific match by ID."""
    for match in data_json['matches']:
        if match['match_id'] == match_id:
            return match
    return None


def get_player_matches(player_name: str, df: pd.DataFrame) -> pd.DataFrame:
    """Get all matches involving a specific player."""
    return df[
        (df['player_1_name'] == player_name) | 
        (df['player_2_name'] == player_name)
    ]


def print_match_explanation(match: Dict) -> None:
    """Pretty-print a match explanation."""
    print(f"\n{'='*70}")
    print(f"MATCH: {match['match_id']}")
    print(f"{'='*70}")
    print(f"\nPlayers: {match['player_1_name']} vs {match['player_2_name']}")
    print(f"Date: {match['date']} | Location: {match['location_id']}")
    print(f"Format: {match['format']:6s} | Race to: {match['race_to']} | Table: {match['table_size']}")
    
    print(f"\nFargo Ratings: {match['fargo_rating_p1']:.1f} vs {match['fargo_rating_p2']:.1f} (gap: {match['rating_gap']:+.1f})")
    
    print(f"\nPrediction:")
    print(f"  Player 1 Win Probability: {match['predicted_win_prob_p1']:.2%}")
    print(f"  Player 2 Win Probability: {match['predicted_win_prob_p2']:.2%}")
    print(f"  Model Confidence: {match['confidence']:.2%}")
    
    print(f"\nActual Outcome: {match['actual_winner'].replace('_', ' ').title()} won")
    print(f"Prediction Correct: {'✓ YES' if match['correct_prediction'] else '✗ NO'}")
    
    print(f"\nFactor Contributions:")
    for factor in match['factors']:
        print(f"  {factor['name']:15s}")
        print(f"    Contribution: {factor['contribution']:+.6f} ({factor['contribution']*100:+.2f}%)")
        print(f"    Direction: {factor['direction'].replace('_', ' ').title()}")
        print(f"    Weight (Importance): {factor['weight']:.1%}")
    
    print(f"\nInterpretation: {match['note']}\n")


# ============================================================================
# ANALYSIS FUNCTIONS
# ============================================================================

def get_feature_importance_ranking(data_json: Dict) -> List[Dict]:
    """Get ranked feature importance."""
    return sorted(data_json['feature_importance'], 
                  key=lambda x: x['normalized_importance'], 
                  reverse=True)


def analyze_rating_gap_impact(df: pd.DataFrame) -> Dict:
    """Analyze how rating gap influences predictions."""
    return {
        'mean_contribution': df['rating_gap_contribution'].mean(),
        'std_contribution': df['rating_gap_contribution'].std(),
        'max_contribution': df['rating_gap_contribution'].max(),
        'min_contribution': df['rating_gap_contribution'].min(),
        'mean_weight': df['rating_gap_weight'].mean(),
        'correlation_with_accuracy': df['rating_gap_contribution'].corr(df['correct_prediction'])
    }


def analyze_race_to_impact(df: pd.DataFrame) -> Dict:
    """Analyze how race length influences predictions."""
    return {
        'mean_contribution': df['race_to_contribution'].mean(),
        'std_contribution': df['race_to_contribution'].std(),
        'max_contribution': df['race_to_contribution'].max(),
        'min_contribution': df['race_to_contribution'].min(),
        'mean_weight': df['race_to_weight'].mean(),
        'correlation_with_accuracy': df['race_to_contribution'].corr(df['correct_prediction'])
    }


def accuracy_by_confidence_quantile(df: pd.DataFrame, n_quantiles: int = 5) -> pd.DataFrame:
    """Analyze accuracy broken down by confidence quantiles."""
    df['confidence_quantile'] = pd.qcut(df['confidence'], q=n_quantiles, duplicates='drop')
    
    result = df.groupby('confidence_quantile', observed=True).agg({
        'correct_prediction': ['sum', 'count', 'mean'],
        'confidence': ['min', 'max', 'mean']
    })
    
    result.columns = ['correct_count', 'total_count', 'accuracy', 'conf_min', 'conf_max', 'conf_mean']
    return result


def rating_gap_buckets_analysis(df: pd.DataFrame, bucket_size: int = 50) -> pd.DataFrame:
    """Analyze accuracy and predictions by rating gap buckets."""
    df['gap_bucket'] = pd.cut(df['rating_gap'], 
                               bins=np.arange(df['rating_gap'].min(), 
                                            df['rating_gap'].max() + bucket_size, 
                                            bucket_size))
    
    result = df.groupby('gap_bucket', observed=True).agg({
        'correct_prediction': ['sum', 'count', 'mean'],
        'predicted_win_prob_p1': ['min', 'max', 'mean'],
        'confidence': 'mean'
    })
    
    result.columns = ['correct', 'total', 'accuracy', 'pred_min', 'pred_max', 'pred_mean', 'conf_mean']
    return result


def race_to_buckets_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Analyze accuracy and predictions by race length."""
    result = df.groupby('race_to').agg({
        'correct_prediction': ['sum', 'count', 'mean'],
        'predicted_win_prob_p1': ['min', 'max', 'mean'],
        'confidence': 'mean'
    })
    
    result.columns = ['correct', 'total', 'accuracy', 'pred_min', 'pred_max', 'pred_mean', 'conf_mean']
    return result.sort_index()


# ============================================================================
# FILTERING & EXPLORATION
# ============================================================================

def find_most_important_rating_gaps(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Find matches where rating gap had most impact."""
    df_temp = df.copy()
    df_temp['rating_gap_impact'] = abs(df_temp['rating_gap_contribution']) * df_temp['rating_gap_weight']
    return df_temp.nlargest(top_n, 'rating_gap_impact')[
        ['match_id', 'player_1_name', 'player_2_name', 'date', 'rating_gap',
         'rating_gap_contribution', 'rating_gap_weight', 'predicted_win_prob_p1', 
         'correct_prediction']
    ]


def find_most_important_race_lengths(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Find matches where race length had most impact."""
    df_temp = df.copy()
    df_temp['race_impact'] = abs(df_temp['race_to_contribution']) * df_temp['race_to_weight']
    return df_temp.nlargest(top_n, 'race_impact')[
        ['match_id', 'player_1_name', 'player_2_name', 'date', 'race_to',
         'race_to_contribution', 'race_to_weight', 'predicted_win_prob_p1',
         'correct_prediction']
    ]


def find_confident_errors(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Find most confident incorrect predictions."""
    errors = df[~df['correct_prediction']]
    return errors.nlargest(top_n, 'confidence')[
        ['match_id', 'player_1_name', 'player_2_name', 'date', 'predicted_win_prob_p1',
         'actual_winner', 'confidence', 'rating_gap', 'race_to']
    ]


def find_correct_uncertain(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Find correct predictions that were uncertain (low confidence)."""
    correct = df[df['correct_prediction']]
    return correct.nsmallest(top_n, 'confidence')[
        ['match_id', 'player_1_name', 'player_2_name', 'date', 'predicted_win_prob_p1',
         'actual_winner', 'confidence', 'rating_gap', 'race_to']
    ]


def find_upsets(df: pd.DataFrame) -> pd.DataFrame:
    """Find matches where lower-rated player won."""
    upsets = df[
        ((df['rating_gap'] > 0) & (df['actual_winner'] == 'player_2')) |
        ((df['rating_gap'] < 0) & (df['actual_winner'] == 'player_1'))
    ]
    return upsets[
        ['match_id', 'player_1_name', 'player_2_name', 'date', 'rating_gap',
         'actual_winner', 'correct_prediction', 'confidence']
    ].sort_values('rating_gap', key=abs, ascending=False)


# ============================================================================
# FORMAT-SPECIFIC ANALYSIS
# ============================================================================

def analyze_by_format(df: pd.DataFrame) -> pd.DataFrame:
    """Compare prediction accuracy across formats."""
    return df.groupby('format').agg({
        'correct_prediction': ['sum', 'count', 'mean'],
        'confidence': ['mean', 'std'],
        'predicted_win_prob_p1': 'mean',
        'rating_gap': 'mean'
    }).round(4)


def analyze_by_table_size(df: pd.DataFrame) -> pd.DataFrame:
    """Compare prediction accuracy across table sizes."""
    return df.groupby('table_size').agg({
        'correct_prediction': ['sum', 'count', 'mean'],
        'confidence': ['mean', 'std'],
        'predicted_win_prob_p1': 'mean',
        'rating_gap': 'mean'
    }).round(4)


def analyze_by_location(df: pd.DataFrame, min_matches: int = 20) -> pd.DataFrame:
    """Compare prediction accuracy across locations (minimum 20 matches)."""
    result = df.groupby('location_id').agg({
        'correct_prediction': ['sum', 'count', 'mean'],
        'confidence': ['mean', 'std'],
        'predicted_win_prob_p1': 'mean'
    }).round(4)
    
    # Filter to locations with minimum matches
    result = result[result[('correct_prediction', 'count')] >= min_matches]
    return result.sort_values(('correct_prediction', 'mean'), ascending=False)


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

def example_usage():
    """Demonstrate how to use these analysis functions."""
    
    print("\n" + "="*70)
    print("MATCH EXPLAINABILITY ANALYSIS EXAMPLES")
    print("="*70)
    
    # Load data
    df, data_json = load_explainability_data()
    stats = load_feature_stats()
    
    # 1. Overall statistics
    print("\n1. OVERALL STATISTICS")
    print(f"   Total matches: {len(df)}")
    print(f"   Accuracy: {df['correct_prediction'].mean():.2%}")
    print(f"   Mean confidence: {df['confidence'].mean():.4f}")
    
    # 2. Feature importance
    print("\n2. FEATURE IMPORTANCE RANKING")
    for feat in get_feature_importance_ranking(data_json):
        print(f"   {feat['feature']:15s}: {feat['normalized_importance']:.2%}")
    
    # 3. Rating gap analysis
    print("\n3. RATING GAP IMPACT")
    rating_analysis = analyze_rating_gap_impact(df)
    print(f"   Mean contribution: {rating_analysis['mean_contribution']:+.8f}")
    print(f"   Std contribution: {rating_analysis['std_contribution']:.8f}")
    print(f"   Mean weight: {rating_analysis['mean_weight']:.4f}")
    
    # 4. Race to analysis
    print("\n4. RACE LENGTH IMPACT")
    race_analysis = analyze_race_to_impact(df)
    print(f"   Mean contribution: {race_analysis['mean_contribution']:+.8f}")
    print(f"   Std contribution: {race_analysis['std_contribution']:.8f}")
    print(f"   Mean weight: {race_analysis['mean_weight']:.4f}")
    
    # 5. Accuracy by confidence quantile
    print("\n5. ACCURACY BY CONFIDENCE (Quantiles)")
    conf_by_quantile = accuracy_by_confidence_quantile(df.copy(), n_quantiles=4)
    print(conf_by_quantile)
    
    # 6. Most important rating gaps
    print("\n6. TOP 5 MATCHES - Rating Gap Impact")
    top_rating = find_most_important_rating_gaps(df, top_n=5)
    for idx, row in top_rating.iterrows():
        print(f"   {row['player_1_name']:20s} vs {row['player_2_name']:20s} "
              f"(gap: {row['rating_gap']:+7.1f}, impact: {abs(row['rating_gap_contribution']):+.6f})")
    
    # 7. Most confident errors
    print("\n7. TOP 3 CONFIDENT ERRORS")
    errors = find_confident_errors(df, top_n=3)
    for idx, row in errors.iterrows():
        print(f"   {row['match_id']}: Predicted P1={row['predicted_win_prob_p1']:.1%}, "
              f"but {row['actual_winner']} won (conf:{row['confidence']:.2%})")
    
    # 8. By format
    print("\n8. ACCURACY BY FORMAT")
    by_format = analyze_by_format(df)
    print(by_format)
    
    # 9. Single match example
    print("\n9. EXAMPLE - SINGLE MATCH EXPLANATION")
    match = find_match_explanation(df.iloc[0]['match_id'], data_json)
    print_match_explanation(match)


if __name__ == '__main__':
    example_usage()
