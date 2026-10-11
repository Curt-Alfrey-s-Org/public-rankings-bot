# Stratified Train/Validation/Test Splits — Alfa Rating Model

## Executive Summary

Successfully created stratified train/validation/test splits for the Alfa rating model training from 12,000 classified billiards matches.

**Split Allocation:**
- **Train**: 7,200 matches (60%)
- **Validation**: 2,400 matches (20%)
- **Test**: 2,400 matches (20%)
- **Total**: 12,000 matches

**Status**: ✓ Complete | ✓ No overlaps | ✓ Stratification verified

---

## Split Configuration

### Stratification Strategy

Splits were created using **stratified sampling** to ensure balanced representation across categorical dimensions:

1. **Game Format** (9-ball, 8-ball, 10-ball)
2. **Table Size** (7ft, 8ft, 9ft)
3. **Format-Size Combinations** – Primary stratification key

The two-stage stratified split process:
1. First split: 60% train vs. 40% validation+test (stratified by format+table_size)
2. Second split: 50-50 split of validation+test (stratified by format+table_size)

This ensures each split maintains the same proportional distribution of categories.

### Data Source

- **File**: `data/alfa_matches_classified.csv`
- **Total Records**: 12,000 matches
- **Date Range**: 2023-01-01 to 2024-12-31
- **Format Coverage**: 100% 9-ball (current dataset)
- **Table Size Coverage**: 100% 9ft (current dataset)

---

## Distribution Verification

### Original Dataset Distribution

| Dimension | Value | Count | Percentage |
|-----------|-------|-------|-----------|
| **Game Format** | 9-ball | 12,000 | 100.00% |
| **Table Size** | 9ft | 12,000 | 100.00% |
| **Combined Category** | 9ball_9ft | 12,000 | 100.00% |

### Train Set Distribution

| Dimension | Value | Count | Percentage |
|-----------|-------|-------|-----------|
| **Game Format** | 9-ball | 7,200 | 100.00% |
| **Table Size** | 9ft | 7,200 | 100.00% |
| **Combined Category** | 9ball_9ft | 7,200 | 100.00% |

### Validation Set Distribution

| Dimension | Value | Count | Percentage |
|-----------|-------|-------|-----------|
| **Game Format** | 9-ball | 2,400 | 100.00% |
| **Table Size** | 9ft | 2,400 | 100.00% |
| **Combined Category** | 9ball_9ft | 2,400 | 100.00% |

### Test Set Distribution

| Dimension | Value | Count | Percentage |
|-----------|-------|-------|-----------|
| **Game Format** | 9-ball | 2,400 | 100.00% |
| **Table Size** | 9ft | 2,400 | 100.00% |
| **Combined Category** | 9ball_9ft | 2,400 | 100.00% |

**Observation**: Since the current dataset contains only 9-ball format on 9ft tables, all splits have identical distributions (100.00% each). This is perfect stratification for the available data. Once future data with additional formats or table sizes is added, the stratification will maintain balanced representation.

---

## Output Files

All split files are located in: `/home/ansible/rankings-bot/Rankings-Bot/data/splits/`

### CSV Files

| File | Records | Size | Columns |
|------|---------|------|---------|
| `train_matches.csv` | 7,200 | 960 KB | 18 (all original + strat_group) |
| `val_matches.csv` | 2,400 | 321 KB | 18 (all original + strat_group) |
| `test_matches.csv` | 2,400 | 320 KB | 18 (all original + strat_group) |
| `split_info.json` | — | 2.0 KB | Metadata & verification |

### Column Structure

Each CSV contains all original columns plus:
- `match_id` – Unique match identifier
- `date` – Match date
- `player_1_id`, `player_1_name` – First player info
- `player_2_id`, `player_2_name` – Second player info
- `winner_id`, `winner_games`, `loser_games` – Match outcome
- `race_to` – Game race target
- `table_size` – Table dimensions (9ft)
- `event_type` – Tournament type
- `format` – Game format (9-ball)
- `location_id` – Venue identifier
- `equipment` – Equipment notes
- `fargo_rating_p1`, `fargo_rating_p2` – Player ratings (if available)
- `strat_group` – Stratification group (format + table_size)

---

## Integrity Verification

### No Overlap Verification

| Comparison | Overlapping Records |
|-----------|---------------------|
| Train ↔ Validation | 0 |
| Train ↔ Test | 0 |
| Validation ↔ Test | 0 |
| **Total Unique IDs** | 12,000 |
| **Total Records Across Splits** | 12,000 |

✓ **Result**: Perfect split integrity — no record appears in multiple sets.

### Record Count Validation

```
train_matches.csv:  7,201 lines (7,200 records + header)
val_matches.csv:    2,401 lines (2,400 records + header)
test_matches.csv:   2,401 lines (2,400 records + header)
─────────────────────────────────────────
Total records:     12,000 ✓
```

---

## Sample Data

### Train Set (First 3 Matches)

