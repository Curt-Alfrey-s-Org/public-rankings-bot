# Case Study: Skylar Woodward — Table Size (7 ft vs 9 ft) Impact

**Status:** Placeholder for future analysis.  
**Goal:** Quantify how table size affects performance and ratings for elite players.

---

## Hypothesis

Strong players may perform differently on 7-ft vs 9-ft tables due to:
- Break-and-run frequency (7-ft favors break dominance)
- Pattern play and safety (9-ft favors positional play)
- Equipment sensitivity (cloth, pocket size)

---

## Planned Analysis

1. **Data:** Extract Skylar Woodward's match history by table size from `tournament_history_matches` (or external sources).
2. **Metrics:** Win rate, games-per-match, runout rate by `table_size` (7ft, 8ft, 9ft).
3. **Rating stability:** Compare Fargo (or Alfa) rating when stratified by table size.
4. **Conclusion:** Document whether table-size adjustment is warranted for prediction models.

---

## Implementation

- Script: `scripts/alfa_rating_data_prep.py` already extracts `table_size`.
- Model: `fit_context_adjustments.py` includes `table_size` in context features.
- Run: `python fit_context_adjustments.py` then review `metrics/context_adjustment_analysis.json` for `by_table_size` stratified metrics.

---

## References

- [ALFA_RATING_V2_SPEC.md](ALFA_RATING_V2_SPEC.md) — Table size adjustment hypothesis
- [CONTEXT_ADJUSTMENT_VALIDATION_REPORT.md](../CONTEXT_ADJUSTMENT_VALIDATION_REPORT.md) — Current table_size coefficients
