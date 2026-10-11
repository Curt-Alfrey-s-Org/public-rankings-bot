"""
Create visualizations and summary report for match explainability.

This script:
1. Creates feature importance bar chart
2. Shows contribution distributions
3. Generates confidence distribution plot
4. Creates sample match explanation tables
5. Generates comprehensive summary report
"""

import pandas as pd
import numpy as np
import json
import matplotlib.pyplot as plt
import os

# ============================================================================
# SETUP
# ============================================================================
print("\n" + "=" * 80)
print("GENERATING VISUALIZATIONS AND REPORT")
print("=" * 80 + "\n")

os.makedirs('metrics/visualizations', exist_ok=True)

# Load explainability data
with open('metrics/alfa_match_explainers.json', 'r') as f:
    json_data = json.load(f)

csv_data = pd.read_csv('metrics/alfa_match_explainers.csv')

explainers = json_data['matches']
feature_importance = json_data['feature_importance']
statistics = json_data['statistics']

# ============================================================================
# 1. FEATURE IMPORTANCE VISUALIZATION
# ============================================================================
print("STEP 1: Creating Feature Importance Chart")
print("-" * 80)

fig, ax = plt.subplots(figsize=(10, 6))

features = [f['feature'] for f in feature_importance]
importances = [f['normalized_importance'] for f in feature_importance]
colors = ['#2E86AB' if f['feature'] == 'rating_gap' else '#A23B72' for f in feature_importance]

bars = ax.bar(features, importances, color=colors, edgecolor='black', linewidth=1.5)

# Add value labels on bars
for bar, imp in zip(bars, importances):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height,
            f'{imp:.1%}',
            ha='center', va='bottom', fontsize=12, fontweight='bold')

ax.set_ylabel('Normalized Importance', fontsize=12, fontweight='bold')
ax.set_title('Feature Importance in Match Outcome Prediction', fontsize=14, fontweight='bold')
ax.set_ylim(0, 0.6)
ax.grid(axis='y', alpha=0.3, linestyle='--')

plt.tight_layout()
plt.savefig('metrics/visualizations/feature_importance.png', dpi=150, bbox_inches='tight')
print(f"✓ Saved feature importance chart to metrics/visualizations/feature_importance.png\n")
plt.close()

# ============================================================================
# 2. CONTRIBUTION DISTRIBUTIONS
# ============================================================================
print("STEP 2: Creating Contribution Distribution Charts")
print("-" * 80)

fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Rating gap contributions
rating_gaps = csv_data['rating_gap_contribution'].values
ax = axes[0]
ax.hist(rating_gaps, bins=50, color='#2E86AB', edgecolor='black', alpha=0.7)
ax.axvline(np.mean(rating_gaps), color='red', linestyle='--', linewidth=2, label=f'Mean: {np.mean(rating_gaps):.6f}')
ax.set_xlabel('Contribution to Win Probability', fontsize=11, fontweight='bold')
ax.set_ylabel('Number of Matches', fontsize=11, fontweight='bold')
ax.set_title('Rating Gap Contributions', fontsize=12, fontweight='bold')
ax.legend()
ax.grid(axis='y', alpha=0.3)

# Race to contributions
race_to_contribs = csv_data['race_to_contribution'].values
ax = axes[1]
ax.hist(race_to_contribs, bins=50, color='#A23B72', edgecolor='black', alpha=0.7)
ax.axvline(np.mean(race_to_contribs), color='red', linestyle='--', linewidth=2, label=f'Mean: {np.mean(race_to_contribs):.6f}')
ax.set_xlabel('Contribution to Win Probability', fontsize=11, fontweight='bold')
ax.set_ylabel('Number of Matches', fontsize=11, fontweight='bold')
ax.set_title('Race To Contributions', fontsize=12, fontweight='bold')
ax.legend()
ax.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig('metrics/visualizations/contribution_distributions.png', dpi=150, bbox_inches='tight')
print(f"✓ Saved contribution distributions to metrics/visualizations/contribution_distributions.png")

# Statistics
print(f"\n  Rating Gap Contributions:")
print(f"    Mean: {np.mean(rating_gaps):+.8f}, Std: {np.std(rating_gaps):.8f}")
print(f"    Range: [{np.min(rating_gaps):.8f}, {np.max(rating_gaps):.8f}]")
print(f"\n  Race To Contributions:")
print(f"    Mean: {np.mean(race_to_contribs):+.8f}, Std: {np.std(race_to_contribs):.8f}")
print(f"    Range: [{np.min(race_to_contribs):.8f}, {np.max(race_to_contribs):.8f}]\n")

plt.close()

# ============================================================================
# 3. CONFIDENCE DISTRIBUTION
# ============================================================================
print("STEP 3: Creating Confidence Distribution Chart")
print("-" * 80)

