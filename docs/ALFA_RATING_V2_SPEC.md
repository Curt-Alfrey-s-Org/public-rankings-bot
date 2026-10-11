# Alfa Rating v2 Specification

**Goal:** Develop an AI-optimized pool player rating system that exceeds Fargo accuracy while remaining explainable and transparent.

**Status:** Specification Phase

---

## 1. Objective Metrics & Baselines

### Primary Metrics (vs Fargo baseline)

| Metric | Description | Fargo Baseline | Target | Method |
|--------|-------------|-----------------|--------|--------|
| **Brier Score** | Calibration error for binary match outcome predictions | ~0.20 | <0.18 | Lower is better; measures how close predicted win% is to actual outcomes |
| **Ranking Correlation (Spearman ρ)** | Agreement between Alfa and Fargo rank order | 1.0 (self) | >0.95 | Should agree with Fargo on general ranking but improve edge cases |
| **Stability (RMSE over 100 days)** | How much rating changes when new data is added | ~5–10 pts | <5 pts | Robustness to individual match noise |
| **Cold-Start RMSE** | Prediction error for unrated players in first 10 games | ~80 pts | <50 pts | Starter rating + Bayesian prior quality |
| **Sandbagging Detection Rate** | % of manipulation attempts flagged | 0% (undetected) | >80% | Explainable anomaly scoring |

### Validation Strategy

- Train on historical data (75%), validate on held-out recent matches (25%)
- Stratify by rating bands (200–300, 300–500, 500–700, 700+)
- Separate validation for short races (to 3–5) vs long races (to 11+)
- Report metrics per context (league, tournament, table size)

---

## 2. Data Schema

### Match Record

```python
class Match:
    match_id: str
    date: datetime
    player_1_id: str
    player_2_id: str
    result: {
        "winner_id": str,
        "winner_games": int,
        "loser_games": int,
        "race_to": int,  # e.g., 5, 7, 11
        "table_size": str,  # "7ft" | "8ft" | "9ft"
    }
    event_type: str  # "league" | "tournament" | "casual"
    location_id: str  # For regional coupling
    equipment: {
        "cue_ball_type": str,  # "standard" | "super" | "aramith"
        "cloth_type": str,  # "simonis" | "iwan" | "other"
    }
    player_1_elo_start: float
    player_2_elo_start: float
    player_1_elo_end: float
    player_2_elo_end: float  # Post-match Alfa ratings
```

### Player Profile

```python
class PlayerProfile:
    player_id: str
    name: str
    rating: float  # Current Alfa rating (200–900 scale)
    robustness: int  # Number of games
    rating_history: List[{
        "date": datetime,
        "rating": float,
        "robustness": int,
        "reason": str  # "match_outcome" | "recalibration" | "cold_start"
    }]
    starter_rating: float  # Initial guess (from region/prior classification)
    anomaly_score: float  # 0–1, where >0.7 = suspicious
    anomaly_flags: List[str]  # ["winning_weak_only", "rating_vs_league_mismatch", ...]
```

---

## 3. Match Outcome Model

### Core Algorithm: Fargo-inspired with Context Adjustment

```
predicted_win_prob(player_1, player_2, context) = sigmoid(
    alpha * (rating_1 - rating_2) / 100
    + beta_race_to * log(race_to)
    + beta_table * table_size_adjustment
    + beta_format * format_adjustment
    + beta_event * event_type_adjustment
    + context_residual
)
```

#### Parameters

| Parameter | Fargo Logic | Alfa v2 | Rationale |
|-----------|-------------|---------|-----------|
| `alpha` | ~0.006 per point (2-to-1 ratio at 100 pts) | Fit via logistic regression | Match empirical win rates |
| `beta_race_to` | Implicit in Fargo; long races reduce prob variance | Explicit coefficient | Account for race-length noise floor |
| `beta_table` | None; Fargo ignores table size | ~0.02–0.05 per size change | 7ft → 9ft shifts win% ~2–5% |
| `beta_format` | None; Fargo averages across formats | Separate for 8-ball, 9-ball, 10-ball | Format skill transfer is not 1:1 |
| `beta_event` | None; Fargo treats league = tournament | ~0.01–0.03 per category | Tournament stress/selectivity differs |

