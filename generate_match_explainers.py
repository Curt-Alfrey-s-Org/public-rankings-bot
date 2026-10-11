"""
Generate per-match explainability factors showing what influenced each prediction.

This script:
1. Loads test set and trained logistic regression model
2. For each match, computes contribution of each factor (rating_gap, race_to)
3. Expresses contributions as absolute change in win probability and direction
4. Generates explainability output in CSV and JSON formats
5. Creates feature importance statistics and visualizations
"""

import pandas as pd
import numpy as np
import pickle
import json
import os
from datetime import datetime

# ============================================================================
# SETUP
# ============================================================================
print("=" * 80)
print("GENERATING PER-MATCH EXPLAINABILITY FACTORS")
print("=" * 80)
print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

os.makedirs('metrics', exist_ok=True)

# ============================================================================
# 1. LOAD TEST SET AND MODEL
# ============================================================================
print("STEP 1: Loading Test Data and Model")
print("-" * 80)

# Load test data
test_df = pd.read_csv('data/splits/test_matches.csv')
print(f"✓ Loaded {len(test_df)} test matches")

# Create features
test_df['rating_diff'] = test_df['fargo_rating_p1'] - test_df['fargo_rating_p2']
test_df['player_1_wins'] = (test_df['winner_id'] == test_df['player_1_id']).astype(int)

# Remove NaN rows
valid_idx = ~(test_df['rating_diff'].isnull() | test_df['race_to'].isnull())
test_clean = test_df[valid_idx].copy().reset_index(drop=True)
print(f"✓ Test set after removing NaN: {len(test_clean)} matches\n")

# Load model and parameters
with open('models/alfa_logistic_regression.pkl', 'rb') as f:
    model = pickle.load(f)

with open('models/alfa_model_params.json', 'r') as f:
    params = json.load(f)

coeff_rating_diff = params['coefficients']['rating_diff']
coeff_race_to = params['coefficients']['race_to']
intercept = params['intercept']

print(f"✓ Model loaded:")
print(f"  rating_diff coefficient: {coeff_rating_diff:.8f}")
print(f"  race_to coefficient: {coeff_race_to:.8f}")
print(f"  intercept: {intercept:.8f}\n")

# ============================================================================
# 2. COMPUTE LOGISTIC FUNCTION FOR PROBABILITY EXPLANATIONS
# ============================================================================
print("STEP 2: Computing Per-Match Contributions")
print("-" * 80)

def sigmoid(x):
    """Compute sigmoid function with numerical stability."""
    return 1.0 / (1.0 + np.exp(-np.clip(x, -500, 500)))

# Get full prediction (with all features)
X = test_clean[['rating_diff', 'race_to']].values
log_odds_full = intercept + X[:, 0] * coeff_rating_diff + X[:, 1] * coeff_race_to
prob_full = sigmoid(log_odds_full)

# Get baseline prediction (intercept only, zero features)
log_odds_baseline = intercept
prob_baseline = sigmoid(log_odds_baseline)

# Feature-specific contributions via log-odds
# For rating_diff: what happens if we set it to 0?
log_odds_without_rating = intercept + X[:, 1] * coeff_race_to
prob_without_rating = sigmoid(log_odds_without_rating)

# For race_to: what happens if we set it to 0?
log_odds_without_race = intercept + X[:, 0] * coeff_rating_diff
prob_without_race = sigmoid(log_odds_without_race)

# Compute contributions as probability differences
contribution_rating_diff = prob_without_race - prob_baseline
contribution_race_to = prob_without_rating - prob_baseline

print(f"✓ Baseline prediction (no features): {prob_baseline:.4f}")
print(f"✓ Mean full prediction: {prob_full.mean():.4f}")
print(f"✓ Mean rating_diff contribution: {contribution_rating_diff.mean():+.6f}")
print(f"✓ Mean race_to contribution: {contribution_race_to.mean():+.6f}\n")

