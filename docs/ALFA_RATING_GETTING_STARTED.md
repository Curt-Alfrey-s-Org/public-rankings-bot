# Alfa Rating v2 - Getting Started

**Quick start to make Alfa rating better than Fargo.**

---

## What's Ready to Use

### 1. Full Specification
📄 [docs/ALFA_RATING_V2_SPEC.md](docs/ALFA_RATING_V2_SPEC.md)
- Objective metrics (Brier score, cold-start RMSE, anomaly detection)
- Data schema for matches, players, and predictions
- Match outcome model (logistic regression + context adjustments)
- Explainability layer (per-match factor breakdown)
- 8-week implementation roadmap

### 2. Phase 1 Implementation Guide
📄 [docs/ALFA_RATING_PHASE1_GUIDE.md](docs/ALFA_RATING_PHASE1_GUIDE.md)
- **Step-by-step checklist:** Schema → Extract → Validate → Classify → Baseline → Split
- **Database schema extension:** `database/schema_alfa_extends.sql`
  - New tables: `alfa_player_ratings`, `alfa_anomaly_flags`, `alfa_match_predictions`, `alfa_prediction_factors`
  - New columns on `tournament_history_matches`: table_size, format, location, equipment, Elo tracking
- **Data extraction script:** `scripts/alfa_rating_data_prep.py`
  - Extract 10k+ matches from database
  - Validate quality (>90% completeness)
  - Classify by context (table size, format, location)
  - Export to CSV/JSON

### 3. Fargo Video Transcripts (Research)
📚 **Roadmap sections with Fargo insights:**
- Percentile-based divisions after registration (avoid pre-selection)
- Starter rating + robustness weighting for unrated players
- Rating equivalence (700 woman = 700 man, via mixed-game coupling)
- Fair-match lookups (race length based on rating gap)
- Handicap modes (hot/medium/mild)
- Rating scale benchmarks (150 = beginner, 550 = median, 700+ = pro)
- Rating differences (100 pts = 2:1 win ratio, 200 pts = 4:1)

---

## Next Steps (Immediate)

### Step 1: Apply Database Schema (5 minutes)
```bash
cd /home/ansible/rankings-bot/Rankings-Bot

# Review changes
cat database/schema_alfa_extends.sql

# Apply to database (if using PostgreSQL)
psql -U <your_user> -d <your_db> -f database/schema_alfa_extends.sql

# Verify
psql -U <your_user> -d <your_db> -c "\d alfa_player_ratings"
```

### Step 2: Extract Matches (10–30 minutes)
```bash
# Run extraction
python scripts/alfa_rating_data_prep.py --extract --output data/alfa_matches.csv

# Check results
wc -l data/alfa_matches.csv  # How many matches?
head -5 data/alfa_matches.csv  # Look good?
```

**Expected:** 10,000+ matches from `tournament_history_matches`

### Step 3: Validate Data (5 minutes)
```bash
python scripts/alfa_rating_data_prep.py --validate --input data/alfa_matches.csv
```

**Expected:** Report showing <2% missing fields, >500 unique players

### Step 4: Classify by Context (5 minutes)
```bash
python scripts/alfa_rating_data_prep.py --classify --input data/alfa_matches.csv
```

**Expected:** Matches grouped by (tournament/league, 8-ball/9-ball, 7ft/8ft/9ft)

---

## Key Ideas Behind Alfa v2

### Why Better Than Fargo?

1. **Richer data:** Table size, format, location, equipment → context-aware adjustments
2. **Explainability:** See exactly which factors shifted win probability
3. **Cold-start:** Bayesian blending + better starter rating → converges in 20 games vs 50
4. **Anomaly detection:** Flag sandbagging, rating mismatches, sudden jumps
5. **AI optimization:** Logistic regression + ML layer (optional) instead of just ELO

### Key Metrics

| Metric | Fargo | Alfa Target | Why |
|--------|-------|-------------|-----|
| **Brier Score** | ~0.20 | <0.18 | Calibration; how close predicted % is to actual |
| **Cold-Start RMSE** | ~80 pts | <50 pts | New unrated players converge faster |
| **Ranking Corr.** | 1.0 | >0.95 | Agree with Fargo, improve edges |
| **Sandbagging Detection** | None | >80% | Flag suspicious patterns |

### Model Architecture

```
Input: (rating_1, rating_2, race_to, table_size, format, location)
  ↓
Logistic Regression (core rating → win prob)
  ↓
Context Adjustments
  + table_size: 9ft favors strong players (+3%)
  + format: 8ball favors break, 9ball favors pattern
  + location: coupling confidence weighting
  ↓
Output: Predicted win%, factors, confidence
```

---

## Files You'll Use

| File | Purpose |
|------|---------|
| `database/schema_alfa_extends.sql` | Schema changes (apply once) |
| `scripts/alfa_rating_data_prep.py` | Extract/validate/classify (main workhorse) |
| `data/alfa_matches.csv` | Extracted matches (input to Phase 2) |
| `data/splits/train/val/test_matches.csv` | Train/validation/test (Phase 2 input) |

---

## Documentation Map

```
Rankings-Bot/
├── docs/
│   ├── ALFA_RATING_V2_SPEC.md          ← Full spec, metrics, architecture
│   ├── ALFA_RATING_PHASE1_GUIDE.md     ← Step-by-step Phase 1 checklist
│   ├── BUTTON_REFRESH_ARCHITECTURE.md  ← Frontend refresh (unrelated)
│   └── ...
├── database/
│   ├── schema_postgres.sql              ← Current schema
│   └── schema_alfa_extends.sql          ← NEW: Alfa tables & columns
├── scripts/
│   └── alfa_rating_data_prep.py        ← NEW: Extract/validate/classify
└── Roadmap.md                           ← Updated with Phase 1 status
```

---

## Questions?

- **What data do we have?** See [database/schema_postgres.sql](database/schema_postgres.sql) — `tournament_history_matches`, `tournament_history`, `tournament_results`
- **How do I run it?** See Phase 1 guide, step-by-step in [docs/ALFA_RATING_PHASE1_GUIDE.md](docs/ALFA_RATING_PHASE1_GUIDE.md)
- **What metrics matter?** See [docs/ALFA_RATING_V2_SPEC.md](docs/ALFA_RATING_V2_SPEC.md), section 1 (Brier score, cold-start RMSE, etc.)
- **What's the model?** See [docs/ALFA_RATING_V2_SPEC.md](docs/ALFA_RATING_V2_SPEC.md), section 3 (logistic regression + context adjustments)

---

## Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| **Phase 1: Data** | Week 1–2 | ✅ Ready (scripts written) |
| **Phase 2: Model** | Week 3–4 | ⏳ Next (needs data from Phase 1) |
| **Phase 3: Validation** | Week 5–6 | ⏳ TBD |
| **Phase 4: Integration** | Week 7–8 | ⏳ TBD |
| **Phase 5: Launch** | Week 9+ | ⏳ TBD |

---

**Next action:** Run `python scripts/alfa_rating_data_prep.py --extract` and start Phase 1! 🚀