| Match ID | Date | Player 1 | Player 2 | Format | Table | Winner |
|----------|------|----------|----------|--------|-------|--------|
| tournament_078_m0063 | 2023-05-05 | Freya Clark | Nina Moore | 9ball | 9ft | nina_moore |
| tournament_040_m0016 | 2023-10-03 | Freya Martinez | Blake Robinson | 9ball | 9ft | freya_martinez |
| tournament_115_m0020 | 2023-08-17 | Ryan Hill | Caleb Lee | 9ball | 9ft | ryan_hill |

### Validation Set (First 3 Matches)

| Match ID | Date | Player 1 | Player 2 | Format | Table | Winner |
|----------|------|----------|----------|--------|-------|--------|
| tournament_003_m0044 | 2024-07-20 | Oscar Young | Blake King | 9ball | 9ft | oscar_young |
| tournament_hub_m0074 | 2023-06-01 | Ivan Brown | Julia King | 9ball | 9ft | ivan_brown |
| tournament_monitor_m0080 | 2024-02-14 | Ethan Clark | Ethan Martinez | 9ball | 9ft | ethan_clark |

### Test Set (First 3 Matches)

| Match ID | Date | Player 1 | Player 2 | Format | Table | Winner |
|----------|------|----------|----------|--------|-------|--------|
| tournament_017_m0091 | 2023-04-26 | Kevin Davis | Ursula Taylor | 9ball | 9ft | ursula_taylor |
| tournament_monitor_m0036 | 2024-01-03 | Mike Miller | Blake Davis | 9ball | 9ft | blake_davis |
| tournament_047_m0038 | 2024-09-09 | Mike Taylor | Freya Moore | 9ball | 9ft | freya_moore |

---

## Metadata (split_info.json)

The `split_info.json` file contains complete stratification metadata:

```json
{
  "total_records": 12000,
  "split_sizes": {
    "train": {"records": 7200, "percentage": "60.00%"},
    "validation": {"records": 2400, "percentage": "20.00%"},
    "test": {"records": 2400, "percentage": "20.00%"}
  },
  "stratification": {
    "base_column": "format_table_size combination",
    "original": { ... original distribution ... }
  },
  "split_distributions": {
    "train": { ... train set distribution ... },
    "validation": { ... validation set distribution ... },
    "test": { ... test set distribution ... }
  }
}
```

---

## Model Training Usage

### Load Train/Validation/Test Splits in Python

```python
import pandas as pd

# Load splits
train_df = pd.read_csv('data/splits/train_matches.csv')
val_df = pd.read_csv('data/splits/val_matches.csv')
test_df = pd.read_csv('data/splits/test_matches.csv')

print(f"Train: {len(train_df)} | Val: {len(val_df)} | Test: {len(test_df)}")
# Output: Train: 7200 | Val: 2400 | Test: 2400

# Prepare features and labels
X_train = train_df[feature_columns].values
y_train = train_df['winner_id'].values

X_val = val_df[feature_columns].values
y_val = val_df['winner_id'].values

X_test = test_df[feature_columns].values
y_test = test_df['winner_id'].values
```

### Stratification Benefits

1. **Balanced Training**: Each split contains representative samples of all categories
2. **Fair Evaluation**: Validation and test sets reflect same distribution as training data
3. **No Leakage**: Complete separation of splits prevents training on test data
4. **Robust Metrics**: Model performance estimates are reliable across categories

---

## Future Considerations

### Extending Stratification

When additional data is available with multiple formats (8-ball, 10-ball) or table sizes (7ft, 8ft), the stratification script can be enhanced to:

1. **Create rating bands** – Split players into skill tiers (e.g., 200-400, 400-600, 600+)
2. **Multi-level stratification** – Combine format, table size, and rating bands
3. **Proportional representation** – Maintain exact percentages across all dimensions

### Recommended Enhancements

```python
# Future: Bin ratings into stratification groups
def create_rating_bins(df):
    df['rating_band'] = pd.cut(df['fargo_rating_p1'], 
                                bins=[0, 400, 600, 800, 1000],
                                labels=['beginner', 'intermediate', 'advanced', 'elite'])
    return df

# Future: Multi-dimensional stratification
stratify_by = df['format'] + '_' + df['table_size'] + '_' + df['rating_band']
train_test_split(..., stratify=stratify_by)
```

---

## Script Reference

**Creation Script**: `scripts/create_stratified_splits.py`

Features:
- Loads and validates data
- Creates stratification groups
- Performs two-stage stratified split
- Verifies no overlap
- Generates comprehensive metadata
- Produces detailed distribution reports
- Outputs sample rows from each split

**Run**: 
```bash
python3 scripts/create_stratified_splits.py
```

---

## Summary

✓ **12,000 matches** successfully split into balanced train/validation/test sets  
✓ **Stratification** by game format and table size ensures representative samples  
✓ **No overlaps** verified — complete data separation across sets  
✓ **Metadata generated** for full auditability and reproducibility  
✓ **Ready for training** — splits are production-ready for Alfa rating model  

All files are located in `data/splits/` directory with supporting metadata in JSON format.
