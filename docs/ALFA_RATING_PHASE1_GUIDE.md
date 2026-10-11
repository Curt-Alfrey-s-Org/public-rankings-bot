# Alfa Rating v2 - Phase 1 Implementation Guide

**Phase:** Data Preparation (Week 1–2)  
**Goal:** Extract, validate, and classify 10k+ historical matches for model training  
**Status:** Starting

---

## Checklist

- [ ] **Task 1.1:** Apply schema extension (adds Alfa-specific columns)
- [ ] **Task 1.2:** Extract historical matches from database
- [ ] **Task 1.3:** Validate data quality (check >90% completeness)
- [ ] **Task 1.4:** Classify matches by context (table size, format, location)
- [ ] **Task 1.5:** Generate baseline metrics report
- [ ] **Task 1.6:** Prepare train/validation/test splits

---

## Task 1.1: Apply Schema Extension

**Why:** Add Alfa-specific columns to track table size, format, location, and equipment.

```bash
# 1. Review changes
cat database/schema_alfa_extends.sql

# 2. Apply to PostgreSQL (if using Postgres)
psql -U <user> -d <dbname> -f database/schema_alfa_extends.sql

# 3. Verify tables exist
psql -U <user> -d <dbname> -c "\d alfa_player_ratings"
psql -U <user> -d <dbname> -c "\d alfa_match_predictions"
psql -U <user> -d <dbname> -c "\d alfa_anomaly_flags"
```

**New Tables Created:**
- `alfa_player_ratings` – Tracks rating changes over time
- `alfa_anomaly_flags` – Flags suspicious patterns
- `alfa_match_predictions` – Stores predictions for validation
- `alfa_prediction_factors` – Explainability: per-match factor contributions
- `alfa_data_quality_report` – Training data quality metrics

**New Columns on `tournament_history_matches`:**
- `table_size` – "7ft", "8ft", "9ft"
- `game_format` – "8ball", "9ball", "10ball"
- `race_to` – Explicit race-to (can compute from scores)
- `equipment_ball`, `equipment_cloth` – Equipment metadata
- `event_context` – "league", "tournament", "casual"
- `location_city`, `location_state`, `location_country` – Geographic metadata
- `operator_elo_start`, `player2_elo_start` – Starting Alfa ratings
- `operator_elo_end`, `player2_elo_end` – Ending Alfa ratings

---

## Task 1.2: Extract Historical Matches

**Data Source:** `tournament_history_matches` + `tournament_history` + `tournament_results`

**Output:** `data/alfa_matches.csv` (10,000+ matches)

```bash
cd /home/ansible/rankings-bot/Rankings-Bot

# Run extraction
python scripts/alfa_rating_data_prep.py --extract --output data/alfa_matches.csv

# Check output
head -20 data/alfa_matches.csv
wc -l data/alfa_matches.csv  # Should be >10,000 matches
```

**Script:** `scripts/alfa_rating_data_prep.py`

**What it does:**
1. Queries `tournament_history_matches` with joins to `tournament_history` and `tournament_results`
2. Parses player scores → infers `race_to` (max of two scores)
3. Extracts Fargo ratings from `tournament_results` if available
4. Exports to CSV and JSON

**Expected Output:**
```
match_id,date,player_1_id,player_1_name,player_2_id,player_2_name,winner_id,winner_games,loser_games,race_to,table_size,event_type,format,location_id,fargo_rating_p1,fargo_rating_p2
...
```

---

## Task 1.3: Validate Data Quality

**Goal:** Ensure >90% data completeness; identify and flag bad records.

```bash
# Run validation
python scripts/alfa_rating_data_prep.py --validate --input data/alfa_matches.csv
```

**Checks Performed:**