# ============================================================================
# 3. COMPUTE WEIGHTS AND DIRECTIONS
# ============================================================================
print("STEP 3: Computing Feature Weights and Directions")
print("-" * 80)

# Weight is based on absolute contribution magnitude (relative importance)
abs_contrib_rating = np.abs(contribution_rating_diff)
abs_contrib_race = np.abs(contribution_race_to)
total_contrib = abs_contrib_rating + abs_contrib_race

# Avoid division by zero
weight_rating = np.where(
    total_contrib > 1e-10,
    abs_contrib_rating / total_contrib,
    0.5
)
weight_race = np.where(
    total_contrib > 1e-10,
    abs_contrib_race / total_contrib,
    0.5
)

# Direction based on sign and relationship to P1 probability
direction_rating = np.where(contribution_rating_diff >= 0, 'favors_p1', 'favors_p2')
direction_race = np.where(contribution_race_to >= 0, 'favors_p1', 'favors_p2')

print(f"✓ Weight statistics (rating_diff):")
print(f"  Mean: {weight_rating.mean():.4f}, Median: {np.median(weight_rating):.4f}")
print(f"  Std: {weight_rating.std():.4f}, Range: [{weight_rating.min():.4f}, {weight_rating.max():.4f}]")
print(f"✓ Weight statistics (race_to):")
print(f"  Mean: {weight_race.mean():.4f}, Median: {np.median(weight_race):.4f}")
print(f"  Std: {weight_race.std():.4f}, Range: [{weight_race.min():.4f}, {weight_race.max():.4f}]\n")

# ============================================================================
# 4. COMPUTE CONFIDENCE SCORES
# ============================================================================
print("STEP 4: Computing Confidence Scores")
print("-" * 80)

# Confidence based on distance from 50%
distance_from_50 = np.abs(prob_full - 0.5)
confidence = 2 * distance_from_50  # Scale from [0, 0.5] to [0, 1]
confidence = np.clip(confidence, 0, 1)

print(f"✓ Confidence distribution:")
print(f"  Mean: {confidence.mean():.4f}, Median: {np.median(confidence):.4f}")
print(f"  Std: {confidence.std():.4f}, Range: [{confidence.min():.4f}, {confidence.max():.4f}]")

# Find high and low confidence matches
high_confidence_idx = np.argsort(confidence)[-100:]
low_confidence_idx = np.argsort(confidence)[:100]
print(f"  {len(high_confidence_idx)} high-confidence matches (>0.7)")
print(f"  {len(low_confidence_idx)} low-confidence matches (<0.3)\n")

# ============================================================================
# 5. BUILD EXPLAINABILITY RECORDS
# ============================================================================
print("STEP 5: Building Explainability Records")
print("-" * 80)

explainers = []

for idx, row in test_clean.iterrows():
    match_id = row['match_id']
    predicted_prob_p1 = prob_full[idx]
    
    # Gather factor information
    factors = [
        {
            'name': 'rating_gap',
            'feature_value': row['rating_diff'],
            'contribution': float(contribution_rating_diff[idx]),
            'direction': direction_rating[idx],
            'weight': float(weight_rating[idx])
        },
        {
            'name': 'race_to',
            'feature_value': row['race_to'],
            'contribution': float(contribution_race_to[idx]),
            'direction': direction_race[idx],
            'weight': float(weight_race[idx])
        }
    ]
    
    # Generate note
    if confidence[idx] < 0.3:
        note = "Prediction close to 50/50; match likely decided by execution"
    elif confidence[idx] > 0.7:
        note = "High confidence prediction based on clear rating/race advantage"
    else:
        note = "Moderate confidence prediction"
    
    # Add actual outcome for comparison
    actual_p1_win = row['player_1_wins']
    
    explainer = {
        'match_id': match_id,
        'player_1_name': row['player_1_name'],
        'player_2_name': row['player_2_name'],
        'date': row['date'],
        'location_id': row['location_id'],
        'table_size': row['table_size'],
        'format': row['format'],
        'race_to': int(row['race_to']),
        'fargo_rating_p1': float(row['fargo_rating_p1']),
        'fargo_rating_p2': float(row['fargo_rating_p2']),
        'rating_gap': float(row['rating_diff']),
        'predicted_win_prob_p1': float(predicted_prob_p1),
        'predicted_win_prob_p2': float(1.0 - predicted_prob_p1),
        'actual_winner': 'player_1' if actual_p1_win else 'player_2',
        'correct_prediction': bool(actual_p1_win == (predicted_prob_p1 > 0.5)),
        'factors': factors,
        'confidence': float(confidence[idx]),
        'note': note
    }
    
    explainers.append(explainer)
    
    if (idx + 1) % 500 == 0:
        print(f"  Processed {idx + 1} / {len(test_clean)} matches")