#### Context Adjustments

**Table Size Impact**
- Hypothesis: 7ft → 9ft: stronger players' advantage increases (tighter prob control)
- Model: `table_adjustment = { "7ft": -0.02, "8ft": 0.0, "9ft": +0.03 }`
- Data: Conduct a regional study (Skylar Woodward case study) on same-player results across tables

**Format (8-ball, 9-ball, 10-ball)**
- Hypothesis: 8-ball favors break dominance; 9-ball favors pattern play
- Model: Fit separate `beta_format` per pair of formats
- Data: Collect players with games in 2+ formats; measure cross-format correlation

**Event Type (League vs Tournament)**
- Hypothesis: Tournament results are more reliable (higher stakes, less casual play)
- Model: Weight tournament games 1.2x vs league games
- Data: A/B test: drop league-only players' game weight vs tournament-regular players

**Geography / Regional Coupling**
- Hypothesis: Local players have higher coupling density; distant matches have larger prediction errors
- Model: Confidence weight based on geographic distance to nearest shared opponent
- Data: Compute a "coupling matrix" per region pair; weight matches inversely by distance

---

## 4. Cold-Start & Starter Rating

### Goal
New unrated players should receive fair matchups and convergence in ~10–20 games (vs Fargo's ~50).

### Starter Rating Strategy

```python
def starter_rating(player: NewPlayer) -> float:
    if player.prior_classification:
        # e.g., "APA 7" or "Arizona 6"
        return region_to_elo_mapping[player.prior_classification]
    elif player.local_ranking:
        # e.g., ranked #15 in local league of 200
        return infer_elo_from_percentile(player.percentile)
    else:
        return 400  # Default beginner-friendly rating
```

### Bayesian Prior Weighting

```python
def blended_rating(games_count: int, starter: float, measured: float) -> float:
    """
    Blend starter rating (strong prior) with measured rating (likelihood).
    Robustness threshold ~50 games before confidently moving to measured.
    """
    if games_count < 10:
        weight_starter = 0.8
    elif games_count < 50:
        weight_starter = 0.5 * (1 - games_count / 50)
    else:
        weight_starter = 0.0
    
    return weight_starter * starter + (1 - weight_starter) * measured
```

**Result:** With a good starter rating, new players should converge ±30 points within 20 games.

---

## 5. Anomaly Detection & Sandbagging Flags

### Suspicious Patterns

| Flag | Logic | Score Weight | Action |
|------|-------|--------------|--------|
| `winning_weak_only` | 80%+ of wins vs players rated >50 pts below | +0.3 | May be inflated; check for colluding weak opponents |
| `losing_strong_only` | 80%+ of losses vs players rated >50 pts above | +0.2 | Possible setup play (sandbag); monitor |
| `rating_league_mismatch` | Fargo rating SEM vs actual league division placement (e.g., "Advanced" but rated 350) | +0.25 | Check data entry or old data |
| `sudden_jump` | Rating increase >40 pts in 5 games vs established players | +0.2 | Possible streak luck; resample after 10 more games |
| `high_variance` | Std dev of expected win% vs actual outcomes >0.35 | +0.15 | Inconsistent play; note in profile |
| `break_dominance_outlier` | Break win rate >75% (vs ~55% for same rating) | +0.15 | Possible table/equipment advantage; flag table size |

### Anomaly Score

```python
anomaly_score = sum(flag_weights) / len(active_flags)
# 0.0 = clean; 0.5 = moderate concern; >0.7 = high concern
```

**Action:** Display anomaly_score to admins in UI; do not penalize player rating, but flag for manual review.

---

## 6. Interpretability & Explainability

### Per-Match Explainer

For any predicted match outcome, return:

```python
{
    "match_id": "...",
    "predicted_win_prob": 0.62,
    "factors": [
        {"name": "Rating gap", "contribution": +0.08, "direction": "favors_player_1"},
        {"name": "Table size (9ft)", "contribution": +0.03, "direction": "favors_player_1"},
        {"name": "Event type (tournament)", "contribution": +0.01, "direction": "favors_player_1"},
        {"name": "Race length (to 11)", "contribution": -0.02, "direction": "favors_player_2"},
        {"name": "Regional coupling", "contribution": 0.0, "note": "direct play; high confidence"}
    ],
    "confidence": 0.7,  # based on robustness & coupling
    "note": "Prediction close to 50/50; match likely decided by execution"
}
```

### Rating Change Transparency

When a player's rating updates after a match:

```python
{
    "player_id": "...",
    "old_rating": 525,
    "new_rating": 528,
    "change": +3,
    "match_details": {
        "opponent_rating": 495,
        "opponent_name": "...",
        "result": "win (7-4 race to 7)",
        "expected_outcome_prob": 0.58,  # Upset if <0.5
        "information_gain": 0.04,  # bits of info from result
    },
    "formula": "Glicko-2 / custom ELO variant with robustness decay",
}
```

---

## 7. Implementation Roadmap

### Phase 1: Data Preparation (Week 1–2)
- [ ] Extract historical matches from database (>10k matches minimum)
- [ ] Validate data quality (missing fields, outliers)
- [ ] Compute Fargo baseline predictions on holdout test set
- [ ] Classify matches by context (table size, event type, format)

### Phase 2: Model Development (Week 3–4)
- [ ] Fit logistic regression for core rating-difference → win-prob relationship
- [ ] Add context-adjustment coefficients (race-to, table size, format)
- [ ] Implement cold-start Bayesian blending
- [ ] Fit anomaly-detection thresholds

### Phase 3: Validation & Tuning (Week 5–6)
- [ ] Measure Brier score, ranking correlation, stability vs Fargo
- [ ] Stratify accuracy by rating band and context
- [ ] Sensitivity analysis (which factors matter most?)
- [ ] A/B test starter rating quality on new players

### Phase 4: Integration (Week 7–8)
- [ ] Add explainability layer (per-match factors, rating change details)
- [ ] Build admin UI for anomaly review
- [ ] Deploy alongside Fargo rankings (run both in parallel initially)
- [ ] Collect user feedback on accuracy and fairness

### Phase 5: Launch & Monitoring (Week 9+)
- [ ] Switch to Alfa as primary; keep Fargo in logs for audit
- [ ] Monitor drift (does Alfa accuracy degrade over time?)
- [ ] Periodic recalibration (quarterly refit of context factors)
- [ ] Publish results & comparison study

---

## 8. Success Criteria

- ✅ **Brier score < 0.18** (vs Fargo ~0.20)
- ✅ **Cold-start RMSE < 50 pts** (vs Fargo ~80)
- ✅ **Ranking correlation > 0.95** with Fargo (stable, not radical shifts)
- ✅ **Anomaly detection > 80% precision** for known sandbagging cases
- ✅ **No regression in any player band** (stratified accuracy ≥ Fargo in all buckets)
- ✅ **Explainability score > 4/5** (admin survey on clarity of ratings)

---

## 9. Future Enhancements

### Optional: Machine Learning Layer

Once v1 is stable (>1000 matches validated):
- Neural network to learn non-linear rating-difference → win-prob curve
- RNN to capture form/momentum (recent game history)
- Implicit feature learning (table/equipment substitutes)
- Uncertainty quantification (Bayesian deep learning)

**Constraint:** Keep output interpretable (SHAP explanations, not black-box confidence intervals).

### Optional: Real-time Match Prediction

- Stream live match scores; update win-prob mid-match
- Flag upset-in-progress for broadcast / UI highlighting
- Post-match explain "what went right/wrong"

### Optional: Team Event Modeling

- Extend to team events (co-rated players, team synergy)
- Roster balance suggestions (draft helper)
- Team cap enforcement (Fargo-style)

---

## References

- **Baseline:** Fargo ratings (CSI Q Sports International)
- **Literature:** Glicko-2 (Glickman 2012), Elo variants (Sonas 2012)
- **Validation Data:** Historical BCA/USAPL league matches, regional tours
- **Case Studies:** Dave (6400 games, mixed strength), Karen Corr (coupler), Skylar Woodward (table size)

