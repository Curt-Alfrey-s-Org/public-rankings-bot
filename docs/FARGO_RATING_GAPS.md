# Fargo Rating Differences — Expected Win Rates & Fair Matchups

**Source:** Fargo Rate methodology; logarithmic relationship from rating gap to win probability.  
**Reference:** [FargoRate.com](https://www.fargorate.com/), project `api/services/fargo_handicap.py`

---

## Rating Gap → Expected Win Ratio

Every **+100 points** halves the lower-rated player's expected game wins. Approximate mapping:

| Gap (pts) | Expected Win Ratio | Example (race to 7) |
|-----------|--------------------|---------------------|
| 0 | 50/50 | 7–7 even |
| 15 | ~52/48 | Slight favorite |
| 22 | ~54/46 | |
| 32 | ~57/43 | |
| 42 | ~60/40 | |
| 59 | ~65/35 | |
| 100 | ~2:1 (67/33) | Higher wins ~2x games |
| 200 | ~4:1 (80/20) | Lopsided |

---

## Race Length Impact

- **Single game:** Higher variance; upset more likely.
- **Race to 5:** Moderate variance.
- **Race to 7–9:** Typical tournament; win prob stabilizes.
- **Race to 11+:** Lower-rated player's win prob decays further.

---

## Fair Matchup Rules

From `api/services/fargo_handicap.py` and External Pool analysis:

- **Every 40 pts** = −1 rack from lower-rated player's race.
- **Max reduction:** −3 racks (winners), −2 (losers).
- **High-rated bonus:** 680–740 → +1 rack; 741+ → +2 racks for higher-rated player.
- **Reject lopsided matchups:** Higher-rated player must not need &gt;3× games of lower-rated player.

---

## Fair Match Calculator

To suggest a race length for two ratings:

1. **API:** `GET /api/tournaments/matches/{match_id}/calculate-handicap` (uses `fargo_handicap.calculate_handicap`).
2. **Apply handicaps:** `POST /api/tournaments/{tournament_id}/apply-fargo-handicaps`.

Or compute manually: `diff = abs(r1 - r2)`; `rack_adj = min(diff // 40, 3)`; apply to lower-rated player's race.

---

## Replace A/B/C Handicaps

Fargo-based race lengths replace arbitrary A/B/C handicaps. Use rating-gap → fair race (e.g. race-to-10, race-to-7, race-to-5) from the handicap calculator instead of letter grades.
