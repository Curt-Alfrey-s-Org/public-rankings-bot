# Director Tournaments → Rankings (SSOT, No Data Loss)

## Problem

- **rankings** table is the sole source of truth for rank/points (per RANKINGS_DATA_CONSOLIDATION.md).
- **recalculate_rankings** wrote director tournament results to `players` table only, overwriting rankings-sourced data.
- Director tournament data lived in `tournaments` + `tournament_players` but never flowed into `rankings`.

## Solution (No Data Loss)

1. **Sync director tournaments → rankings**: When recalculate is triggered, write results to `rankings` with `ranking_system='LOCAL'`.
2. **Merge at read time**: Leaderboard includes LOCAL when merging; sums points for same player across systems.
3. **Keep recalculate endpoint**: It now triggers sync-to-rankings + sync-players-from-rankings instead of overwriting players.
4. **Result**: Same data, better organized. Rankings is the sole source; players is a cache for screens that read from it.

## Migration

Run `alembic upgrade head` to add `LOCAL` to the rankings table constraint (migration 041).

## Data Flow

```
POST /api/tournaments/rankings/recalculate
    → sync_director_tournaments_to_rankings() writes to rankings (LOCAL)
    → sync_players_from_rankings() reads merged leaderboard, updates players
    → get_leaderboard_from_rankings() merges WPBA/WPA/LOCAL, sums points per player
```

## Tables

| Table | Role |
|-------|------|
| rankings | Source of truth. Fed by: scrapers, PDF/CSV import, director sync (LOCAL). |
| players | Cache/identity. total_points, current_rank synced from merged rankings. |
| tournaments, tournament_players | Director-run events. Source for LOCAL sync. |
