# Changelog — `tournament-overhaul` branch (2026-04-10)

This document summarizes work on branch **`tournament-overhaul`** relative to **`origin/main`** (merge-base snapshot at documentation time: `6671000` — docs: AI inline doc hooks).

## Backup

Git **backup branch** (same commits as `tournament-overhaul`, including this changelog):

- **`backup/tournament-overhaul-20260410`**

Optional tag: `git tag archive/tournament-overhaul-20260410 <commit>`.

## Commits (newest first)

| Commit     | Summary |
|------------|---------|
| `f339b0a` | Test Center overhaul: bracket engine, wizard parity, wizard test-flag cleanup |
| `bcd6221` | WIP: tournament creation overhaul + prep for test center work |

---

## `bcd6221` — Tournament creation overhaul (WIP)

High-level themes:

- **Bracket templates, association scoping, game-type rules** in the tournament wizard flow.
- **API routes and models** updates for tournaments, rankings scope, tournament history, users, CSV import, etc.
- **Alembic:** migrations `051_wpa_women_dynamic_ranking_systems`, `052_bracket_templates_tournament_association`.
- **`api/ranking_scope.py`** — new ranking-scope logic.
- **Frontend:** large **TournamentWizard** and related pages (DataInput, Rankings, SettingsAdmin, Sidebar, TestCenter stub, App routes); tournament API client updates.
- **Docs:** INDEX, runbooks (e.g. rankings refresh), scraper/UI map, env vars, deployment cross-links.
- **Removed or slimmed:** many legacy **pytest** files, **Playwright** e2e config and specs, **GitHub Actions** workflow files (`tests.yml`, `ci-grok-suggest-fix.yml`), and assorted one-off test scripts — aligned with repo note in INDEX that pytest suite is not the current quality gate (see `docs/INDEX.md` Quality checks).

*Full file list:* `git show --stat bcd6221`

---

## `f339b0a` — Test Center overhaul

- **`api/services/bracket_engine.py`** — bracket generation (single elimination, winners-side double-elim labeling).
- **`api/routes/test_tournaments.py`** — expanded test-tournament API (real bracket generation, advancement, `race_to` from match/row, admin/super_admin on mutating routes, reset-database, bracket-tree, simulate-all-remaining, add player; schema columns via ALTER where needed).
- **`database/schema_postgres.sql`** — test tournament association/bracket columns.
- **`api/routes/tournament_wizard.py`** — reduced surface; wizard persistence behavior updated.
- **Frontend:** **TestCenter** UI (association, templates, coach panel, WPBA game lock, registration search/add player, bracket rounds, simulate all); **test API client** updates; **useTestCenterReset** calls reset API; **TournamentWizard** / **useTournamentPersistence** adjustments; **TournamentSetup** page removed; wizard embedded path simplified.
- **Tests:** `tests/backend/test_bracket_engine.py`.

*Full file list:* `git show --stat f339b0a`

---

## Merge / review notes

- **Scope:** This branch is large (~260 files touched vs `main`); includes intentional removal of prior automated test and CI assets. Review merges with that in mind; restore or replace CI before relying on GitHub Actions for gates.
- **Database:** Apply migrations through the **same app image** as production per project standards (`alembic upgrade head` in container context).
- **Deploy:** Use the project’s unified deploy path ([docs/PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md), `./scripts/full_deploy.sh` as documented).

---

## After this doc

- Changelog committed on `tournament-overhaul`.
- Remote: `git push -u origin tournament-overhaul` (first publish of this branch).
