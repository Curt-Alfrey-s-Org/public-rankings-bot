# Match Explainability Layer Documentation

## Overview

The match explainability system generates per-match factor breakdowns showing what influenced each prediction. For all 2,400 test matches, it computes:

1. **Factor contributions**: How much each feature (rating gap, race to) moved the prediction
2. **Direction**: Whether each factor favored player 1 or player 2
3. **Importance weights**: Relative importance of each factor to the prediction
4. **Confidence scores**: How certain the model is about the prediction
5. **Calibration data**: Actual vs. predicted outcomes for model evaluation

## Generated Files

### 1. Core Explainability Data

#### `metrics/alfa_match_explainers.csv` (593 KB)
**Tabular format for easy analysis in Excel, Pandas, SQL, etc.**

23 columns per match:
- **match_id**: Unique match identifier
- **player_1_name, player_2_name**: Player names
- **date, location_id, table_size, format, race_to**: Match context
- **fargo_rating_p1, fargo_rating_p2**: Player skill ratings
- **rating_gap**: P1 rating - P2 rating (>0 = P1 rated higher)
- **predicted_win_prob_p1, predicted_win_prob_p2**: Model predictions
- **actual_winner**: Who actually won (player_1 or player_2)
- **correct_prediction**: Boolean, was the prediction correct?
- **rating_gap_contribution**: How much rating difference moved prediction (±0.XX)
- **rating_gap_direction**: 'favors_p1' or 'favors_p2'
- **rating_gap_weight**: Importance (0-1, how much this factor mattered)
- **race_to_contribution, race_to_direction, race_to_weight**: Same for race length
- **confidence**: Model confidence (0-1, higher = more certain)
- **note**: Interpretation note

**Example row:**
```
tournament_005_m0079, Taylor King, Ivan Wright, 2024-02-01, boston_classic, 7ft, 8ball, 9,
496.6, 538.8, -42.2, 0.0000, 0.0000, player_1, True,
-0.00353, favors_p2, 0.202, -0.013949, favors_p2, 0.798, 0.002,
"Prediction close to 50/50; match likely decided by execution"
```

#### `metrics/alfa_match_explainers.json` (2.6 MB)
**Complete structured format with all details**

Structure:
```json
{
  "metadata": {
    "generated_at": "2026-02-16T18:17:21.XXX",
    "num_matches": 2400,
    "model_type": "LogisticRegression",
    "features": ["rating_gap", "race_to"]
  },
  "model_parameters": {
    "intercept": 0.074,
    "coefficients": {
      "rating_gap": 0.000335,
      "race_to": -0.00620
    }
  },
  "feature_importance": [
    {
      "feature": "rating_gap",
      "average_contribution": 0.01257,
      "normalized_importance": 0.5037,  // 50.37%
      "rank": 1,
      "direction_dominant": "favors_p1",
      "coefficient": 0.000335
    },
    {
      "feature": "race_to",
      "average_contribution": 0.01238,
      "normalized_importance": 0.4963,  // 49.63%
      "rank": 2,
      "direction_dominant": "favors_p2",
      "coefficient": -0.00620
    }
  ],
  "statistics": {
    "accuracy": 0.5279,
    "mean_confidence": 0.0268,
    "median_confidence": 0.0233,
    "confidence_std": 0.0190
  },
  "matches": [
    {
      "match_id": "tournament_005_m0079",
      "player_1_name": "Taylor King",
      "player_2_name": "Ivan Wright",
      "predicted_win_prob_p1": 0.5010,
      "predicted_win_prob_p2": 0.4990,
      "actual_winner": "player_1",
      "correct_prediction": true,
      "factors": [
        {
          "name": "rating_gap",
          "feature_value": -42.2,
          "contribution": -0.00353,  // -0.35% to P1 win prob
          "direction": "favors_p2",
          "weight": 0.202  // 20.2% importance for this match
        },
        {
          "name": "race_to",
          "feature_value": 9,
          "contribution": -0.01395,  // -1.40% to P1 win prob
          "direction": "favors_p2",
          "weight": 0.798  // 79.8% importance for this match
        }
      ],
      "confidence": 0.002,
      "note": "Prediction close to 50/50; match likely decided by execution"
    }
    // ... 2399 more matches
  ]
}
```

### 2. Statistical Summaries

#### `metrics/feature_importance_stats.json`
Summary statistics about feature contributions across all matches:

