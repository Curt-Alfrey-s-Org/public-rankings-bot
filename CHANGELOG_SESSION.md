# Changelog — Session (March 2026)

## Fargo rating history & retention
- **Migration 039**: Added `fargo_rating_history` table (Alembic) to keep previous Fargo ratings when updated.
- **fargo_client**: When updating a player’s Fargo (sync, manual import), the previous value is stored in `fargo_rating_history` before updating.
- **Player Performance API**: Historical-ratings endpoint now merges Fargo from `fargo_rating_history` and from `rankings` snapshots (scraped archives); supports "First Last" and "Last, First" name variants for rankings.

## Player Performance (frontend)
- **Fargo chart**: New “Fargo rating over time” chart beside the ranking progress chart; data from archives + rankings snapshots.
- **Super admin — All players**: Super admins see an “All players — click to view history” section with filter and player buttons; clicking a player shows that player’s full performance view.
- **URL param**: `/player-performance?player=Name` (admin/super_admin) opens that player’s performance.
- **Migration + seed script**: `scripts/run_migration_and_seed.sh` sources `.env`, runs `alembic upgrade head`, then `scripts/seed_est_from_placement.py`; `seed_est_from_placement.py` prints a startup message for feedback.

## Rankings table (super-admin-only columns)
- **RankingsTable**: New prop `isSuperAdmin`; columns Est. Confidence, Est. Robustness, Live Est. Rating, ALFa Rating are shown only when `isSuperAdmin` is true.
- **Rankings page**: Passes `isSuperAdmin` from `useAuth()` to `RankingsTable`.

## Tournament History
- **View History**: Shown for admins for any player; also shown for the current user when the result row is their own player (using `/api/player-performance/me`).
- **Open in Player Performance**: In the player history view, admins see an “Open in Player Performance →” link to the full performance page for that player.

## Bug fix
- **RankingsTable.tsx**: Fixed `ReferenceError: row is not defined` in EST rating trend cell (use `ranking.est_rating_trend`).

## iOS Swift app — Rankings integration
- **RankingsView.swift**: Full rankings UI with menu/table modes, dark theme (RankingsTheme), felt green accents, hero block, search (client-side filter by player name/country), card-style list, pull-to-refresh, two-decimal points. Removed `.textInputAutocapitalization(.never)` to fix build (no member / cannot infer `.never`).
- **RankingsMenuData.swift**: Drill-down structure (WPBA, WPA, Heyball, Artistic and submenus) matching web.
- **APIClient.swift**: `fetchRankings(system:limit:offset:)` calling `GET /api/v1/rankings/by-system/{system}`.
- **Docs**: `docs/IOS_RANKINGS_INTEGRATION.md` added for iOS Rankings feature and build fix.

## Other
- **rating_archive_service**: Corrected Fargo archive success log message (was `logger.debug(".2f")`).
- **database**: `get_database_manager` imported in `player_performance` routes for Fargo enrichment query.