confidences = csv_data['confidence'].values

fig, ax = plt.subplots(figsize=(10, 6))

ax.hist(confidences, bins=50, color='#06A77D', edgecolor='black', alpha=0.7)
ax.axvline(np.mean(confidences), color='red', linestyle='--', linewidth=2, 
           label=f'Mean: {np.mean(confidences):.4f}')
ax.axvline(np.median(confidences), color='orange', linestyle='--', linewidth=2, 
           label=f'Median: {np.median(confidences):.4f}')

ax.set_xlabel('Confidence Score', fontsize=12, fontweight='bold')
ax.set_ylabel('Number of Matches', fontsize=12, fontweight='bold')
ax.set_title('Prediction Confidence Distribution', fontsize=14, fontweight='bold')
ax.legend(fontsize=10)
ax.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig('metrics/visualizations/confidence_distribution.png', dpi=150, bbox_inches='tight')
print(f"✓ Saved confidence distribution to metrics/visualizations/confidence_distribution.png")

print(f"\n  Confidence Statistics:")
print(f"    Mean: {np.mean(confidences):.4f}, Median: {np.median(confidences):.4f}")
print(f"    Std: {np.std(confidences):.4f}")
print(f"    P25: {np.percentile(confidences, 25):.4f}, P75: {np.percentile(confidences, 75):.4f}")
print(f"    High confidence (>0.7): {(confidences > 0.7).sum()} matches")
print(f"    Low confidence (<0.3): {(confidences < 0.3).sum()} matches\n")

plt.close()

# ============================================================================
# 4. PREDICTION ACCURACY vs CONFIDENCE
# ============================================================================
print("STEP 4: Creating Accuracy vs Confidence Chart")
print("-" * 80)

fig, ax = plt.subplots(figsize=(10, 6))

correct = csv_data['correct_prediction'].values
pred_probs = csv_data['predicted_win_prob_p1'].values

ax.scatter(pred_probs, correct, alpha=0.3, s=20, color='#2E86AB')

# Add calibration curve
bins = np.linspace(0, 1, 11)
bin_centers = (bins[:-1] + bins[1:]) / 2
bin_accuracy = []
for i in range(len(bins)-1):
    mask = (pred_probs >= bins[i]) & (pred_probs < bins[i+1])
    if mask.sum() > 0:
        bin_accuracy.append(correct[mask].mean())
    else:
        bin_accuracy.append(np.nan)

bin_accuracy = np.array(bin_accuracy)
valid_bins = ~np.isnan(bin_accuracy)
ax.plot(bin_centers[valid_bins], bin_accuracy[valid_bins], 'o-', color='red', 
        linewidth=2, markersize=8, label='Calibration curve')

# Perfect calibration line
ax.plot([0, 1], [0, 1], 'k--', linewidth=1, alpha=0.5, label='Perfect calibration')

ax.set_xlabel('Predicted Win Probability (Player 1)', fontsize=12, fontweight='bold')
ax.set_ylabel('Actual Win Rate', fontsize=12, fontweight='bold')
ax.set_title('Prediction Calibration: Model Confidence vs Accuracy', fontsize=14, fontweight='bold')
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.legend(fontsize=10)
ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig('metrics/visualizations/calibration_curve.png', dpi=150, bbox_inches='tight')
print(f"✓ Saved calibration curve to metrics/visualizations/calibration_curve.png\n")
plt.close()

# ============================================================================
# 5. FEATURE WEIGHT DISTRIBUTIONS
# ============================================================================
print("STEP 5: Creating Feature Weight Distribution Charts")
print("-" * 80)

fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Rating gap weights
rating_weights = csv_data['rating_gap_weight'].values
ax = axes[0]
ax.hist(rating_weights, bins=50, color='#2E86AB', edgecolor='black', alpha=0.7)
ax.axvline(np.mean(rating_weights), color='red', linestyle='--', linewidth=2, 
           label=f'Mean: {np.mean(rating_weights):.3f}')
ax.set_xlabel('Feature Weight (Importance)', fontsize=11, fontweight='bold')
ax.set_ylabel('Number of Matches', fontsize=11, fontweight='bold')
ax.set_title('Rating Gap Feature Weights', fontsize=12, fontweight='bold')
ax.set_xlim(0, 1)
ax.legend()
ax.grid(axis='y', alpha=0.3)

# Race to weights
race_weights = csv_data['race_to_weight'].values
ax = axes[1]
ax.hist(race_weights, bins=50, color='#A23B72', edgecolor='black', alpha=0.7)
ax.axvline(np.mean(race_weights), color='red', linestyle='--', linewidth=2, 
           label=f'Mean: {np.mean(race_weights):.3f}')
