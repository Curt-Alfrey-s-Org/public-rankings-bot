# Rankings Bot Updates (Feb 2026)

## Done in this pass

1. **Fargo scraper**
   - Starts from 1st place and works down the list (rank order).
   - Processes **20 players per batch**, **1 second between batches** (configurable via `FARGO_BATCH_SIZE`, `FARGO_BATCH_DELAY_SECONDS`).
   - **Error handling:** Returns a clear message if Fargo rate limit (429) or server not responding; API returns 503 with detail for the UI.

2. **Bracket tab**
   - Fixed "Something went wrong" when selecting a tournament: API response is normalized so frontend gets `round`, `operator_games`, `player2_games`, `winner_player_id`. Error state shows the actual message.

3. **Home button**
   - Added **Home** at the top of the sidebar menu to get back to the dashboard from any tab.

4. **Scrapes every 1 hour**
   - Documented hourly cron in `docs/SCHEDULED_REFRESH.md` and `scripts/cron_refresh_rankings.sh` (e.g. `0 * * * *`).

5. **License # required**
   - Player Management: License # is **required** when adding a player; validation and label "(required to play)" added.

6. **Manual Fargo scrape in admin**
   - Health Dashboard (Admin): **"Run Fargo scrape now"** button to trigger Fargo sync manually; shows success/error (rate limit or server not responding).

---

## Remaining / follow-up

- **Auto-update Players tab from rankings scrape** — After rankings refresh, sync or expose players from rankings so the Players tab shows them (or a "Players from rankings" source).
- **Player performance / Head to head auto-populate** — Ensure these tabs use rankings data and refill after a rankings scrape (or after Fargo sync).
- **Suspend / DQ / edit scores and rankings** — Player Management already has edit and `membership_status` (e.g. suspended). Add: DQ status, and admin inputs to edit player scores/rankings manually.
- **Tablet and mobile** — Ensure layout is responsive (auto-sized, auto-spaced, touch-friendly) so the bot works well on tablets and phones like popular apps.
- **App users and roles** — Add admin UI to create app users and assign roles (auth already has roles; need inputs and list).

---

## Files changed

- `api/services/fargo_client.py` — Batch + delay, `FargoScraperError`, error messages.
- `api/routes/fargo.py` — Sync returns `(updated, error)`; 503 on `FargoScraperError`.
- `frontend/src/api/tournaments.ts` — Normalize matches response (`round`, `operator_games`, etc.).
- `frontend/src/components/Sidebar.tsx` — Home at top of menu.
- `frontend/src/components/BracketViewer.tsx` — Error state with message.
- `frontend/src/features/admin/pages/HealthDashboard.tsx` — Manual Fargo scrape button.
- `frontend/src/pages/PlayerManagement.tsx` — License # required validation and label.
- `docs/SCHEDULED_REFRESH.md` — Hourly cron example.
- `scripts/cron_refresh_rankings.sh` — Comment: hourly example.
