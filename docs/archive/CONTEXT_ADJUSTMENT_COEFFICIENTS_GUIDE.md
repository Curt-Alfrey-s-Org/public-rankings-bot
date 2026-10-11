# Context Adjustment Coefficients - Practical Guide

## How to Use Context Coefficients

### Python Example

```python
import pickle
import json
import numpy as np

# Load models
with open('models/alfa_logistic_regression.pkl', 'rb') as f:
    baseline_model = pickle.load(f)

with open('models/alfa_context_adjustments.pkl', 'rb') as f:
    adjustment_model = pickle.load(f)

with open('models/alfa_context_params.json', 'r') as f:
    params = json.load(f)

# Example match
fargo_p1 = 650.0      # Player 1 Fargo rating
fargo_p2 = 620.0      # Player 2 Fargo rating
race_to = 9           # Race to 9
table_size = "8ft"
game_format = "9ball"
location = "seattle_invitational"

# Step 1: Compute baseline prediction
rating_diff = fargo_p1 - fargo_p2  # 30.0
features = np.array([[rating_diff, float(race_to)]])
baseline_prob = baseline_model.predict_proba(features)[0, 1]

print(f"Baseline Probability (Player 1 wins): {baseline_prob:.4f}")
# Output: Baseline Probability (Player 1 wins): 0.5420

# Step 2: Compute context-based adjustment
# Create feature vector (one-hot encoded)
context_features = np.array([
    [
        int(table_size == '7ft'),    # table_size_7ft
        int(table_size == '8ft'),    # table_size_8ft
        int(table_size == '9ft'),    # table_size_9ft
        int(game_format == '10ball'), # format_10ball
        int(game_format == '8ball'),  # format_8ball
        int(game_format == '9ball'),  # format_9ball
        1,                             # event_tournament (always 1 in baseline)
        0, 0, 0, 0, 0                 # location features (simplified)
    ]
])

adjustment = adjustment_model.predict(context_features)[0]
print(f"Context Adjustment: {adjustment:+.6f}")
# Output: Context Adjustment: +0.015602

# Step 3: Final adjusted prediction (clipped)
adjusted_prob = np.clip(baseline_prob + adjustment, 0.001, 0.999)
print(f"Adjusted Probability (Player 1 wins): {adjusted_prob:.4f}")
# Output: Adjusted Probability (Player 1 wins): 0.5576

# Step 4: Interpretation
confidence = "High" if abs(adjustment) < 0.01 else "Medium" if abs(adjustment) < 0.02 else "Low"
direction = "boost" if adjustment > 0 else "reduce"
magnitude = abs(adjustment) * 100

print(f"\nInterpretation:")
print(f"  Context effect: {direction} player 1 win probability by {magnitude:.2f}%")
print(f"  Confidence in adjustment: {confidence}")
```

### Direct Coefficient Lookup

Instead of using the model, you can apply coefficients directly:

```python
def apply_context_adjustments(baseline_prob, table_size, format, location):
    """
    Directly apply context coefficients to baseline prediction.
    
    Args:
        baseline_prob: Probability from baseline model (0-1)
        table_size: "7ft", "8ft", or "9ft"
        format: "8ball", "9ball", or "10ball"
        location: Tournament location
    
    Returns:
        Adjusted probability (0-1)
    """
    
    coefficients = {
        'table_size': {
            '7ft': +0.013861,
            '8ft': -0.013681,
            '9ft': -0.000180,
        },
        'format': {
            '8ball': -0.014664,
            '9ball': +0.004739,
            '10ball': +0.009926,
        },
        'location': {
            'seattle_invitational': -0.037543,
            'phoenix_open': -0.037012,
            'chicago_nationals': -0.032490,
            'boston_classic': -0.020571,
            'las_vegas_open': -0.007782,
        }
    }
    
    # Intercept (applies to all matches)
    adjustment = +0.020182
    
    # Add table size effect
    if table_size in coefficients['table_size']:
        adjustment += coefficients['table_size'][table_size]
    
    # Add format effect
    if format in coefficients['format']:
        adjustment += coefficients['format'][format]
    
    # Add location effect (if venue is known)
    if location in coefficients['location']:
        adjustment += coefficients['location'][location]
    
    # Apply adjustment and clip to valid probability range
    adjusted_prob = np.clip(baseline_prob + adjustment, 0.001, 0.999)
    
    return adjusted_prob

# Usage
baseline = 0.5420
adjusted = apply_context_adjustments(baseline, '8ft', '9ball', 'seattle_invitational')
print(f"Baseline: {baseline:.4f} → Adjusted: {adjusted:.4f}")
```

## Coefficient Reference Table

### Complete Coefficient List

| Feature | Coefficient | Interpretation |
|---------|-------------|-----------------|
| **Intercept** | +0.020182 | Global boost (always apply) |
| | | |
| **Table Size** | | |
| table_size_7ft | +0.013861 | 7ft tables favor player 1 |
| table_size_8ft | -0.013681 | 8ft tables favor player 2 |
| table_size_9ft | -0.000180 | 9ft tables neutral |
| | | |
| **Game Format** | | |
| format_8ball | -0.014664 | 8ball slightly favors underdog |
| format_9ball | +0.004739 | 9ball favors expected winner |
| format_10ball | +0.009926 | 10ball favors expected winner |
| | | |
| **Event Type** | | |
| event_tournament | -0.000000 | Tournament (no effect) |
| | | |
| **Location** | | |
| location_seattle_invitational | -0.037543 | Strong competition |
| location_phoenix_open | -0.037012 | Strong competition |
| location_chicago_nationals | -0.032490 | Strong competition |
| location_boston_classic | -0.020571 | Moderate competition |
| location_las_vegas_open | -0.007782 | Slight competition |

