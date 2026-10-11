# Match Explainability - Quick Reference Card

## 📊 What Was Built

Per-match explainability factors for **2,400 billiards tournament matches** showing what influenced each prediction.

**Total deliverables: 18 files | ~3.8 MB data | 5 visualizations | 2 comprehensive guides**

## 🎯 Key Metrics at a Glance

| Metric | Value |
|--------|-------|
| Matches Analyzed | 2,400 |
| Prediction Accuracy | 52.79% |
| Feature 1: Rating Gap | 50.37% importance |
| Feature 2: Race To | 49.63% importance |
| Model Confidence | Mean: 2.68%, Max: 8.80% |
| Data Size | 596 KB (CSV) + 2.6 MB (JSON) |

## 📁 Where to Find Everything

### Main Data Files
```
metrics/alfa_match_explainers.csv          ← Use this for Excel/Pandas
metrics/alfa_match_explainers.json         ← Use this for APIs
metrics/feature_importance_stats.json      ← Summary statistics
```

### Reports & Visualizations
```
metrics/EXPLAINABILITY_REPORT.md           ← Read this first (human-readable)
metrics/sample_matches_table.html          ← Open in web browser
metrics/visualizations/                    ← 5 PNG charts
```

### Documentation & Tools
```
docs/EXPLAINABILITY_COMPLETION_REPORT.md   ← Executive summary
docs/MATCH_EXPLAINABILITY_GUIDE.md         ← Full reference (400+ lines)
analyze_explainability.py                  ← Python analysis tools
```

### Generation Scripts
```
generate_match_explainers.py               ← Generate explanations
generate_explainability_visualizations.py  ← Generate charts & report
```

## 🚀 Get Started in 30 Seconds

### Option 1: Quick View (No Code)
1. Open `metrics/visualizations/feature_importance.png`
2. Read `metrics/EXPLAINABILITY_REPORT.md`
3. View `metrics/sample_matches_table.html` in browser

### Option 2: Excel Analysis
1. Open `metrics/alfa_match_explainers.csv` in Excel
2. Sort/filter by any column
3. Create pivot tables as needed

### Option 3: Python Analysis
```python
python analyze_explainability.py  # See example analysis
```

## 📈 Understanding the Data

### What's in the CSV? (23 columns per match)

Essential columns:
- `match_id` - Unique match identifier
- `player_1_name`, `player_2_name` - Player names
- `rating_gap` - P1 rating - P2 rating
- `predicted_win_prob_p1` - Model's prediction (0-1)
- `actual_winner` - Who actually won
- `correct_prediction` - Was model right? (True/False)
- `rating_gap_contribution` - How much rating moved prediction (-0.04 to +0.04)
- `rating_gap_direction` - "favors_p1" or "favors_p2"
- `rating_gap_weight` - Importance (0-1)
- `race_to_contribution` - How much race length moved prediction
- `race_to_direction` - "favors_p1" or "favors_p2"
- `race_to_weight` - Importance (0-1)
- `confidence` - Model confidence (0-1, very low!)
- `note` - Interpretation

### What does "Contribution" mean?

```
Rating gap: +0.08 = Moved P1 win probability UP by 8 percentage points
Race to: -0.02 = Moved P1 win probability DOWN by 2 percentage points
```

### What does "Weight" mean?

```
Rating gap weight: 0.80 = This factor was 80% important for this match
Race to weight:    0.20 = This factor was 20% important for this match
```

Weights always sum to 1.0.

### What does "Confidence" mean?

```
Confidence: 0.05 (5%) = Prediction is barely above 50-50
Confidence: 0.50 (50%) = Prediction is notably skewed
Confidence: 0.90+ = Very confident prediction

Note: Max in dataset is only 8.8%! Very low confidence everywhere.
```

## 🔍 Common Questions & Answers

**Q: Why are confidence scores so low?**
A: Pool has high execution variance. While skill (rating) matters, luck matters more. Model reflects this reality.

**Q: How do I find matches where rating gap had most impact?**
A: 
```python
df['rating_gap_impact'] = abs(df['rating_gap_contribution']) * df['rating_gap_weight']
top = df.nlargest(10, 'rating_gap_impact')
```

**Q: How do I find my player's matches?**
A:
```python
df[(df['player_1_name'] == 'Name') | (df['player_2_name'] == 'Name')]
```

**Q: How accurate are predictions by format?**
A:
```python
df.groupby('format')['correct_prediction'].mean()
```

## 📊 The 5 Visualizations

1. **feature_importance.png** - Bar chart (50-50 split)
2. **contribution_distributions.png** - How much factors move predictions
3. **confidence_distribution.png** - Why confidence is so low
4. **calibration_curve.png** - Prediction reliability
5. **feature_weights.png** - Per-match importance variation

## 💡 Key Insights

### Finding #1: Balanced Importance
- Rating gap: 50.37% of predictions
- Race to: 49.63% of predictions
- **Both factors matter equally!**

### Finding #2: Low Confidence Everywhere
- No matches have >8.8% confidence
- Mean: 2.68%, Median: 2.33%
- **Reflects execution variance dominates skill**