```json
{
  "feature_ranking": [...],  // Ranked importance
  "per_match_distribution": {
    "rating_gap": {
      "mean_contribution": 0.01257,
      "std_contribution": 0.01542,
      "min_contribution": -0.03672,
      "max_contribution": 0.03625,
      "mean_weight": 0.4375,
      "std_weight": 0.1995
    },
    "race_to": {
      "mean_contribution": 0.01238,
      "std_contribution": 0.00126,
      "min_contribution": -0.01395,
      "max_contribution": -0.01085,
      "mean_weight": 0.5625,
      "std_weight": 0.1995
    }
  },
  "prediction_calibration": {
    "accuracy": 0.5279,
    "correct_predictions": 1267,
    "total_predictions": 2400,
    "mean_predicted_prob": 0.5054,
    "std_predicted_prob": 0.0134
  },
  "confidence": {
    "mean": 0.0268,
    "median": 0.0233,
    "std": 0.0190,
    "min": 0.0000,
    "max": 0.0880,
    "p25": 0.0108,
    "p75": 0.0397
  }
}
```

### 3. Visualizations

#### `metrics/visualizations/feature_importance.png`
Bar chart showing normalized importance:
- Rating gap: 50.37%
- Race to: 49.63%

**Key insight**: Features contribute almost equally, suggesting both skill gap and match conditions matter.

#### `metrics/visualizations/contribution_distributions.png`
Histograms showing how contributions vary across matches:
- **Rating gap**: Ranges from -0.0367 to +0.0362 (symmetric around 0)
- **Race to**: Ranges from -0.0140 to -0.0109 (mostly negative)

#### `metrics/visualizations/confidence_distribution.png`
Distribution of model confidence:
- Mean confidence: 0.0268 (very low!)
- Range: 0.00 to 0.088
- **Almost all matches are ~50/50 predictions**

This is expected for pool/billiards: skill differences matter, but execution variance is high.

#### `metrics/visualizations/calibration_curve.png`
How well-calibrated predictions are:
- X-axis: Model's predicted win probability for Player 1
- Y-axis: Actual win rate for given probabilities
- Shows if model is overconfident, underconfident, or well-calibrated

#### `metrics/visualizations/feature_weights.png`
Distribution of per-match feature importance:
- **Rating gap weights**: Mean 0.4375, ranges 0.0008 to 0.7697
- **Race to weights**: Mean 0.5625, ranges 0.2303 to 0.9992

In some matches, race length is 80% of the prediction; in others, rating gap dominates.

### 4. Human-Readable Reports

#### `metrics/EXPLAINABILITY_REPORT.md`
Comprehensive markdown report including:

**Section 1: Overview**
- Total matches analyzed: 2,400
- Test set accuracy: 52.79%
- Correct predictions: 1,267 / 2,400

**Section 2: Feature Rankings**
```
1. RATING GAP (50.37%)
   - Positive coefficient: Higher P1 rating → Higher P1 win probability
   - Avg contribution: +0.01257
   - Coefficient: +0.000335

2. RACE TO (49.63%)
   - Negative coefficient: Longer race → Slightly lower win probability
   - Avg contribution: +0.01238
   - Coefficient: -0.00620
```

**Section 3: Key Insights**
- Feature contributions are nearly equal (50-50 split)
- Very low confidence scores indicate most matches could go either way
- Model accurately reflects that billiards outcomes depend heavily on execution

**Section 4: Best-Calibrated Matches (Top 5)**
Sample high-confidence correct predictions

**Section 5: Worst-Calibrated Matches (Bottom 5)**
Sample near-50/50 predictions

**Section 6: Misclassified Matches (Top 5 errors)**
Most confident predictions that were wrong

**Section 7: Improvement Recommendations**
- Additional features: head-to-head history, recent form, venue effects
- Model enhancements: polynomial features, non-linear models, format-specific models

#### `metrics/sample_matches_table.html`
Interactive HTML table of sample matches for easy viewing in browsers.

## How to Interpret Explainability Data

### Understanding Contributions

A contribution shows how much a feature moved the prediction probability:

```
Rating gap contribution: +0.08
→ Rating difference moved P1 win probability up by 8 percentage points

Race to contribution: -0.02
→ Match length moved P1 win probability down by 2 percentage points
```