print(f"✓ Generated {len(explainers)} explainability records\n")

# ============================================================================
# 6. GENERATE STATISTICS
# ============================================================================
print("STEP 6: Generating Feature Importance Statistics")
print("-" * 80)

# Feature importance: average absolute contribution
avg_importance_rating = np.mean(np.abs(contribution_rating_diff))
avg_importance_race = np.mean(np.abs(contribution_race_to))

# Total importance (normalize to sum to 1)
total_importance = avg_importance_rating + avg_importance_race
norm_importance_rating = avg_importance_rating / total_importance if total_importance > 0 else 0.5
norm_importance_race = avg_importance_race / total_importance if total_importance > 0 else 0.5

feature_importance = [
    {
        'feature': 'rating_gap',
        'average_contribution': float(avg_importance_rating),
        'normalized_importance': float(norm_importance_rating),
        'rank': 1 if norm_importance_rating >= norm_importance_race else 2,
        'direction_dominant': 'favors_p1' if coeff_rating_diff > 0 else 'favors_p2',
        'coefficient': float(coeff_rating_diff)
    },
    {
        'feature': 'race_to',
        'average_contribution': float(avg_importance_race),
        'normalized_importance': float(norm_importance_race),
        'rank': 2 if norm_importance_rating >= norm_importance_race else 1,
        'direction_dominant': 'favors_p1' if coeff_race_to > 0 else 'favors_p2',
        'coefficient': float(coeff_race_to)
    }
]

# Sort by normalized importance
feature_importance.sort(key=lambda x: x['normalized_importance'], reverse=True)
for i, feat in enumerate(feature_importance, 1):
    feat['rank'] = i

print(f"Feature Importance Ranking:")
for feat in feature_importance:
    print(f"  {feat['rank']}. {feat['feature']:15s} - {feat['normalized_importance']:6.2%} importance")
    print(f"     Avg contribution: {feat['average_contribution']:+.6f}")
    print(f"     Dominant direction: {feat['direction_dominant']}")

# Accuracy statistics
predictions = np.array([e['predicted_win_prob_p1'] > 0.5 for e in explainers])
actuals = np.array([e['actual_winner'] == 'player_1' for e in explainers])
accuracy = (predictions == actuals).sum() / len(predictions)

print(f"\n✓ Prediction Accuracy: {accuracy:.4f} ({100*accuracy:.2f}%)")
print(f"✓ Correct predictions: {(predictions == actuals).sum()} / {len(predictions)}")

# Confidence statistics
confidences = np.array([e['confidence'] for e in explainers])
print(f"\n✓ Confidence distribution:")
print(f"  Mean: {confidences.mean():.4f}, Median: {np.median(confidences):.4f}")
print(f"  Std: {confidences.std():.4f}")
print(f"  P25: {np.percentile(confidences, 25):.4f}, P75: {np.percentile(confidences, 75):.4f}\n")

# ============================================================================
# 7. SAVE CSV OUTPUT
# ============================================================================
print("STEP 7: Saving CSV Output")
print("-" * 80)

