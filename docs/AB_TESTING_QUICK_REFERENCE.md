# A/B Testing Framework — Quick Reference

## Location
All A/B test outputs are in the Rankings-Bot project:
```
/home/ansible/rankings-bot/Rankings-Bot/
├── ab_test_comprehensive.py          ← Main test script
├── models/ab_test_results.json        ← Complete results (JSON)
├── metrics/ab_test_comparison.csv     ← Metrics comparison (CSV)
├── metrics/AB_TEST_REPORT.md          ← Detailed findings (Markdown)
└── metrics/visualizations/
    ├── ab_test_01_brier_score.png     ← Model comparison
    ├── ab_test_02_roc_curves.png      ← ROC curves
    ├── ab_test_03_calibration.png     ← Calibration analysis
    ├── ab_test_04_by_rating_gap.png   ← Stratified by rating diff
    ├── ab_test_05_by_race_length.png  ← Stratified by format
    └── ab_test_06_by_experience.png   ← Stratified by player experience
```

---

## Quick Results

### Best Model: **Logistic Regression**
- **Brier Score:** 0.2492 (11.89% better than Fargo)
- **Calibration RMSE:** 0.0234 (near-perfect)
- **Log Loss:** 0.6915 (11.6% better)
- **Wilcoxon p-value:** 0.000682 ✅ (highly significant)

### Other Models
- **Fargo Baseline:** 0.2828 Brier score (baseline for comparison)
- **Alfa Full System:** 0.2502 Brier score (complex, no clear benefit)

---

## Key Findings

1. ✅ **Machine learning beats Fargo formula** (11–13% improvement)
2. ✅ **Simple beats complex** (Logistic better than Alfa despite Alfa's complexity)
3. ✅ **Statistical tests confirm significance** (p-values < 0.05)
4. ✅ **Consistent across all player segments** (rating gaps, formats, experience levels)
5. ⚠️ **Low AUC-ROC** (0.50–0.54) suggests weak rating-outcome correlation in test data

---

## Viewing Results

### Terminal View (Quick Check)
```bash
cd /home/ansible/rankings-bot/Rankings-Bot
cat metrics/ab_test_comparison.csv
head metrics/AB_TEST_REPORT.md
ls -lh metrics/visualizations/ab_test_*.png
```

### Python View (Detailed Analysis)
```python
import json

with open('models/ab_test_results.json') as f:
    results = json.load(f)

# View model metrics
for model, metrics in results['models'].items():
    print(f"{model}: Brier={metrics['brier_score']:.6f}")

# View statistical tests
for test_type, comparisons in results['statistical_tests'].items():
    print(f"\n{test_type}:")
    for comparison, result in comparisons.items():
        print(f"  {comparison}: p={result['p_value']:.6f}")

# View stratified results
for category, results in results['stratified_analysis'].items():
    print(f"\n{category}:")
    for model_name, metrics in results:
        print(f"  {model_name} - {metrics['segment']}: {metrics['brier_score']:.4f}")
```

### Visualizations
Use any image viewer (Preview on Mac, Photos on Windows, feh/eog on Linux):
```bash
# View all visualizations
open metrics/visualizations/  # macOS
nautilus metrics/visualizations/  # Ubuntu
explorer metrics/visualizations/  # Windows (PowerShell)
```

---

## Running Fresh Tests

To re-run the A/B testing framework:
```bash
cd /home/ansible/rankings-bot/Rankings-Bot
source .venv/bin/activate
python3 ab_test_comprehensive.py

# Or with explicit logging
python3 ab_test_comprehensive.py 2>&1 | tee ab_test_run.log
```

**Runtime:** ~30–45 seconds (includes data load, model inference, metrics, statistical tests, visualization generation)

---

## Interpreting Metrics

| Metric | Range | Better | Interpretation |
|--------|-------|--------|-----------------|
| **Brier Score** | [0, 1] | Lower | Calibration error (predicted vs actual probability) |
| **Accuracy** | [0, 1] | Higher | % correct predictions (threshold 0.5) |
| **Log Loss** | [0, ∞) | Lower | Cross-entropy; penalizes confident wrong predictions |
| **AUC-ROC** | [0, 1] | Higher | Ranking quality (0.5=random, 1.0=perfect) |
| **Calibration RMSE** | [0, ∞) | Lower | Deviation of predicted from actual in bins |
| **Precision** | [0, 1] | Higher | True positives / all positive predictions |
| **Recall** | [0, 1] | Higher | True positives / all actual positives |
| **F1 Score** | [0, 1] | Higher | Harmonic mean of precision & recall |

### Why We Prioritize Brier & Calibration

For a **probabilistic rating system**, calibration matters most:
- Brier score directly measures calibration error
- Accuracy is less relevant (predictions near 0.5 boundary)
- Log loss penalizes overconfident wrong predictions
- Calibration RMSE shows agreement in probability bins

---

## Statistical Tests Explained

### McNemar Test
**Question:** Do two models make significantly different binary predictions?
- **Null hypothesis:** Models make same correct/incorrect predictions
- **p-value < 0.05:** Models differ significantly
- **Interpretation:** Useful for accuracy, timing of errors

### Wilcoxon Signed-Rank Test
**Question:** Are paired differences (Model A vs Model B) significant?
- **Null hypothesis:** Distributions of differences are symmetric about zero
- **p-value < 0.05:** Significant difference detected
- **Interpretation:** Better for continuous metrics (Brier score) on paired data

**For this test:**
- Logistic vs Fargo: p=0.000682 ✅ (highly significant improvement)
- Alfa vs Fargo: p=0.001384 ✅ (significant improvement)
- Logistic vs Alfa: p=0.012035 ✅ (significant, Logistic better)

---

## Troubleshooting

### "ImportError: No module named 'sklearn'"
```bash
source .venv/bin/activate
pip install scikit-learn
```

### "FileNotFoundError: test_matches.csv"
Ensure you're in the project root:
```bash
cd /home/ansible/rankings-bot/Rankings-Bot
```

### "Model expects N features but got M"
Feature mismatch between training and test data. Check:
- `models/alfa_model_params.json` for expected features
- `prepare_features()` method in script for feature computation

---

## Next Steps

Based on results:

1. **Deploy Logistic Regression** to production
   - 2 features: rating_diff, race_to
   - Update player ratings using new predictions
   - Monitor performance vs Fargo baseline

2. **Investigate Low AUC-ROC**
   - Why correlation is weak (~0.54)?
   - Need better features or different rating system?

3. **Future Improvements**
   - Add features if testing validates benefit
   - Ensemble methods (weighted Logistic + Fargo)
   - Player-specific calibration by skill level

---

**For detailed analysis, see:** `docs/AB_TESTING_SUMMARY.md`
