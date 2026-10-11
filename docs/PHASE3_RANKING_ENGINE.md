# Phase 3: Ranking Engine

Phase 3 adds **movement detection** and **trend/history APIs** so you can see how rankings change over time and report on rank/points movement.

## Capabilities

- **Rank over time** — Player history (rank and points by snapshot date) is exposed via the existing **Player** endpoint and the **Snapshots** endpoint. The Rankings UI uses this in the player detail modal.
- **Movement** — When new snapshots are saved (e.g. after **Refresh** or scheduled refresh), the backend compares the new snapshot to the previous one and records changes in the `ranking_changes` table. Change types: `rank_up`, `rank_down`, `points_change`, `new_player`.
- **Movement view** — The **Movement** page in the web app (Menu → Movement) shows recent ranking changes per system (WPBA / WPA) with player name, change type, old → new rank/points, and date.

## API for reporting

All endpoints are under `/api/rankings/`. No auth required for read-only endpoints unless noted.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/rankings/player/{player_name}` | GET | Player data and **history** (WPBA and WPA) — rank/points over time. |
| `/api/rankings/snapshots` | GET | Query: `system=WPBA|WPA`, `limit=30`. Returns list of **snapshot dates** (newest first) for trend views. |
| `/api/rankings/movement` | GET | Query: `system=WPBA|WPA`, `limit=50`. Returns **recent ranking changes** (movement) for the system. |
| `/api/rankings/wpba`, `/api/rankings/wpa` | GET | Latest rankings with pagination. |
| `/api/rankings/last-update` | GET | Last snapshot date per system. |
| `/api/rankings/quality` | GET | Data quality checks (duplicates, missing/invalid fields, point consistency). |
| `/api/rankings/audit` | GET | **Director/Admin only.** Recent audit log (who submitted what). |
| `/api/rankings/refresh` | POST | **Admin only.** Trigger scrape and save new snapshots (and movement). |
| `/api/rankings/import` | POST | **Director/Admin only.** Bulk import placeholder (501). |

### Movement response shape

`GET /api/rankings/movement?system=WPBA&limit=50` returns:

```json
{
  "system": "WPBA",
  "movement": [
    {
      "player_name": "Player Name",
      "ranking_system": "WPBA",
      "old_rank": 5,
      "new_rank": 3,
      "old_points": 120.5,
      "new_points": 135.0,
      "change_date": "2026-02-01",
      "change_type": "rank_up"
    }
  ]
}
```

`change_type`: `rank_up`, `rank_down`, `points_change`, `new_player`. For `new_player`, `old_rank` and `old_points` are null.

### Snapshots response shape

`GET /api/rankings/snapshots?system=WPA&limit=30` returns:

```json
{
  "system": "WPA",
  "snapshot_dates": ["2026-02-01", "2026-01-28", "2026-01-25", ...]
}
```

Use these dates with ranking data or player history to build trend views (e.g. “rank as of date X”).

## Implementation notes

- Movement is computed in **database/db_manager.py**: after each `save_rankings`, `_detect_and_save_changes(system, snapshot_date)` runs and inserts into `ranking_changes`.
- Schema: **database/schema.sql** includes `ranking_changes` and `audit_log`; **setup.sh** initializes the DB from this schema so all tables (including Phase 2.5 and Phase 3) are created on a fresh run.
