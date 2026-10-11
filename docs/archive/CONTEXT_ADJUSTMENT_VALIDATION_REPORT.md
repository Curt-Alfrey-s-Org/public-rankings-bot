# Context Adjustment Validation Metrics

**Generated:** 2026-02-16  
**Validation Period:** 2,401 matches (20% hold-out validation set)  
**Test Period:** 2,400 matches (final hold-out test set)

## Executive Summary

| Metric | Result | Status |
|--------|--------|--------|
| Brier Score Improvement (Val) | -0.21% | ⚠ Marginal |
| Brier Score Improvement (Test) | -0.46% | ⚠ Marginal |
| Accuracy Improvement (Val) | +0.74% | ✓ Positive |
| Max Adjustment Magnitude | ±3.8% | ✓ Within ±5% limit |
| Context Variables | 12 features | ✓ Interpretable |
| Generalization (R²) | -0.002 | ⚠ Limited |

## Validation Set Detailed Results

### Overall Performance
```
Baseline Model (Logistic Regression)
  Brier Score:  0.250087
  Accuracy:     0.5060 (50.6%)
  Log Loss:     0.6933
  
Adjusted Model (Baseline + Context Layer)
  Brier Score:  0.250615
  Accuracy:     0.5098 (51.0%)
  Log Loss:     0.6944
  
Performance Delta
  Brier Score:  +0.000528 (-0.21%)  [WORSE]
  Accuracy:     +0.0037 (+0.74%)     [BETTER]
  Log Loss:     +0.001061 (-0.15%)   [WORSE]
```

**Interpretation:** The context adjustment layer slightly degrades Brier score on the validation set, suggesting some overfitting to training residuals. However, it produces a modest accuracy improvement.

### Stratified Validation Results

#### By Table Size
```
7ft (785 samples)
  Baseline Brier: 0.250016
  Adjusted Brier: 0.249445
  Improvement:    +0.23% ✓
  
8ft (804 samples)
  Baseline Brier: 0.250436
  Adjusted Brier: 0.251025
  Improvement:    -0.24% ✗
  
9ft (812 samples)
  Baseline Brier: 0.249809
  Adjusted Brier: 0.251340
  Improvement:    -0.61% ✗
```

**Finding:** 7ft tables benefit from adjustments (+0.23%), while larger tables (8ft, 9ft) see slight degradation. This suggests the adjustment model's 7ft coefficient (+0.0139) is helping but may be fitting noise on larger tables.

#### By Format
```
8ball (scoring: hand loss first to target)
  Baseline Brier: 0.250186
  Adjusted Brier: 0.250126
  Improvement:    +0.02% ✓
  Count: 804
  
9ball (scoring: balls in numerical order)
  Baseline Brier: 0.250240
  Adjusted Brier: 0.250128
  Improvement:    +0.04% ✓
  Count: 819
  
10ball (scoring: balls 1-10 in order)
  Baseline Brier: 0.249829
  Adjusted Brier: 0.251605
  Improvement:    -0.71% ✗
  Count: 778
```

**Finding:** 8ball and 9ball see marginal improvements (<0.05%), while 10ball shows degradation. The format coefficients show 8ball has negative adjustment (-0.0147) which helps slightly, while 10ball's positive adjustment (+0.0099) appears to hurt.

## Test Set Results

### Overall Test Performance
```
Baseline Model
  Brier Score:  0.249011
  Accuracy:     0.5279 (52.8%)
  
Adjusted Model
  Brier Score:  0.250162
  Accuracy:     0.5208 (52.1%)
  
Delta
  Brier Score:  +0.001151 (-0.46%) [WORSE]
  Accuracy:     -0.0071 (-1.35%)    [WORSE]
```

**Critical Finding:** Both metrics degrade on the test set, suggesting the adjustment layer does NOT generalize to unseen data. The context coefficients appear to have learned training-specific patterns.

## Context Coefficient Analysis

### Coefficient Ranking (by absolute magnitude)

1. **seattle_invitational** (-0.037543)
   - 910 training samples
   - Interpretation: Player 1 win probability consistently lower than expected at this venue
   - Confidence: Medium (910 samples)
   - Actionable: Use this coefficient with caution; validate with new data

2. **phoenix_open** (-0.037012)
   - 911 training samples
   - Effect: Very similar to Seattle tournament
   - Confidence: Medium
   - Pattern suggests: Both are challenging venues for lower-ranked players

3. **chicago_nationals** (-0.032490)
   - ~900 samples
   - Effect: Moderate reduction
   - Confidence: Medium
   - Pattern: Regional tournament with strong competition

4. **boston_classic** (-0.020571)
   - 908 samples
   - Effect: Weaker than other tournaments
   - Confidence: Medium
   - Interpretation: More balanced field

5. **table_size_8ft** (-0.013681)
   - 2,411 training samples
   - Effect: Reduce predictions for 8ft tables
   - Confidence: High (largest sample size)
   - Interpretation: 8ft tables are slightly more challenging than ratings predict

### Positive Coefficients (boost predictions)

1. **table_size_7ft** (+0.013861)
   - Boost predictions for 7ft tables
   - Interpretation: Player 1 advantage slightly higher than expected

2. **format_10ball** (+0.009926)
   - Boost for 10-ball games
   - Interpretation: 10-ball format slightly favors expected winner

3. **format_9ball** (+0.004739)
   - Modest boost for 9-ball games

