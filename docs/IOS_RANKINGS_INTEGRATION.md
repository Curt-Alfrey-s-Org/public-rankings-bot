# iOS Swift App — Rankings Integration

Summary of the Rankings feature and UI added to the Pro Billards Software Swift app, aligned with the web app.

---

## Overview

- **Full rankings drill-down**: Top level (WPBA, WPA, Heyball, Artistic) with submenus and leaf ranking types matching the web.
- **API**: `GET /api/v1/rankings/by-system/{system}` used for any ranking system via `APIClient.fetchRankings(system:limit:offset:)`.
- **UI**: Dark theme, felt green accents, card-style layout, hero block, search, and list with pull-to-refresh.

---

## Files

| File | Purpose |
|-----|--------|
| `RankingsView.swift` | Rankings screen: menu mode, table mode, theme, search, list, row styling. |
| `RankingsMenuData.swift` | Drill-down structure (top level + submenus and leaf ranking types). |
| `APIClient.swift` | `fetchRankings(system:limit:offset:)` calling by-system endpoint; login, health. |
| `MainTabView.swift` | Tab bar including Rankings. |
| `LoginView.swift` / `AuthState.swift` | Auth and token storage. |

---

## Theme (RankingsTheme)

- Background: slate-950–style.
- Text: slate-50 (primary), slate-400 (muted).
- Felt: dark green for accents, borders, top-3 tint.
- Cards: slate-900/800 gradient, rounded, felt border.
- Buttons: dark slate bg, felt/purple border, white bold text.

---

## Features

- **Menu mode**: Card with “Choose category” / “Choose ranking”, Back, list of menu options (min height 48pt).
- **Table mode**: Back, hero (“🏆 {title} Tournament Rankings”, “X professional players”), search field, client-side filter by player name and country, card-style list, pull-to-refresh.
- **RankingRowView**: Felt tint and medal styling for top 3, rank in felt, name/country, metadata line, points with two decimals (`"%.2f"`).

---

## Build Fix (March 2026)

- **Issue**: `RankingsView.swift` line 231 — `Value of type 'some View' has no member 'textInputAutocapitalization'` and `Cannot infer contextual base in reference to member 'never'`.
- **Cause**: `.textInputAutocapitalization(.never)` not available or not inferred on the deployment target / modifier chain.
- **Fix**: Removed `.textInputAutocapitalization(.never)` from the search `TextField`. Search still works; `.autocorrectionDisabled()` kept. Keyboard may auto-capitalize on some devices.

---

## API

- Rankings by system: `GET /api/v1/rankings/by-system/{system}` (e.g. `wpba-women`, `wpa-men`, `heyball-women`, `artistic`).
- Response: `{ total, count, rankings: [{ player_name, rank, points, country, ... }], association? }`.

See `docs/IOS_SWIFT_NEXT_STEPS.md` for app structure and next steps.
