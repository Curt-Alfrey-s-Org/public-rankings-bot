# Logistic Regression Model Results - Match Outcome Prediction

## Executive Summary

Successfully fitted a logistic regression model for predicting match outcomes based on Fargo rating differences and race-to distance. The model achieved **51.1% accuracy** on the validation set, with a Brier score of **0.2500** and log loss of **0.6931**.

---

## Model Overview

### Model Type
- **Algorithm**: Logistic Regression (sklearn.linear_model.LogisticRegression)
- **Features**: 2
  - `rating_diff`: Difference in Fargo ratings (Player 1 - Player 2)
  - `race_to`: Maximum games in the match format (7, 8, or 9)

### Model Equation

```
P(Player 1 Wins) = 1 / (1 + exp(-(0.074049 + 0.000335 * rating_diff + -0.006203 * race_to)))
```

---

## Model Coefficients

| Feature | Coefficient | Interpretation |
|---------|-------------|-----------------|
| `rating_diff` (α) | 0.000335 | +0.335 per 1000 rating point difference |
| `race_to` (β) | -0.006203 | Negative impact as race-to increases |
| **Intercept** | **0.074049** | Base log-odds favoring Player 1 |

### Coefficient Interpretation

- **Positive rating_diff coefficient (0.000335)**: Player 1's winning probability increases when their Fargo rating is higher than Player 2's. Each 100-point rating advantage increases log-odds by 0.0335.

- **Negative race_to coefficient (-0.006203)**: Higher race-to values slightly decrease Player 1's winning probability. Longer matches have marginally different outcome distributions. This suggests standard matches (race-to 7) may slightly favor Player 1.

---

## Training Set Performance

| Metric | Value |
|--------|-------|
| **Number of matches** | 7,200 |
| **Accuracy** | 51.26% |
| **Brier score** | 0.2497 |
| **Log loss** | 0.6926 |

### Outcome Distribution
- Player 1 wins: 3,643 (50.6%)
- Player 2 wins: 3,557 (49.4%)

### Feature Statistics
- `rating_diff`: mean = -1.68, std = 183.72, range = [-443.20, 448.70]
- `race_to`: mean = 7.99, std = 0.81, range = [7, 9]

---

## Validation Set Performance

| Metric | Value |
|--------|-------|
| **Number of matches** | 2,400 |
| **Accuracy** | 51.12% |
| **Brier score** | 0.2500 |
| **Log loss** | 0.6931 |

### Key Observations

1. **Stable generalization**: Validation metrics are nearly identical to training metrics, indicating no overfitting.
2. **Brier score ~0.25**: Slightly higher than the theoretical baseline of 0.20, suggesting room for improvement. The 0.25 value represents calibration error - predictions are roughly neutral with slight bias.
3. **Slightly better than 50%**: The 51.12% accuracy is only marginally better than random guessing (50%), indicating weak predictive power with these features alone.

---

## Feature Importance

| Feature | Coefficient Magnitude | Relative Importance |
|---------|----------------------|---------------------|
| `race_to` | 0.006203 | 95% |
| `rating_diff` | 0.000335 | 5% |

**Note**: `race_to` is more than 18× more important than `rating_diff`, suggesting that match format dominates the prediction over rating differences.

---

## Model Limitations & Insights

1. **Weak predictive power**: The model barely outperforms random (51% vs 50%). Additional features are needed.
   - Suggested additions: Player win history, head-to-head records, skill category, venue effects

2. **Rating diff effect is minimal**: A 200-point rating advantage provides only a ~7% probability increase, suggesting:
   - Fargo ratings may not fully capture match win probability
   - Or, match outcomes are highly variable regardless of rating

3. **Race-to effect**: Longer matches (higher race-to) slightly favor Player 2, which could reflect:
   - Better endurance or consistency of lower-rated players
   - Variance reduction in longer matches

4. **Class balance**: Nearly perfect 50/50 split, no imbalance issues

---

## Files Generated

### Model Files
- **Location**: `models/`
- `alfa_logistic_regression.pkl` - Pickled scikit-learn model (722 bytes)
- `alfa_model_params.json` - Human-readable model parameters (656 bytes)

### Model Parameters JSON Structure
```json
{
  "model_type": "LogisticRegression",
  "features": ["rating_diff", "race_to"],
  "coefficients": {
    "rating_diff": 0.000335,
    "race_to": -0.006203
  },
  "intercept": 0.074049,
  "training_metrics": { ... },
  "validation_metrics": { ... },
  "description": "..."
}
```

---

## Usage Example

### Loading the Model
```python
import pickle

with open('models/alfa_logistic_regression.pkl', 'rb') as f:
    model = pickle.load(f)

# Predict for a match
# Player 1: 750 Fargo rating, Player 2: 700 Fargo rating
# Race-to: 9
rating_diff = 750 - 700  # 50
race_to = 9

prediction = model.predict([[rating_diff, race_to]])  # [1] or [0]
probability = model.predict_proba([[rating_diff, race_to]])[0, 1]  # P(Player 1 wins)
```

### Using Parameters
```python
import json
import numpy as np

with open('models/alfa_model_params.json', 'r') as f:
    params = json.load(f)

# Manual calculation
rating_diff = 50
race_to = 9
intercept = params['intercept']
alpha = params['coefficients']['rating_diff']
beta = params['coefficients']['race_to']

log_odds = intercept + alpha * rating_diff + beta * race_to
probability = 1 / (1 + np.exp(-log_odds))
```

---

## Next Steps for Model Improvement

1. **Feature Engineering**:
   - Player historical win rates
   - Head-to-head win rate
   - Player skill category or tier
   - Venue/table effects
   - Time since last match
   - Player fatigue (multiple matches/day)

2. **Model Alternatives**:
   - Gradient Boosting (XGBoost, LightGBM)
   - Neural networks
   - Ensemble methods

3. **Data Enhancement**:
   - Validate Fargo rating data quality
   - Collect more granular player statistics
   - Track skill progression over time

4. **Baseline Comparison**:
   - Compare to naive Fargo-only model
   - Establish stronger baseline expectations
   - Consider league-wide win % analysis

---

## Technical Notes

- **Training algorithm**: LBFGS solver (100% convergence)
- **Regularization**: Default (L2, C=1.0)
- **Random seed**: 42 (reproducible)
- **Data validation**: Zero missing values in merged datasets
- **Class imbalance**: None (50.6% / 49.4%)

---

**Generated**: 2026-02-16  
**Data source**: `data/splits/train_matches.csv`, `data/splits/val_matches.csv`, `data/alfa_matches.csv`  
**Script**: `fit_logistic_regression.py`
