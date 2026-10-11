# Mobile App Migration — Expo Removed, Pure React Native at Root

**Date:** March 15, 2026

---

## What Changed

- **Removed:** `mobile/` directory (Expo-based React Native app)
- **Added:** Pure React Native app at project root (`src/`, `app.json`, `babel.config.js`, `index.js`, `metro.config.js`, `package.json`)

---

## Why

- User requested: "the ios app IS NOT an expo app, delete any ref and code pertaining to expo...the app is a standard ios app"
- iOS simulator showed grey box with tabs instead of web-app-like UI
- Goal: Visual and functional parity with web app; standard iOS/Android native builds

---

## New Structure

```
rankings-bot/
├── app.json
├── babel.config.js
├── index.js
├── metro.config.js
├── package.json
└── src/
    ├── App.tsx
    ├── config.js
    ├── api/
    │   └── rankings.js
    └── screens/
        ├── HomeScreen.js
        ├── RankingsScreen.js
        ├── SettingsScreen.js
        ├── TournamentHistoryScreen.js
        ├── PlayerPerformanceScreen.js
        └── HotStreakScreen.js
```

---

## Run (Dev)

```bash
cd /home/ansible/rankings-bot
npm install
npm start
# In another terminal:
npx react-native run-ios   # or run-android
```

---

## Docs to Update

- `docs/INDEX.md` — Mobile app entry (was `mobile/README.md`)
- `docs/WEB_AND_MOBILE_CHECKLIST.md` — Native dev now uses root, not `mobile/`
- `docs/PRODUCTION_READINESS.md`, `docs/PRODUCTION_AND_IOS_READINESS.md` — EAS/mobile references
- `docs/MOBILE_APP_EXPANSION.md`, `docs/APP_NOOB_CHECKLIST.md` — Path references

---

## See Also

- [IOS_SWIFT_NEXT_STEPS.md](IOS_SWIFT_NEXT_STEPS.md) — Native Swift app option
- [IOS_RANKINGS_INTEGRATION.md](IOS_RANKINGS_INTEGRATION.md) — iOS rankings feature
- [CHANGELOG_20260315_SESSION2.md](../CHANGELOG_20260315_SESSION2.md) — Full change list