csv_records = []
for exp in explainers:
    record = {
        'match_id': exp['match_id'],
        'player_1_name': exp['player_1_name'],
        'player_2_name': exp['player_2_name'],
        'date': exp['date'],
        'location_id': exp['location_id'],
        'table_size': exp['table_size'],
        'format': exp['format'],
        'race_to': exp['race_to'],
        'fargo_rating_p1': round(exp['fargo_rating_p1'], 1),
        'fargo_rating_p2': round(exp['fargo_rating_p2'], 1),
        'rating_gap': round(exp['rating_gap'], 1),
        'predicted_win_prob_p1': round(exp['predicted_win_prob_p1'], 4),
        'predicted_win_prob_p2': round(exp['predicted_win_prob_p2'], 4),
        'actual_winner': exp['actual_winner'],
        'correct_prediction': exp['correct_prediction'],
        'rating_gap_contribution': round(exp['factors'][0]['contribution'], 6),
        'rating_gap_direction': exp['factors'][0]['direction'],
        'rating_gap_weight': round(exp['factors'][0]['weight'], 4),
        'race_to_contribution': round(exp['factors'][1]['contribution'], 6),
        'race_to_direction': exp['factors'][1]['direction'],
        'race_to_weight': round(exp['factors'][1]['weight'], 4),
        'confidence': round(exp['confidence'], 4),
        'note': exp['note']
    }
    csv_records.append(record)

csv_df = pd.DataFrame(csv_records)
csv_path = 'metrics/alfa_match_explainers.csv'
csv_df.to_csv(csv_path, index=False)
print(f"✓ Saved CSV to {csv_path}")
print(f"  Columns: {len(csv_df.columns)}")
print(f"  Rows: {len(csv_df)}\n")

# ============================================================================
# 8. SAVE JSON OUTPUT
# ============================================================================
print("STEP 8: Saving JSON Output")
print("-" * 80)

json_output = {
    'metadata': {
        'generated_at': datetime.now().isoformat(),
        'num_matches': len(explainers),
        'model_type': 'LogisticRegression',
        'features': ['rating_gap', 'race_to']
    },
    'model_parameters': {
        'intercept': intercept,
        'coefficients': {
            'rating_gap': coeff_rating_diff,
            'race_to': coeff_race_to
        }
    },
    'feature_importance': feature_importance,
    'statistics': {
        'accuracy': float(accuracy),
        'mean_confidence': float(confidences.mean()),
        'median_confidence': float(np.median(confidences)),
        'confidence_std': float(confidences.std())
    },
    'matches': explainers
}

json_path = 'metrics/alfa_match_explainers.json'
with open(json_path, 'w') as f:
    json.dump(json_output, f, indent=2)
print(f"✓ Saved JSON to {json_path}")
print(f"  Size: {len(json.dumps(json_output)) / 1024 / 1024:.2f} MB\n")

# ============================================================================
# 9. SAVE FEATURE IMPORTANCE STATISTICS
# ============================================================================
print("STEP 9: Saving Feature Importance Statistics")
print("-" * 80)

importance_stats = {
    'feature_ranking': feature_importance,
    'per_match_distribution': {
        'rating_gap': {
            'mean_contribution': float(np.mean(np.abs(contribution_rating_diff))),
            'std_contribution': float(np.std(np.abs(contribution_rating_diff))),
            'min_contribution': float(np.min(np.abs(contribution_rating_diff))),
            'max_contribution': float(np.max(np.abs(contribution_rating_diff))),
            'mean_weight': float(np.mean(weight_rating)),
            'std_weight': float(np.std(weight_rating))
        },
        'race_to': {
            'mean_contribution': float(np.mean(np.abs(contribution_race_to))),
            'std_contribution': float(np.std(np.abs(contribution_race_to))),
            'min_contribution': float(np.min(np.abs(contribution_race_to))),
            'max_contribution': float(np.max(np.abs(contribution_race_to))),
            'mean_weight': float(np.mean(weight_race)),
            'std_weight': float(np.std(weight_race))
        }
    },
    'prediction_calibration': {
        'accuracy': float(accuracy),
        'correct_predictions': int((predictions == actuals).sum()),
        'total_predictions': len(predictions),
        'mean_predicted_prob': float(np.mean(prob_full)),
        'std_predicted_prob': float(np.std(prob_full))
    },
    'confidence': {
        'mean': float(np.mean(confidences)),
        'median': float(np.median(confidences)),
        'std': float(np.std(confidences)),
        'min': float(np.min(confidences)),
        'max': float(np.max(confidences)),
        'p25': float(np.percentile(confidences, 25)),
        'p75': float(np.percentile(confidences, 75))
    }
}