### Finding #3: Slight Accuracy Gain
- 52.79% accuracy (vs 50% random)
- Modest but better than chance
- **Model captures small skill signal**

### Finding #4: Formula
```
P(P1 Wins) = 1/(1 + exp(-(0.074 + 0.000335*rating_gap - 0.00620*race_to)))

Approx in plain English:
- Each 100-point rating gap → ~3.4% probability shift
- Each 2-game longer race → ~1.2% probability shift
```

## 🎓 For Data Scientists

### Model Architecture
- Type: Logistic Regression
- Features: 2 (rating_diff, race_to)
- Training: 7,200 matches
- Validation: 2,400 matches
- Test: 2,400 matches

### Coefficients
```
β₀ (intercept):  0.0740
β₁ (rating_gap): 0.000335 (positive = higher rated player more likely to win)
β₂ (race_to):   -0.00620 (negative = longer races less predictable)
```

### Performance
- Train accuracy: 51.26%
- Val accuracy: 51.13%
- Test accuracy: 52.79%
- No overfitting detected

## 🔧 Using with Python

```python
import pandas as pd
import json

# Load data
df = pd.read_csv('metrics/alfa_match_explainers.csv')
with open('metrics/alfa_match_explainers.json') as f:
    data = json.load(f)

# Basic analysis
print(f"Accuracy: {df['correct_prediction'].mean():.1%}")
print(f"Mean confidence: {df['confidence'].mean():.4f}")

# Find a match
match = df[df['match_id'] == 'tournament_005_m0079'].iloc[0]

# Find high-impact moments
df['rating_gap_impact'] = abs(df['rating_gap_contribution'])
high_impact = df.nlargest(5, 'rating_gap_impact')
```

## 🔄 Regenerating Outputs

To regenerate from scratch:

```bash
# Step 1: Generate explanations
python generate_match_explainers.py

# Step 2: Generate visualizations and report
python generate_explainability_visualizations.py

# Step 3: Run analysis examples
python analyze_explainability.py
```

Requirements: pandas, numpy, matplotlib (all in requirements.txt)

## 📚 Documentation Hierarchy

Start here → Skim this → Deep dive →
```
1. This file              Quick overview
2. EXPLAINABILITY_REPORT.md    Executive summary + examples
3. MATCH_EXPLAINABILITY_GUIDE   Complete reference
```

## ⚡ 5-Minute Tour

1. **See the data** (30 sec)
   ```bash
   head metrics/alfa_match_explainers.csv
   ```

2. **View visualizations** (1 min)
   ```bash
   open metrics/visualizations/feature_importance.png
   ```

3. **Read report** (2 min)
   ```bash
   less metrics/EXPLAINABILITY_REPORT.md
   ```

4. **Run analysis** (1.5 min)
   ```bash
   python analyze_explainability.py
   ```

## 🎯 Common Use Cases

| Use Case | File | Sample Code |
|----------|------|------------|
| See sample matches | `sample_matches_table.html` | Open in browser |
| Find rating gap effects | `alfa_match_explainers.csv` | Filter by `rating_gap_weight` |
| Find race length effects | `alfa_match_explainers.csv` | Sort by `race_to_contribution` |
| Get model stats | `feature_importance_stats.json` | Load and inspect |
| Export for Excel | `alfa_match_explainers.csv` | Copy directly |
| Build API | `alfa_match_explainers.json` | Parse and serve |

## ✅ Verification Checklist

- [x] 2,400 matches explained
- [x] CSV format for analysis
- [x] JSON format for APIs
- [x] 5 visualizations created
- [x] Feature importance calculated
- [x] Confidence scores computed
- [x] Calibration analyzed
- [x] Full documentation written
- [x] Python analysis tools provided
- [x] Example outputs shown

## 📞 Support Scripts

**Need a specific analysis?** Run these:

```bash
# See 10 most important rating gap matches
python -c "from analyze_explainability import find_most_important_rating_gaps, load_explainability_data; df, _ = load_explainability_data(); print(find_most_important_rating_gaps(df, 10))"

# See prediction accuracy by format
python -c "from analyze_explainability import analyze_by_format, load_explainability_data; df, _ = load_explainability_data(); print(analyze_by_format(df))"

# See misclassified matches
python -c "from analyze_explainability import find_confident_errors, load_explainability_data; df, _ = load_explainability_data(); print(find_confident_errors(df, 5))"
```

## 🎓 For Your Next Steps

1. **Understand the data**: Read MATCH_EXPLAINABILITY_GUIDE.md
2. **Explore the outputs**: Open visualizations and CSV
3. **Run analysis**: Use analyze_explainability.py
4. **Build improvements**: Consider the recommendations in EXPLAINABILITY_REPORT.md
5. **Deploy**: Integrate explanations into your product/API

---

**Generated**: February 16, 2026  
**Test Set**: 2,400 billiards tournament matches  
**Model**: Logistic Regression (Fargo-based prediction)  
**All files**: metrics/ and docs/