**Key calculation:**
```
Baseline prediction (no features): 51.85%
After rating_gap: Changed by -0.35%
After race_to: Changed by -1.40%
Final prediction: 50.10%

The sum of contributions ≈ (final prediction - baseline)
```

### Understanding Directions

Direction shows which player the factor favors:

```
rating_gap_contribution: +0.08, direction: "favors_p1"
→ Rating gap moved probability in favor of Player 1

race_to_contribution: -0.02, direction: "favors_p2"
→ Match length moved probability in favor of Player 2
```

### Understanding Weights

Weight shows how important the factor was for that specific match (0-1):

```
rating_gap_weight: 0.80
→ For this match, rating gap was 80% of the prediction strength
→ Race to was 20% of the prediction strength
→ Total: 80% + 20% = 100%
```

Weights vary by match:
- Matches with huge rating gaps: rating_gap weight ≈ 0.7-0.8, race_to weight ≈ 0.2-0.3
- Matches with similar ratings: weight distribution is mixed
- **Average**: rating_gap = 43.75%, race_to = 56.25%

### Understanding Confidence

Confidence indicates how far from 50% the prediction is:

```
predicted_win_prob_p1: 0.501
confidence: 0.002 (0.2%)
→ Nearly 50/50; very uncertain

predicted_win_prob_p1: 0.541
confidence: 0.082 (8.2%)
→ Somewhat confident P1 will win (but still not very certain)
```

**Distribution across all 2,400 matches:**
- Mean confidence: 2.68%
- Max confidence: 8.80%
- **No matches have >0.7 (70%) confidence**

This reflects the reality of billiards: luck and execution matter as much as skill.

## Usage Examples

### 1. Find most impactful features for a specific match

```python
import json

with open('metrics/alfa_match_explainers.json') as f:
    data = json.load(f)

match = data['matches'][0]
print(f"Match: {match['match_id']}")
print(f"Prediction: P1 wins {match['predicted_win_prob_p1']:.1%}")
print(f"Confidence: {match['confidence']:.1%}")
print("\nFactor breakdown:")
for factor in match['factors']:
    print(f"  {factor['name']:15s}: {factor['contribution']:+.4f} ({factor['weight']:.1%} weight)")
```

### 2. Find matches rating gap had the most impact

```python
import pandas as pd

df = pd.read_csv('metrics/alfa_match_explainers.csv')
df['rating_gap_impact'] = abs(df['rating_gap_contribution'])
top_rating_impact = df.nlargest(10, 'rating_gap_impact')
print(top_rating_impact[['match_id', 'player_1_name', 'player_2_name', 
                          'rating_gap', 'rating_gap_contribution', 'rating_gap_weight']])
```

### 3. Analyze prediction accuracy by confidence level

```python
import pandas as pd

df = pd.read_csv('metrics/alfa_match_explainers.csv')

# Bin confidence into quartiles
df['confidence_bin'] = pd.cut(df['confidence'], bins=4)

for bin_range in df['confidence_bin'].unique():
    mask = df['confidence_bin'] == bin_range
    accuracy = df[mask]['correct_prediction'].mean()
    count = mask.sum()
    print(f"{bin_range}: {accuracy:.1%} accuracy ({count} matches)")
```

### 4. Export explanations for a specific player

```python
import pandas as pd

df = pd.read_csv('metrics/alfa_match_explainers.csv')
player_matches = df[(df['player_1_name'] == 'Taylor King') | (df['player_2_name'] == 'Taylor King')]
player_matches.to_csv('taylor_king_explanations.csv', index=False)
```

### 5. Compare predicted vs actual outcomes

```python
import pandas as pd

df = pd.read_csv('metrics/alfa_match_explainers.csv')

# When did model predict P1 wins but P2 won?
errors = df[
    (df['predicted_win_prob_p1'] > 0.5) & 
    (df['actual_winner'] == 'player_2')
]
print(f"Model predicted P1 but P2 won: {len(errors)} times")
print(f"These matches had mean rating gap: {errors['rating_gap'].mean():.1f}")
```

## Model Details

### Logistic Regression Formula

$$P(\text{Player 1 Wins}) = \frac{1}{1 + e^{-(\beta_0 + \beta_1 \cdot \text{rating\_gap} + \beta_2 \cdot \text{race\_to})}}$$

Where:
- $\beta_0 = 0.0740$ (intercept/baseline)
- $\beta_1 = 0.000335$ (rating_gap coefficient)
- $\beta_2 = -0.00620$ (race_to coefficient)