importance_path = 'metrics/feature_importance_stats.json'
with open(importance_path, 'w') as f:
    json.dump(importance_stats, f, indent=2)
print(f"✓ Saved feature importance stats to {importance_path}\n")

# ============================================================================
# 10. PRINT SAMPLE EXPLANATIONS
# ============================================================================
print("STEP 10: Sample Match Explanations")
print("-" * 80)

# High confidence examples (best calibrated)
print("\nHIGH CONFIDENCE EXAMPLES (Top 3):")
high_conf_examples = sorted(explainers, key=lambda x: x['confidence'], reverse=True)[:3]
for i, exp in enumerate(high_conf_examples, 1):
    print(f"\n{i}. {exp['match_id']}")
    print(f"   {exp['player_1_name']} vs {exp['player_2_name']}")
    print(f"   Predicted P1 win: {exp['predicted_win_prob_p1']:.1%} (Confidence: {exp['confidence']:.1%})")
    print(f"   Actual: {'Player 1 won' if exp['actual_winner'] == 'player_1' else 'Player 2 won'}")
    print(f"   Rating gap: {exp['rating_gap']:+.1f}")
    print(f"   Note: {exp['note']}")

# Low confidence examples (close matches)
print("\n\nLOW CONFIDENCE EXAMPLES (Bottom 3):")
low_conf_examples = sorted(explainers, key=lambda x: x['confidence'])[:3]
for i, exp in enumerate(low_conf_examples, 1):
    print(f"\n{i}. {exp['match_id']}")
    print(f"   {exp['player_1_name']} vs {exp['player_2_name']}")
    print(f"   Predicted P1 win: {exp['predicted_win_prob_p1']:.1%} (Confidence: {exp['confidence']:.1%})")
    print(f"   Actual: {'Player 1 won' if exp['actual_winner'] == 'player_1' else 'Player 2 won'}")
    print(f"   Rating gap: {exp['rating_gap']:+.1f}")
    print(f"   Note: {exp['note']}")

# Misclassified examples
print("\n\nMISCLASSIFIED EXAMPLES (Top 3 most confident errors):")
misclassified = [e for e in explainers if not e['correct_prediction']]
misclassified = sorted(misclassified, key=lambda x: x['confidence'], reverse=True)[:3]
for i, exp in enumerate(misclassified, 1):
    print(f"\n{i}. {exp['match_id']}")
    print(f"   {exp['player_1_name']} vs {exp['player_2_name']}")
    print(f"   Predicted P1 win: {exp['predicted_win_prob_p1']:.1%} (Confidence: {exp['confidence']:.1%})")
    print(f"   Actual: {'Player 1 won' if exp['actual_winner'] == 'player_1' else 'Player 2 won'}")
    print(f"   Rating gap: {exp['rating_gap']:+.1f}")
    print(f"   Note: {exp['note']} [INCORRECT]")

print("\n" + "=" * 80)
print("EXPLAINABILITY GENERATION COMPLETE!")
print("=" * 80)
print(f"\nOutputs saved to:")
print(f"  • {csv_path}")
print(f"  • {json_path}")
print(f"  • {importance_path}")
