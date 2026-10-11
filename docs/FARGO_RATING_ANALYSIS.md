# Fargo Rating System — Algorithm Analysis

Analysis of the Fargo rating system based on content from [fargorate.com](https://fargorate.com), scraped for integration reference.

## Source

- **Scraped content**: `Rankings-Bot/data/fargorate_scrape/`
- **Integration code**: `Rankings-Bot/api/services/fargo_client.py`

## How Fargo Ratings Work

Fargo ratings are **ELO-type maximum likelihood ratings** for pocket billiards (8-ball, 9-ball, 10-ball). The system computes the optimum set of ratings that best predict the outcome of all games across all players.

### Core Principles

1. **Relative performance** — Skill is inferred from who beats whom, not from absolute measures.
2. **Global optimization** — A global optimization couples all players worldwide on the same scale.
3. **Daily updates** — Ab initio global optimizations run every day at 6:00 AM GMT.

### Win Probability vs Rating Difference

Ratings are on a **logarithmic scale**. For each 100-point gap, the higher-rated player is twice as likely to win a game.

| Rating difference | Win ratio (stronger : weaker) |
|-------------------|-------------------------------|
| 0                 | 1:1 (equal)                   |
| 34                | 5:4                           |
| 50                | 7:5                           |
| 100               | 2:1                           |
| 200               | 4:1                           |
| 300               | 8:1                           |
| 400               | 16:1                          |

### Fair Match Handicaps (stronger goes to 9)

| Rating difference | Weaker player goes to |
|-------------------|------------------------|
| 17                | 8                       |
| 36                | 7                       |
| 58                | 6                       |
| 85                | 5                       |
| 117               | 4                       |
| 158               | 3                       |
| 217               | 2                       |
| 317               | 1                       |

### Rating Scale (approximate)

| Rating | Skill level |
|--------|-------------|
| 800    | Top world-class (< 20 worldwide) |
| 700    | Top regional US, world-class female |
| 600    | ~30 per million population |
| 500    | Median league player, ~5% runouts |
| 400    | ~1% runouts |
| 300    | Common league level |
| 200    | Beginner, modestly coordinated |
| 100    | Beginner, somewhat uncoordinated |

### Robustness

- **Robustness** = number of games contributing to a player’s rating.
- **Established rating** = 200+ games.
- Players with &lt; 200 games may have their rating blended with a **starter rating** (prior/estimate).

### Games Included

- 8-ball, 9-ball, 10-ball on 9-foot or 7-foot tables.

### Recency

- Weight of a match toward a player’s rating **diminishes over time**.
- More recent matches have greater influence.

## Implementation Notes for Integration

The project does **not** recompute Fargo ratings locally. It:

1. **Fetches** ratings from FargoRate APIs and dashboard.
2. **Syncs** ratings into the `rankings` table via `fargo_client.py`.
3. **Uses** FairMatch scraping for per-player lookups when no API is configured.

### External Data Sources

- `api.fargorate.com/v1` — bulk ratings by org (returns 404 for some orgs).
- `dashboard.fargorate.com/api` — Top 100 World/USA/World F/M lists.
- `fairmatch.fargorate.com` — per-player search (via Selenium scraper).

### ELO-Type Formula (for reference)

The public site does not publish the exact formula. Typical ELO-style win probability:

```
P(A beats B) = 1 / (1 + 10^((R_B - R_A) / 400))
```

A 100-point difference corresponds to roughly a 2:1 win ratio, which is consistent with a scale factor around 100–120 (instead of the chess 400).

## References

- [FargoRate.com](https://fargorate.com)
- Scraped content: `data/fargorate_scrape/`
- Project: `api/services/fargo_client.py`, `api/services/fairmatch_scraper.py`