ax.set_xlabel('Feature Weight (Importance)', fontsize=11, fontweight='bold')
ax.set_ylabel('Number of Matches', fontsize=11, fontweight='bold')
ax.set_title('Race To Feature Weights', fontsize=12, fontweight='bold')
ax.set_xlim(0, 1)
ax.legend()
ax.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig('metrics/visualizations/feature_weights.png', dpi=150, bbox_inches='tight')
print(f"✓ Saved feature weight distributions to metrics/visualizations/feature_weights.png")

print(f"\n  Rating Gap Weights:")
print(f"    Mean: {np.mean(rating_weights):.4f}, Std: {np.std(rating_weights):.4f}")
print(f"\n  Race To Weights:")
print(f"    Mean: {np.mean(race_weights):.4f}, Std: {np.std(race_weights):.4f}\n")

plt.close()

# ============================================================================
# 6. CREATE SUMMARY REPORT
# ============================================================================
print("STEP 6: Creating Summary Report")
print("-" * 80)

# Sample best and worst calibrated matches
best_calibrated = csv_data.nlargest(5, 'confidence')
worst_calibrated = csv_data.nsmallest(5, 'confidence')
misclassified = csv_data[~csv_data['correct_prediction']].nlargest(5, 'confidence')

report = f"""
{'=' * 80}
MATCH EXPLAINABILITY REPORT
{'=' * 80}

OVERVIEW
{'=' * 80}

Total Matches Analyzed: {len(csv_data):,}
Test Set Accuracy: {statistics['accuracy']:.2%}
Correct Predictions: {(csv_data['correct_prediction']).sum():,} / {len(csv_data):,}

FEATURE IMPORTANCE RANKING
{'=' * 80}

"""

for i, feat in enumerate(feature_importance, 1):
    report += f"\n{i}. {feat['feature'].upper()}\n"
    report += f"   Normalized Importance: {feat['normalized_importance']:.2%}\n"
    report += f"   Average Contribution: {feat['average_contribution']:+.8f}\n"
    report += f"   Coefficient: {feat['coefficient']:+.12f}\n"
    report += f"   Dominant Direction: {feat['direction_dominant'].replace('_', ' ').title()}\n"

report += f"""

KEY INSIGHTS
{'=' * 80}

1. FEATURE CONTRIBUTIONS
   • Rating Gap: 50.37% importance
     - Positive coefficient (0.000335): Higher P1 rating → Higher P1 win probability
     - Average contribution: +0.012568
   
   • Race To: 49.63% importance
     - Negative coefficient (-0.006203): Longer race → Slightly lower any player's win prob
     - Average contribution: +0.012382

2. PREDICTION CONFIDENCE
   • Mean Confidence: {statistics['mean_confidence']:.4f}
   • Median Confidence: {statistics['median_confidence']:.4f}
   • Standard Deviation: {statistics['confidence_std']:.4f}
   
   Note: Very low confidence scores indicate the model makes nearly 50/50 predictions
   for most matches, suggesting outcome is highly dependent on execution/skill variance.

3. MODEL CALIBRATION
   • Overall Accuracy: {statistics['accuracy']:.2%}
   • High Confidence Matches (>0.7): {(csv_data['confidence'] > 0.7).sum()}
   • Low Confidence Matches (<0.3): {(csv_data['confidence'] < 0.3).sum()}
   • Medium Confidence Matches: {((csv_data['confidence'] >= 0.3) & (csv_data['confidence'] <= 0.7)).sum()}

BEST-CALIBRATED MATCHES (Top predictions by confidence)
{'=' * 80}

"""

for idx, (i, row) in enumerate(best_calibrated.iterrows(), 1):
    report += f"\n{idx}. {row['match_id']}\n"
    report += f"   Players: {row['player_1_name']} vs {row['player_2_name']}\n"
    report += f"   Prediction: P1 Win {row['predicted_win_prob_p1']:.1%} (Confidence: {row['confidence']:.2%})\n"
    report += f"   Actual: {'Player 1' if row['actual_winner'] == 'player_1' else 'Player 2'} won\n"
    report += f"   Correct: {'✓' if row['correct_prediction'] else '✗'}\n"
    report += f"   Rating Gap: {row['rating_gap']:+.1f}\n"
    report += f"   Race To: {int(row['race_to'])}\n"

report += f"""

WORST-CALIBRATED MATCHES (Near 50/50 predictions)
{'=' * 80}

"""

for idx, (i, row) in enumerate(worst_calibrated.iterrows(), 1):
    report += f"\n{idx}. {row['match_id']}\n"
    report += f"   Players: {row['player_1_name']} vs {row['player_2_name']}\n"
    report += f"   Prediction: P1 Win {row['predicted_win_prob_p1']:.1%} (Confidence: {row['confidence']:.2%})\n"
    report += f"   Actual: {'Player 1' if row['actual_winner'] == 'player_1' else 'Player 2'} won\n"
    report += f"   Correct: {'✓' if row['correct_prediction'] else '✗'}\n"
    report += f"   Rating Gap: {row['rating_gap']:+.1f}\n"
    report += f"   Race To: {int(row['race_to'])}\n"

