# Fargo Rating History — Design

## Goal

Give each player a **rating history** over the past year (or longer): a time series of Fargo ratings so we can show progress (charts, “rating 90 days ago”, etc.).

## Constraint

The Fargo API and dashboard return **current** rating only. There is no “rating as of date X” API. So we must **record** the rating ourselves on a schedule and retain those snapshots.

---

## Your Schedule — Does It Work?

**Yes.** Your proposed schedule is a good balance of detail and storage:

| Window        | Sampling                         | Purpose                          |
|---------------|----------------------------------|----------------------------------|
| Last 30 days  | **Every day**                   | Fine-grained recent progress     |
| 31–365 days   | **45, 60, 90, 180, 365 days**   | Key milestones in first year      |
| After 1 year  | **Every 6 months**               | Long-term trend without bloat     |

So we **display** history at: D-1, D-2, …, D-30, D-45, D-60, D-90, D-180, D-365, then D-547, D-730, … (6-month steps).

To have “rating 45 days ago” we must have **stored** it 45 days ago. So we need to:

1. **Record** a snapshot every day (when we run Fargo sync).
2. **Retain** all daily snapshots for the last 30 days; for older data, keep only the milestone dates (45, 60, 90, 180, 365 days ago, then 6-month intervals) so the table doesn’t grow forever.

---

## Implementation Outline

### 1. New table: `fargo_rating_history`

```sql
CREATE TABLE IF NOT EXISTS fargo_rating_history (
    id SERIAL PRIMARY KEY,
    player_name VARCHAR(255) NOT NULL,
    ranking_system VARCHAR(32) NOT NULL,   -- e.g. WPBA_Women, WPA_Women
    snapshot_date DATE NOT NULL,
    fargo_rating DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_name, ranking_system, snapshot_date)
);
CREATE INDEX idx_fargo_history_player_system ON fargo_rating_history(player_name, ranking_system);
CREATE INDEX idx_fargo_history_date ON fargo_rating_history(snapshot_date DESC);
```

- One row per (player, system, date).
- `snapshot_date` = the date we recorded the rating (usually “today” when sync runs).

### 2. Record daily

- **When**: Each time Fargo sync runs (e.g. daily cron or “Update Fargo Rating”).
- **What**: For every player that has a `fargo_rating` on the **latest** rankings snapshot, insert (or upsert) one row into `fargo_rating_history` with:
  - `player_name`, `ranking_system` (org), `snapshot_date = today`, `fargo_rating`.
- **Where**: In `sync_fargo_ratings_rate_limited` (or immediately after `update_rankings_with_fargo`), add a call to append today’s ratings to `fargo_rating_history`. Use `INSERT ... ON CONFLICT (player_name, ranking_system, snapshot_date) DO UPDATE SET fargo_rating = EXCLUDED.fargo_rating` so re-runs on the same day just update.

### 3. Retention job (periodic)

- **Goal**: Keep last 30 days as daily; older than 30 days keep only “milestone” dates so we have exactly the points you want (45, 60, 90, 180, 365 days, then every 6 months).
- **How**: Run daily (e.g. after sync). For each `(player_name, ranking_system)`:
  - Keep all rows where `snapshot_date >= today - 30 days`.
  - For `snapshot_date < today - 30 days`, keep only rows where the date is one of the milestones: 45, 60, 90, 180, 365 days ago from today, or 18 months, 24 months, 30 months, … (6-month steps).
- **Implementation**: e.g. “milestone dates” = `today - 45`, `today - 60`, `today - 90`, `today - 180`, `today - 365`, and then `today - (365 + 6*k)` for k = 1, 2, 3, … Delete all other rows older than 30 days.

This gives you exactly the history curve you described without unbounded growth.

### 4. API

- **GET** `/api/fargo/player/{player_name}/history?system=WPBA` (or `WPA`)  
  Returns `{ "history": [ { "date": "YYYY-MM-DD", "fargo_rating": 650 }, ... ] }` ordered by date descending (or ascending for charts).
- Backed by `SELECT snapshot_date, fargo_rating FROM fargo_rating_history WHERE player_name = ? AND ranking_system = ? ORDER BY snapshot_date DESC`.

### 5. Frontend

- Player profile or “Movement” page: chart of `fargo_rating` over time using the history API. Optional: show “30 days ago”, “90 days ago”, “1 year ago” badges.

---

## Summary

| Question | Answer |
|----------|--------|
| Does “every day for 30d, then 45/60/90/180/365d, then every 6 months” work? | **Yes.** Record daily; retain daily for 30d and milestone dates only for older data. |
| Do we need a new table? | **Yes.** Current `rankings` only stores current Fargo (no per-date history). |
| Where do we write? | In/after Fargo sync: append today’s (player, system, date, rating) to `fargo_rating_history`. |
| How to avoid infinite growth? | Retention job: keep last 30 days daily; for older, keep only 45/60/90/180/365d and 6-month intervals. |

If you want, next step is to add the table (e.g. Alembic migration), the append logic in the Fargo sync path, the retention job, and the history API + a small chart on the frontend.
