# Changelog — March 15, 2026 (Session 2)

**Branch:** main  
**Scope:** WPBA rankings 500 fix, duplicate column fix, Expo removal, pure React Native migration

---

## Summary

- **Backend:** Fixed 500 error on rankings/wpba/overall (SQL schema compatibility)
- **Frontend:** Fixed duplicate "player name" column in rankings table
- **Mobile:** Removed Expo-based mobile app; added pure React Native app at project root
- **Web:** Responsive layout, safe-area, dashboard, and styling updates

---

## Backend & Database

### postgres_manager.py
- **players_by_name CTE:** Adjusted for tournament schema compatibility
  - `full_name`: Use `LOWER(TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')))` instead of `LOWER(TRIM(name))` (column `name` does not exist)
  - `fargo_score`: Use `MAX(fargo_score)` instead of `MAX(COALESCE(fargo_score, fargo_rating))` (column `fargo_rating` does not exist)
  - Optional enrichment columns (`alfa_rating`, `fargo_robustness`, `est_rating`, `est_rating_confidence`, `est_rating_robustness`, `est_rating_trend`): Replaced with `NULL::...` literals where columns absent in tournament schema

---

## Frontend (Web)

### RankingsTable.tsx
- Filter out `player_name` column to prevent duplicate "Player Name" columns (API returns both `name` and `player_name`)

### Other frontend updates
- **App.css, App.tsx, index.css:** Safe-area, viewport, responsive layout
- **ConnectionStatus.tsx, DraggableDashboard.tsx:** Dashboard and layout updates
- **Home.tsx, Rankings.tsx:** Page layout and responsive behavior

---

## Mobile / React Native

### Removed (Expo mobile app)
- **mobile/** directory deleted entirely
  - Expo app, config, assets, screens, API clients, auth, navigation
  - See `docs/MOBILE_APP_MIGRATION.md` for migration notes

### Added (Pure React Native at root)
- **Root-level config:** `app.json`, `babel.config.js`, `index.js`, `metro.config.js`, `package.json`
- **src/App.tsx:** Main app with React Navigation (Bottom Tabs, Drawer, Native Stack)
- **src/config.js:** API base URL config
- **src/api/rankings.js:** Rankings API client (Axios)
- **src/screens/:** HomeScreen, RankingsScreen, SettingsScreen, TournamentHistoryScreen, PlayerPerformanceScreen, HotStreakScreen

**Design:** Styling matches web app (slate-950, slate-800, sky-500) for visual parity.

**Run:** `npm install && npm start` then `npx react-native run-ios` or `run-android` (requires native iOS/Android setup).

---

## Documentation

- **CHANGELOG_20260315_SESSION2.md** (this file)
- **docs/MOBILE_APP_MIGRATION.md** — New docs for mobile/ removal and pure React Native migration

---

## Files Changed

| Type | Path |
|------|------|
| Modified | database/postgres_manager.py |
| Modified | frontend/src/App.css, App.tsx, index.css |
| Modified | frontend/src/components/ConnectionStatus.tsx, DraggableDashboard.tsx, RankingsTable.tsx |
| Modified | frontend/src/pages/Home.tsx, Rankings.tsx |
| Deleted | mobile/* (entire directory) |
| Added | app.json, babel.config.js, index.js, metro.config.js, package.json |
| Added | src/App.tsx, src/config.js, src/api/, src/screens/ |

---

## Next Steps

- Run `npm install` at project root for React Native dependencies
- Configure iOS/Android native projects if needed (`npx react-native init` or manual setup)
- Update docs: INDEX.md, WEB_AND_MOBILE_CHECKLIST.md, PRODUCTION_READINESS.md, etc., to reference new root-level mobile structure