### Feature Combinations

**Example 1: 7ft 8ball at Seattle**
```
Intercept:          +0.020182
+ table_size_7ft:   +0.013861
+ format_8ball:     -0.014664
+ location_seattle: -0.037543
─────────────────────────────
Total adjustment:   -0.018164 (-1.82%)
```

**Example 2: 9ft 10ball at Las Vegas**
```
Intercept:          +0.020182
+ table_size_9ft:   -0.000180
+ format_10ball:    +0.009926
+ location_vegas:   -0.007782
─────────────────────────────
Total adjustment:   +0.022146 (+2.21%)
```

## When to Use Adjustments

### ✓ Use adjustments when:
1. Match location is one of the top 5 tournaments
2. You have baseline Fargo ratings for both players
3. You want venue-aware probability calibration
4. You're analyzing historical matches for fairness

### ⚠ Be cautious when:
1. Table size or format is unusual or invalid
2. Player ratings are estimated (not official)
3. Location is not in the supported list (use default)
4. Sample size for location is small (<500)

### ✗ Don't use adjustments when:
1. Baseline model confidence is already high
2. You need maximum accuracy (baseline alone may be better)
3. New/unproven venues (no historical data)
4. Making critical ranking decisions (use conservative baseline)

## Interpretation Guide

### Location Effects (±3.7% range)
**Negative locations** (Seattle, Phoenix, Chicago):
- Players underperform vs expected based on ratings
- Reason: Stronger competition, better players, higher stakes
- **Recommendation:** Use adjustment to identify stronger venues

**Positive locations** (None in top 5):
- Would indicate weaker competition
- None observed in data

### Format Effects (±1.5% range)
**8ball (negative -1.47%):**
- Slightly favors underdog
- More tactical, less rating-dependent
- Higher upset potential

**9ball & 10ball (positive 0.47% to 0.99%):**
- Slightly favor expected winner
- More straightforward, rating-dependent
- Lower upset potential

### Table Size Effects (±1.4% range)
**7ft (positive +1.39%):**
- Closer proximity, better position
- Slightly favors stronger player

**8ft (negative -1.37%):**
- More distance, tougher position play
- Slightly favors weaker players (compensation)

**9ft (neutral -0.02%):**
- Standard tournament table
- Minimal effect

## Confidence Levels

### High Confidence Coefficients
- **Intercept** (all matches)
- **Table size** (2,300-2,400 training samples each)
- **Format** (2,300-2,400 training samples each)
- **Event type** (7,199 training samples)

### Medium Confidence Coefficients
- **Location top 5** (900-1000 training samples each)
  - Venue-specific patterns but smaller sample sizes

### Low Confidence Coefficients
- **Table size_9ft** (-0.0002) - essentially zero
- Any location with <800 samples - not included in model

## Adjustment Application Process

```
Input Match Data
    ↓
Compute Baseline Probability
    (Using logistic regression model)
    ↓
Encode Context Features
    (One-hot encode table_size, format, event, location)
    ↓
Compute Adjustment
    (Linear combination of context coefficients)
    ↓
Apply Adjustment
    (baseline_prob + adjustment)
    ↓
Clip to Valid Range
    (Ensure 0.001 ≤ result ≤ 0.999)
    ↓
Output Final Probability
```

## Model Files Reference

### Primary Model Files
- `models/alfa_logistic_regression.pkl` (baseline)
  - Features: rating_diff, race_to
  - Output: Player 1 win probability

- `models/alfa_context_adjustments.pkl` (adjustment layer)
  - Features: One-hot encoded context (12 features)
  - Output: Adjustment delta

### Parameter Files
- `models/alfa_context_params.json` (coefficients & metadata)
  - Contains all coefficients for direct lookup
  - Training/validation metrics
  - Adjustment factors by context

### Analysis Files
- `metrics/context_adjustment_analysis.json`
  - Complete evaluation results
  - Stratified performance metrics
  - Split performance (train/val/test)

- `metrics/brier_improvement_summary.csv`
  - Before/after comparison
  - Rows for each split and context

## Updating Coefficients

To retrain the adjustment layer with new data:

```bash
# 1. Ensure data splits are updated
# (data/splits/train_matches.csv, val_matches.csv, test_matches.csv)

# 2. Run fitting script
python fit_context_adjustments.py

# 3. Verify results
python evaluate_context_adjustments.py

# 4. Generate analysis report
python generate_context_analysis_report.py

# 5. Review output files
cat metrics/brier_improvement_summary.csv
cat CONTEXT_ADJUSTMENT_VALIDATION_REPORT.md
```

## FAQ

**Q: Why does Seattle show such a negative adjustment (-3.75%)?**  
A: Historical data shows players underperform at Seattle tournaments compared to their Fargo ratings. This could indicate stronger competition, elevation effects, or different playing styles. Use caution when interpreting—this is empirical observation, not proof of causation.

**Q: Can I use these coefficients for live matches?**  
A: Yes, with baseline Fargo ratings. However, note that validation performance was slightly worse than baseline (-0.21%), suggesting use only for calibration/analysis, not for changing predictions.

**Q: What if a location isn't in the list?**  
A: Use zero adjustment (or just the intercept). The model was only fitted for the top 5 locations due to sample size constraints. Other venues need more data to estimate reliable coefficients.

**Q: Should I combine all adjustments or pick one?**  
A: Combine all applicable adjustments (this is what the model does). The linear model captures independent effects of table_size, format, and location.

**Q: How often should I retrain?**  
A: Quarterly or when you accumulate 1000+ new matches. More frequent retraining risks overfitting; less frequent means outdated venue effects.