### Interpretation

**Rating gap coefficient (+0.000335):**
- For every 1-point increase in (P1 rating - P2 rating)
- P1 win probability increases by ~0.0335 percentage points (0.0335%)
- E.g., 100-point rating advantage → +3.35% win probability

**Race to coefficient (-0.00620):**
- For every 1-increase in race length
- P1 win probability decreases by 0.62 percentage points
- E.g., race to 11 vs race to 9 (2-game difference) → -1.24% to P1
- Suggests longer matches have more execution variance

### Training vs Test Performance

| Metric | Training (7,200) | Validation (2,400) | Test (2,400) |
|--------|------------------|-------------------|-------------|
| Accuracy | 51.26% | 51.13% | 52.79% |
| Brier Score | 0.2497 | 0.2500 | ~0.25 |
| Log Loss | 0.6926 | 0.6931 | ~0.69 |

**Findings:**
- No overfitting: train ≈ val ≈ test accuracy
- Model performs slightly better on test (52.79% vs 51.13%) - likely random variation
- ~52% accuracy suggests modest skill capture with high execution variance

## Limitations & Caveats

1. **Only 2 features**: Model only uses rating gap and race length. Missing:
   - Head-to-head history
   - Recent form/streak
   - Venue effects
   - Format-specific advantages
   - Time-of-day/fatigue factors

2. **Static Fargo ratings**: Ratings from fixed time point, don't change within test set

3. **Nearly 50/50 predictions**: Most predictions are barely above chance, reflecting that skill differences are small and execution variance is high

4. **No temporal features**: Model doesn't know date; can't learn seasonal patterns

5. **Past data only**: Relies on historical matches; may not predict future changes in player skill

## Recommendations

### For Improved Predictions

1. **Add temporal information**:
   - Recent win rate (last 10 games)
   - Rating change (improving vs declining)
   - Venue expertise (how often plays there)

2. **Non-linear models**:
   - Random Forest (capture complex relationships)
   - Gradient Boosting (iterative improvement)
   - Neural Networks (learn feature interactions)

3. **Format-specific models**:
   - Separate model for 8-ball, 9-ball, 10-ball
   - Different strategies matter per format

4. **Match context**:
   - Tournament bracket position
   - Tiebreaker rules
   - Opponent difficulty (strength of other competitors)

### For Production Deployment

1. **Monitor calibration**: Track actual vs predicted outcomes over time

2. **Update ratings periodically**: Fargo ratings should be refreshed monthly

3. **Explainability API**: Serve explanations from these pre-computed results:
   ```
   GET /api/match/{match_id}/explanation
   → Returns factors, confidence, note
   ```

4. **Threshold-based alerts**: Flag >0.8 confidence predictions for review

5. **User-facing explanations**:
   ```
   "Taylor King (496) vs Ivan Wright (539)
    Model predicts 50.1% chance for Taylor
    
    Rating gap: -42 points favors Ivan slightly (-0.35%)
    Race to 9: Standard length, minimal impact (-1.40%)
    
    This is essentially a coin flip. Ivan has slight edge due to rating.
    Actual outcome will depend heavily on execution and luck."
   ```

## File Locations Summary

```
metrics/
├── alfa_match_explainers.csv           (2,400 rows, CSV format)
├── alfa_match_explainers.json          (2,400 matches, full details)
├── feature_importance_stats.json       (summary statistics)
├── EXPLAINABILITY_REPORT.md            (human-readable report)
├── sample_matches_table.html           (interactive HTML table)
└── visualizations/
    ├── feature_importance.png          (bar chart)
    ├── contribution_distributions.png  (histograms)
    ├── confidence_distribution.png     (histogram)
    ├── calibration_curve.png           (line plot)
    └── feature_weights.png             (histograms)
```

## Quick Start

1. **For quick analysis**: Use `metrics/alfa_match_explainers.csv` in Excel/Pandas
2. **For visualizations**: Open files in `metrics/visualizations/`
3. **For detailed explanations**: Read `metrics/EXPLAINABILITY_REPORT.md`
4. **For programmatic access**: Load `metrics/alfa_match_explainers.json` in Python/JavaScript
5. **For statistics**: Reference `metrics/feature_importance_stats.json`

---

Generated: February 16, 2026  
Model: Logistic Regression (Fargo-based match prediction)  
Dataset: 2,400 test matches from billiards tournaments