### Zero/Minimal Effects

- **format_8ball**: -0.014664 (negative despite high sample count)
- **event_tournament**: -0.000000 (dummy effect)
- **table_size_9ft**: -0.000180 (negligible)

## Model Fit Statistics

### Training Set
```
Linear Regression (Context Adjustment Model)
  MAE (Mean Absolute Error):    0.4987
  RMSE:                        0.4995
  R² Score:                    0.0019
```

**Interpretation:** The linear model explains only 0.19% of variance in residuals. This suggests context variables have very weak linear relationships with prediction errors.

### Validation Set
```
  MAE:                         0.4998
  RMSE:                        0.5006
  R² Score:                    -0.0022
```

**Interpretation:** Validation R² is negative, indicating the model performs WORSE than simply predicting the mean residual (0). This is a strong signal of poor generalization.

## Constraint Compliance

### Adjustment Magnitude Constraints
- **Limit:** ±5.0% maximum adjustment
- **Observed Maximum:** ±3.75% (location coefficients)
- **Status:** ✓ All within limits
- **Margin:** 1.25 percentage points (25% buffer)

### Prediction Bounds
- **Range:** [0.001, 0.999]
- **Clipping Cases:** ~0.1% of predictions hit bounds (normal)
- **Status:** ✓ Compliant

## Aggregate Effect Distribution

When applied across all validation samples:
```
Adjustment Distribution (2,401 validation samples):
  Mean adjustment:     +0.0185
  Std deviation:       0.0227
  Min adjustment:      -0.0488
  Max adjustment:      +0.0370
  
This means on average, the model boosts predictions by 1.85% with 
variation of ±2.27% across different contexts.
```

## Calibration Analysis

### Calibration Curve Metrics
The model's calibration was measured by comparing predicted probabilities against actual outcomes in probability bins:

```
10-Bin Calibration (Validation Set)
  Expected Calibration Error: 0.0047 (0.47%)
  Maximum error in any bin:   0.0089 (0.89%)
  Perfect calibration score:  0.0000
  
Baseline model:               0.0035
Adjusted model:               0.0042
```

**Finding:** The adjustment layer slightly reduces calibration quality (0.0042 vs 0.0035), suggesting it introduces small miscalibrations despite good intentions.

## Summary of Issues

| Issue | Severity | Evidence |
|-------|----------|----------|
| Poor generalization | 🔴 High | Validation/test Brier worse than baseline (-0.2% to -0.5%) |
| Overfitting | 🔴 High | R² = -0.002 (negative!) on validation |
| Limited feature power | 🟡 Medium | R² = 0.0019 on training suggests weak context signals |
| Calibration degradation | 🟡 Medium | ECE increases from 0.35% to 0.42% |
| Location effect uncertainty | 🟡 Medium | Medium sample sizes (900-1000) may not support ±3.7% adjustments |

## Positive Aspects

| Positive | Evidence |
|----------|----------|
| Safety constraints satisfied | Max ±3.8% < ±5.0% limit |
| Interpretable coefficients | Clear venue and format effects |
| Consistent patterns | Location penalties align with expectations |
| No extreme outliers | Well-behaved adjustment distribution |
| No numerical issues | All predictions remain in [0, 1] range |

## Recommendations for Production Use

### If Using the Adjustment Layer:
1. **Apply selectively:** Restrict to location-based adjustments only
2. **Monitor continuously:** Track A/B comparison against baseline
3. **Set confidence thresholds:** Only apply adjustments where Brier improves
4. **Fallback strategy:** Default to baseline if adjustments don't improve in newer data

### Alternative Approaches:
1. **Retrain context model** with regularization (L1/L2) to prevent overfitting
2. **Use ensemble** combining multiple adjustment strategies
3. **Non-linear context modeling** with trees or neural networks
4. **Focus on high-confidence adjustments** (locations with 1000+ samples)

## Validation Data Quality

### Data Coverage
- All 2,401 validation samples have complete Fargo ratings (100%)
- Context variable coverage:
  - Table size: 100% (3,199 / 2,401 valid)
  - Format: 100% (2,401 / 2,401 valid)
  - Location: 2,361 / 2,401 (98.3%)
  - Event type: 2,401 / 2,401 (100%)

### Potential Issues
- Smaller tournaments (900-1000 samples each) may not have enough data for reliable venue coefficients
- Interactions between contexts (e.g., "7ft + 10ball") not modeled
- Temporal effects (venue improvements over time) not captured
- Skill composition changes at venues not accounted for

## Conclusion

The context adjustment layer demonstrates:

**Strengths:**
- Identifies venue as strongest factor in match outcomes
- Maintains safety constraints
- Provides interpretability

**Weaknesses:**
- Does NOT improve generalization (worse on validation/test)
- Poor feature-target relationship (R² ≈ 0)
- Signs of overfitting to training noise
- Marginal improvements on training don't transfer

**Recommendation:** 
The context adjustment layer in its current form is **NOT recommended for production use**. Improvements on validation (-0.21%) and test (-0.46%) are degradations, indicating the model captures training-specific noise. 

To make this system production-ready, consider regex regularization, non-linear models, or feature engineering improvements (context interactions, temporal effects, player attributes).

---

**Report Status:** ✓ Final  
**Validation Period:** 2,401 samples (Feb 2025 - Feb 2026)  
**Test Period:** 2,400 samples (Feb 2025 - Feb 2026)
