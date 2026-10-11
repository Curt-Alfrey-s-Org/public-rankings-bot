# Lower Priority Roadmap — Implementation Plan

**Status:** Planned. High and medium priority items are complete. These are deferred until needed.

---

## 1. League Management

**Reference:** External pool vendor league manager — `https://leagues.digitalpool.com`

**Scope:**
- `leagues` table: id, name, org_code, season_start, season_end, created_at
- `league_teams` table: league_id, team_name, captain_player_id
- `league_team_members` table: team_id, player_id, role
- `league_matches` table: home_team_id, away_team_id, scheduled_at, result
- API: CRUD for leagues, teams, match scheduling
- Frontend: League standings, team roster, schedule view

**Effort:** ~2–3 weeks

---

## 2. Tour/Series Support

**Scope:**
- `tours` table: id, name, year, description
- `tour_stops` table: tour_id, tournament_id, stop_number, points_multiplier
- Series points: aggregate points across stops; configurable per-tour formula
- API: GET /tours, GET /tours/{id}/standings
- Frontend: Tour standings, stop calendar

**Effort:** ~1–2 weeks

---

## 3. Round Robin / Group Stage

**Scope:**
- Extend `tournament_manager` to support `format: "round_robin"` or `"groups"`
- Round robin: N×(N-1)/2 matches per group; standings by wins/points
- Group stage: groups feed into knockout (e.g. top 2 advance)
- Bracket generation for round robin: generate all pairings
- API: Same tournament endpoints; format field determines behavior

**Effort:** ~2 weeks

---

## 4. Native Mobile Apps

**Scope:**
- Expo/React Native app in `mobile/` (or separate repo)
- EAS build for iOS/Android
- Reuse API; mobile-specific UI for rankings, tournaments, bracket viewer
- Push notifications via Expo
- See PRODUCTION_AND_IOS_READINESS.md for TestFlight steps

**Effort:** ~3–4 weeks (initial)

---

## 5. Multi-Language Support (i18n)

**Scope:**
- react-i18next or similar for frontend
- Translation files: en, es, de, fr, zh, etc. (14+ per External Pool)
- API: Accept `Accept-Language`; return localized strings where applicable
- Database: Store display names in default locale; optional translations table

**Effort:** ~2–3 weeks (framework + initial languages)

---

**When to start:** After production is stable and core features are validated by users.