report += f"""

MISCLASSIFIED MATCHES (Most confident errors)
{'=' * 80}

"""

for idx, (i, row) in enumerate(misclassified.iterrows(), 1):
    report += f"\n{idx}. {row['match_id']}\n"
    report += f"   Players: {row['player_1_name']} vs {row['player_2_name']}\n"
    report += f"   Predicted: P1 Win {row['predicted_win_prob_p1']:.1%} (Confidence: {row['confidence']:.2%})\n"
    report += f"   Actual: {'Player 1' if row['actual_winner'] == 'player_1' else 'Player 2'} won [INCORRECT]\n"
    report += f"   Rating Gap: {row['rating_gap']:+.1f}\n"
    report += f"   Race To: {int(row['race_to'])}\n"

report += f"""

DATA INTERPRETATION
{'=' * 80}

What the Explanations Tell Us:

1. RATING GAP (50.37% importance)
   - Shows how much the rating difference between players influences the prediction
   - Positive contribution = favors player 1 (higher rated player)
   - Controls for skill gap known from past performance

2. RACE TO (49.63% importance)
   - Shows how match length affects prediction strength
   - Slight negative effect suggests longer races have marginally lower predictability
   - Longer races may allow for more variance in outcomes (probability of upsets)

3. NEARLY PERFECT SYMMETRY
   - Features contribute almost equally (50-50 split)
   - Suggests both skill gap (rating) and match conditions (race) matter equally
   - Model is not dominated by any single factor

4. LOW CONFIDENCE SCORES
   - Most predictions are barely above 50% confidence
   - Indicates many matches could go either way based on execution
   - Accurate representation of pool's skill-based nature

NEXT STEPS FOR IMPROVEMENT
{'=' * 80}

1. Additional Features to Consider:
   - Match history between players
   - Player streak/form (recent wins/losses)
   - Head-to-head records
   - Table/venue effects
   - Format-specific advantages

2. Model Enhancements:
   - Polynomial features (rating_gap^2, interactions)
   - Adaptive weighting by skill level
   - Non-linear models (random forest, gradient boosting)
   - Separate models for different formats (8-ball, 9-ball, 10-ball)

3. Validation:
   - Time-series cross-validation (using temporal splits)
   - Format-specific performance analysis
   - Venue/location-specific calibration

{'=' * 80}
Report Generated: {pd.Timestamp.now()}
{'=' * 80}
"""

report_path = 'metrics/EXPLAINABILITY_REPORT.md'
with open(report_path, 'w') as f:
    f.write(report)

print(f"✓ Saved comprehensive report to {report_path}\n")

# ============================================================================
# 7. SAMPLE MATCHES TABLE
# ============================================================================
print("STEP 7: Creating Sample Matches Table")
print("-" * 80)

# Create sample table with key matches
sample_matches = pd.concat([
    best_calibrated[['match_id', 'player_1_name', 'player_2_name', 'predicted_win_prob_p1', 
                      'actual_winner', 'correct_prediction', 'confidence', 'rating_gap']],
    worst_calibrated[['match_id', 'player_1_name', 'player_2_name', 'predicted_win_prob_p1', 
                        'actual_winner', 'correct_prediction', 'confidence', 'rating_gap']],
])

sample_html = sample_matches.to_html(index=False, float_format=lambda x: f'{x:.4f}' if x < 1 else f'{x:.0f}')

html_path = 'metrics/sample_matches_table.html'
with open(html_path, 'w') as f:
    f.write(f"""
<html>
<head>
    <title>Sample Match Explanations</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #2E86AB; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <h1>Sample Match Explanations</h1>
    {sample_html}
</body>
</html>
""")

print(f"✓ Saved sample matches table to {html_path}\n")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("VISUALIZATIONS AND REPORT GENERATION COMPLETE!")
print("=" * 80)

print(f"\nGenerated Files:")
print(f"  Visualizations:")
print(f"    • metrics/visualizations/feature_importance.png")
print(f"    • metrics/visualizations/contribution_distributions.png")
print(f"    • metrics/visualizations/confidence_distribution.png")
print(f"    • metrics/visualizations/calibration_curve.png")
print(f"    • metrics/visualizations/feature_weights.png")
print(f"  Reports & Tables:")
print(f"    • metrics/EXPLAINABILITY_REPORT.md")
print(f"    • metrics/sample_matches_table.html")
print(f"    • metrics/alfa_match_explainers.csv (2,400 matches)")
print(f"    • metrics/alfa_match_explainers.json (2,400 matches)")
print(f"    • metrics/feature_importance_stats.json")

print(f"\n" + "=" * 80)