| Check | Threshold | Action if Failed |
|-------|-----------|------------------|
| Missing `match_id` | <5% | Flag as duplicate/id issue |
| Missing `date` | <5% | Remove or estimate from neighbors |
| Missing `player_1/2_name` | 0% | Remove (can't identify players) |
| Missing `winner_games/loser_games` | 0% | Remove (can't compute outcomes) |
| Invalid scores (winner ≤ loser) | <1% | Flip or remove |
| Duplicate match IDs | <1% | Deduplicate by date + players |
| Date range consistency | Check | Ensure chronological |
| Unique players | >100 | Threshold for meaningful data |

**Output:** `data/alfa_matches_validation.json`

```json
{
  "total_matches": 12543,
  "timestamp": "2026-02-16T...",
  "checks": {
    "missing_fields": {
      "match_id": 0,
      "date": 3,
      "player_1_name": 0,
      "winner_games": 0
    },
    "invalid_scores": {
      "invalid_winners": 2,
      "examples": [...]
    },
    "duplicate_matches": {
      "duplicate_match_ids": 0
    },
    "date_range": {
      "earliest": "2020-01-01",
      "latest": "2026-02-16",
      "count": 12540
    },
    "player_coverage": {
      "unique_players": 2847
    }
  }
}
```

**Acceptance Criteria:**
- ✅ Total matches: ≥10,000
- ✅ Missing critical fields: <2%
- ✅ Invalid scores: <1%
- ✅ Unique players: >500
- ✅ Date range: ≥3 years

---

## Task 1.4: Classify Matches by Context

**Goal:** Group matches by table size, format, location, and event type for stratified analysis.

```bash
# Run classification
python scripts/alfa_rating_data_prep.py --classify --input data/alfa_matches.csv
```

**Output:** `data/alfa_matches_classified.csv` (same as input CSV, with inferred context columns)

**Classification Heuristics:**
- **Table size:** Infer from tournament metadata or location (default: 9ft)
- **Format:** Infer from tournament name ("8ball", "9ball", "10ball")
- **Event type:** All extracted matches = "tournament" (league data not yet available)
- **Location:** Parse from tournament metadata (city, state, country)

**Groupings to Analyze:**

| Context | Example | Count | Purpose |
|---------|---------|-------|---------|
| `tournament_9ball_9ft` | BCA nationals on 9ft | ~5000 | High-quality matches, professional level |
| `tournament_9ball_8ft` | Regional tour on 8ft | ~3000 | Medium quality, good distribution |
| `tournament_8ball_*` | 8ball events | ~2000 | Format-specific modeling |
| By location | Vegas, regional, international | ~200 regions | Coupling analysis |

**Output Statistics:**

```
tournament_9ball_9ft: 5234 matches
tournament_9ball_8ft: 3108 matches
tournament_8ball_9ft: 2145 matches
tournament_10ball_9ft: 1156 matches
tournament_8ball_8ft: 900 matches
...
```

---

## Task 1.5: Generate Baseline Metrics Report

**Goal:** Compute Fargo baseline predictions on hold-out test set.

```bash
python scripts/alfa_rating_baseline.py \
  --input data/alfa_matches_classified.csv \
  --train-split 0.75 \
  --test-split 0.25 \
  --output metrics/fargo_baseline.json
```

**Metrics Computed (on test set):**

| Metric | Fargo Baseline | Target | Description |
|--------|-----------------|--------|-------------|
| **Brier Score** | 0.20 | <0.18 | Calibration error (lower is better) |
| **Ranking Corr. (Spearman ρ)** | 1.0 | >0.95 | Agreement with Fargo rank order |
| **Stability (RMSE/100d)** | ~8 pt | <5 pt | How much rating changes w/ new data |
| **Cold-start RMSE (10 games)** | ~80 pt | <50 pt | Error for unrated players |
| **Precision @ K** | – | >0.85 | Top-K accuracy for winner prediction |

**Output:** `metrics/fargo_baseline.json`

```json
{
  "model": "fargo",
  "dataset": "alfa_matches_classified",
  "date_range": ["2020-01-01", "2026-02-16"],
  "total_matches": 12543,
  "train_matches": 9407,
  "test_matches": 3136,
  "metrics": {
    "brier_score": 0.1987,
    "logloss": 0.4512,
    "ranking_correlation": {
      "spearman_rho": 1.0,
      "kendall_tau": 0.9892
    },
    "stratified_accuracy": {
      "200-300": 0.72,
      "300-500": 0.76,
      "500-700": 0.83,
      "700+": 0.91
    },
    "by_context": {
      "tournament_9ball_9ft": {
        "brier": 0.196,
        "count": 1234
      },
      "tournament_8ball_9ft": {
        "brier": 0.205,
        "count": 456
      }
    }
  }
}
```

---

## Task 1.6: Prepare Train/Validation/Test Splits

**Goal:** Create stratified splits for Phase 2 model development.

```bash
python scripts/alfa_rating_split_data.py \
  --input data/alfa_matches_classified.csv \
  --train 0.60 --val 0.20 --test 0.20 \
  --stratify-by context \  # Ensure each split covers all contexts
  --output-dir data/splits
```

**Splits:**
- **Train (60%):** 7,525 matches – Used to fit model
- **Validation (20%):** 2,508 matches – Used for hyperparameter tuning
- **Test (20%):** 2,508 matches – Used for final evaluation

**Stratification:** Ensure each split includes all contexts (table sizes, formats, locations).

**Output Files:**
- `data/splits/train_matches.csv`
- `data/splits/val_matches.csv`
- `data/splits/test_matches.csv`
- `data/splits/split_info.json` (metadata)

---

## Implementation Notes

### Data Quality Issues to Handle

1. **Missing table_size:** Default to "9ft" (most common)
2. **Missing format:** Infer from tournament name or default to "9ball"
3. **Missing race_to:** Compute from max(winner_games, loser_games)
4. **Fargo ratings missing:** Mark as `NULL` (will be imputed in Phase 2)
5. **Duplicate matches:** Deduplicate by (date, operator_name, player2_name, scores)

### Coupling Analysis

Once data is classified, compute:
- **Regional overlap:** How many matches connect players from different regions?
- **Rating range span:** What rating range do we have data for?
- **Time series:** Are matches evenly distributed over time or clustered?

### Next Steps (Phase 2)

Phase 1 deliverables feed into Phase 2:
- Input: `data/splits/train_matches.csv`
- Task: Fit logistic regression + context adjustments
- Output: `models/alfa_v1_logistic.pkl`

---

## Scripts Available

| Script | Purpose |
|--------|---------|
| `scripts/alfa_rating_data_prep.py` | Extract, validate, classify matches |
| `scripts/alfa_rating_baseline.py` | Compute Fargo baselines (to implement) |
| `scripts/alfa_rating_split_data.py` | Create train/val/test splits (to implement) |

---

## Timeline

| Week | Tasks |
|------|-------|
| **Week 1** | 1.1–1.3 (schema, extraction, validation) |
| **Week 2** | 1.4–1.6 (classification, baseline, splits) |

