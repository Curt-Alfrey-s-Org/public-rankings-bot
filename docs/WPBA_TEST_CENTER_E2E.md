# WPBA-style Test Center — End-to-end checklist

For the **full billiards tournament lifecycle** (formats, registration, scoring, points, rankings, awards) that ProBilliardsSoftware targets end-to-end, see [BILLIARDS_TOURNAMENT_LIFECYCLE.md](BILLIARDS_TOURNAMENT_LIFECYCLE.md).

**Production New Tournament** (4-step UI, canonical API order on create, Test Center parity goal, AI must use APIs—not UI—and restart from step 1 after errors): [TOURNAMENT_WIZARD_VISUAL_OVERVIEW.md](TOURNAMENT_WIZARD_VISUAL_OVERVIEW.md) § *Production workflow, Test Center parity, and AI automation*.

## Goals and data-flow rules

The **Test Center** is where we run fake tournaments end-to-end so we can
validate every aspect of the bot code that touches tournament creation and
scoring — bracket engine, ratings, rankings, hot streaks, leaderboard, and
tournament history pages — **before** any change affects real data. Once the
test results look correct across all views, that code is promoted to
production, where real tournaments are created and their results feed real
ratings and real rankings.

**Step 1 data flow (WPBA tournaments):**

1. The Test Center API reads the list of **real WPBA player names from the
   production database** (`DATABASE_URL` → `mv_latest_rankings` where
   `ranking_system ILIKE 'WPBA%'`). This is a read-only `SELECT`; nothing is
   ever written back to production.
2. Each real name is copied into the **Test Center database**
   (`TEST_CENTER_DATABASE_URL`) with the literal prefix `"test "` prepended to
   the first-name column, so the display name always renders as
   `"test <name>"` (e.g. `"test John Smith"` or `"test Smith John"`,
   commas/order don't matter).
3. After the names are in the test DB, the admin enters the test tournament's
   **name**, **location**, **tables**, **entry fee**, selects **Double
   Elimination** as the format, and clicks **Next** (the button is labeled
   *Activate Tournament*). This finishes Step 1.

**Hard rules (enforced in code):**

- Test Center code **writes only** to `TEST_CENTER_DATABASE_URL`. The
  production engine (`DATABASE_URL`) is used strictly for `SELECT`s in one
  helper, `TestTournamentManager.import_wpba_players_from_production()`.
- No "test objects" — test tournaments, test players, test matches, test
  rankings rows, test tournament-history rows — may ever be stored in the
  production DB.
- A runtime guard refuses to import from production when
  `DATABASE_URL` and `TEST_CENTER_DATABASE_URL` resolve to the same database.
- `setup_test_tournament` no longer inserts any hard-coded default players, so
  the only path players can enter the test DB is via the `"test "`-prefixed
  copy from production (or explicit admin UI actions).

**After running the test tournament:**

Run the matches (or click **Simulate all remaining**) and review the **Test
Rankings**, **Test Leaderboard**, **Test Hot Streak**, and **Test Tournament
History** sub-tabs to verify the bot is computing ratings, rankings, and all
dependent pages correctly. When the test data looks right, merge the code to
production; from that point real tournaments will update real ratings and
rankings.

**Backend endpoint powering the copy:**

- `POST /api/test-tournaments/import-wpba-players-from-production`
  (admin+). Optional body `{"limit": N}`; defaults to the current test
  tournament's `max_players` (fallback 64). Returns `{copied,
  skipped_duplicates, limit, source_ranking_system}`.
- The same path is used automatically by `auto_fill_players()` whenever the
  test tournament's `ranking_system` starts with `WPBA`, and is auto-triggered
  by the UI after **Activate Tournament** for WPBA tournaments.

---

Use **Settings → Test Center** (admin+) with a running API and Postgres test schema.

## “The Classics USA” scenario (64 players, double elimination)

1. **Reset** (optional): Reset & Cleanup tab → reset test database, or `POST /api/test-tournaments/reset-database`.
2. **Setup (step 1):**
   - Association: WPBA (or your WPBA-tagged association).
   - Bracket template: **64 players** (draw size 64).
   - Name: e.g. `The Classics USA`.
   - Location: `Sparta, TN`.
   - Dates: start `2026-04-15`, end `2026-04-17`.
   - Format: **Double elimination** (full winners + losers + grand final for 64).
   - Max players: **64**; tables: **14**; entry fee: **1000**; prize pool: **20000**.
   - Race to: **8**; grand final race to: **10** (WPBA-style one-set final).
   - Activate tournament.
3. **Registration (step 2):** Click **Seed 64 classics demo** (or fill 64 named players). Seeded players 1–32 get `seed` set for bracket ordering.
4. **Brackets (step 3):** Generate bracket — expect **126** matches (63 winners + 62 losers + 1 grand final).
5. **Dashboard:** **Simulate all remaining** — should run until the tournament status is **completed**.
6. **Leaderboard:** Check finishing order, **placement** rank, and **WPBA R-points** (banded 1–24 per Iron City / repo table).

## Isolated “Test Data” views (same UI as production)

After a test tournament **completes**, results are persisted into the **test center** Postgres (`tournament_history`, `tournament_results`, `rankings`, `players`) so read-only mirrors can serve the same pages against test data only.

Use the **Test Rankings**, **Test Leaderboard**, **Test Hot Streak**, and **Test Tournament History** sub-tabs (after the separator on the tab bar). They render the **same** `Rankings`, `Leaderboard`, `HotStreak`, and `TournamentHistory` components as production, with API prefixes under `/api/test-center/...` (`frontend/src/contexts/ApiPathContext.tsx`). **Reset & Cleanup** clears both `test_*` workflow tables and these view tables.

## API reference (auth: admin JWT)

- `POST /api/test-tournaments/setup` — body includes `location`, `start_date`, `end_date`, `prize_pool`, `race_to_final`, `points_structure` (optional; defaults to WPBA classic bands).
- `POST /api/test-tournaments/seed-classics-demo-players` — 64 demo players.
- `POST /api/test-tournaments/generate-bracket` — builds double-elim for **64** only when `format` is `double_elimination`.
- `POST /api/test-tournaments/simulate-all-remaining` — fair simulation in dependency order.

Read-only mirrors for embedded tabs (same handlers as production, different engine): `GET /api/test-center/rankings/*`, `GET /api/test-center/tournaments/*`, `GET /api/test-center/tournament-history/*` — see `api/routes/test_center_views.py`.

## Official WPBA references

- Rules and point chart: [wpba.com/rules](https://wpba.com/rules) (9-ball PDF + point system image).
- Full double elimination for other field sizes is not implemented yet (`ValueError` from bracket engine).
