# 10-Tournament Rule

## Rule Statement

As stated at the top of the WPBA PDF and applying to other associations per their published math and rules:

**Only the most recent 10 tournaments count toward a player's total ranking points.**

- The **11th** (next-oldest) tournament is **still shown** in listings and breakdowns but **not included** in the total points calculation.
- **12th and older** tournaments remain in **tournament history** and are used by other parts of the application (e.g., player performance analysis, leaderboard trends, hot streak detection).

## Scope

This rule applies to:
- **WPBA** rankings (as explicitly stated in their official PDF)
- **Other associations** (WPA, etc.) where rankings are computed from multiple tournaments/events — the same "most recent 10 count; 11th shown but not counted; older in history" concept applies per their published rules and math.

## Data Impact

### Ranking Total
- **Calculation:** Sum only points from each player's **most recent 10 tournaments** (by chronological tournament order, most recent first).
- **Players with fewer than 10 tournaments:** All their tournaments count (no penalty for having fewer events).

### Display and Breakdowns
- The 11th tournament can still appear in player breakdowns, recent tournament lists, and historical views.
- Its points are **excluded** from any displayed ranking total that follows this rule.
- Full tournament history remains available for analysis.

### Tournament History Storage
- **No tournaments are removed** from the database.
- All tournaments (including 12th and older) stay in `tournament_history` and `tournament_results` tables.
- **Player performance**, **leaderboard**, and other pages continue to use full tournament history for their calculations and displays.
- Only the **ranking total computation** (when merging confirmed tournament imports) applies the most-recent-10 rule.

## Implementation

The rule is implemented in `tournament_tools/load_final_results.py` when merging confirmed tournament imports into rankings:

- `RANKING_COUNT_TOURNAMENTS = 10`: Constant defining how many tournaments count toward total points.
- `calculate_player_totals_last_n_tournaments()`: Helper function that computes per-player totals using only the last N tournaments.
- `merge_confirmed_imports_to_rankings()`: Updated to use the helper instead of summing all tournaments.

## Examples

### Player with 12 tournaments
- **Tournaments 1-10** (most recent): Points included in ranking total
- **Tournament 11**: Points excluded from total, but tournament shown in history
- **Tournament 12+**: Kept in tournament history for performance analysis

### Player with 8 tournaments
- **All 8 tournaments**: Points included in ranking total (no minimum requirement)

## References

- WPBA official PDF (rule stated at the top)
- Other association rules (same math and logic applies)
- Implementation: `tournament_tools/load_final_results.py`