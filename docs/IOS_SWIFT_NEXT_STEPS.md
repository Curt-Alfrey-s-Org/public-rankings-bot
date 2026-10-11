# Next Steps: Swift iOS App (Tournament Mode iPad-Only)

This doc outlines how to create a **native Swift/SwiftUI** iOS app for Rankings-Bot that reuses the same API, with **tournament mode on iPad only** and **iPhone-optimized** layouts for the rest.

---

## 1. Current State

- **Backend:** FastAPI at `http://127.0.0.1:8003` (local) or your production URL. Auth: `POST /api/v1/auth/login`, then `Authorization: Bearer <token>` for protected routes.
- **Existing mobile:** Pure React Native app at project root (`src/`), no Expo. You can keep it or replace it with a native Swift app.
- **Relevant API surface:** `/api/v1/auth/*`, `/api/v1/rankings/*`, `/api/health`, `/api/tournaments/*`, tournament wizard, director, etc. (see `api/main.py` and route includes).

---

## 2. Device Strategy: iPhone vs iPad

| Feature | iPhone | iPad |
|--------|--------|------|
| Login / auth | ✅ | ✅ |
| Rankings (list, detail) | ✅ Compact list/detail | ✅ Same or split view |
| Events / tournament list | ✅ Read-only list | ✅ Read-only + **Tournament Mode** |
| **Tournament mode** (bracket, draw, score entry, director) | ❌ Hidden | ✅ Only here |
| Settings, profile | ✅ | ✅ |
| AI Coach, Head-to-Head, etc. | ✅ If you include them | ✅ |

**Rule:** Use `UIDevice.current.userInterfaceIdiom == .pad` (or `UITraitCollection`) to show/hide **Tournament Mode** and to choose layout (compact vs regular).

---

## 3. Next Steps to Create the Swift App

### Step 1: New Xcode project

1. **File → New → Project** → **App** (SwiftUI, iOS).
2. **Product name:** e.g. `RankingsBot`.
3. **Bundle ID:** e.g. `com.alfaqd.rankingsbot` (or match existing `com.alfaqd.mobile` if you want one app).
4. **Interface:** SwiftUI. **Language:** Swift. **Storage:** None (add Core Data later if needed).
5. **Devices:** iPhone and iPad (Universal).

### Step 2: API client in Swift

- **Base URL:** From a config (e.g. `Config.apiBaseURL`), pointing to `http://127.0.0.1:8003` for dev or your production URL.
- **Auth:** After login, store token in **Keychain** (e.g. `Security` framework or a small wrapper). Send `Authorization: Bearer <token>` on every request.
- **Endpoints to implement first:**
  - `POST /api/v1/auth/login` (email/username + password → token).
  - `GET /api/v1/health` (sanity check).
  - `GET /api/v1/rankings/wpba` (or the rankings list your web app uses).
  - `GET /api/tournaments/` or the events endpoint you use for the list.
- Use `URLSession` (or async/await) and a shared `APIClient` type that adds the Bearer header and handles 401 (logout/refresh).

### Step 3: App structure (SwiftUI)

- **Root:** `TabView` on iPhone (e.g. Home, Rankings, Events, Settings). On iPad you can use the same tabs and add a **fifth tab or a sidebar entry** for **Tournament Mode** only when `userInterfaceIdiom == .pad`.
- **Conditional Tournament Mode:**
  - In the tab/sidebar configuration, add the tournament-mode destination only when running on iPad:
    - e.g. `if UIDevice.current.userInterfaceIdiom == .pad { ... TournamentModeView() ... }`
  - Or use `horizontalSizeClass` / `UITraitCollection` so that “regular” width (iPad) shows tournament mode; “compact” (iPhone) does not.

### Step 4: iPhone-first screens (what fits on iPhone)

- **Login:** Single screen; small form (email, password, button). Fits any iPhone.
- **Home:** Shortcuts or summary; compact vertical stack.
- **Rankings:** List (scrollable); tap row → detail (push or sheet). Keep cells simple (name, rank, rating) so they fit narrow width.
- **Events:** List of events (name, date, venue); tap → read-only detail. No bracket or score entry here.
- **Settings:** Form (account, API URL for dev, logout). Use `Form` or `List`; works on all sizes.

Design for **compact** width (e.g. 320pt) and safe area; use `ScrollView` + `VStack`/`LazyVStack` so nothing is cut off on small iPhones.

### Step 5: iPad-only Tournament Mode

- **When:** Only present this flow on iPad (idiom or regular horizontal size class).
- **Screens to plan (SwiftUI views):**
  - **Tournament list/dashboard** (director view): list of tournaments you’re running; tap one to open bracket/draw.
  - **Bracket / draw:** Large canvas (scrollable if needed). Use the same API as the web app (e.g. tournament wizard or director endpoints) to load/save rounds, matches, results.
  - **Score entry / match card:** Side panel or modal for entering scores; submit via API.
- **Layout:** Prefer **NavigationSplitView** (sidebar + content + optional detail) or a **master–detail** so list is on the left, bracket/detail on the right. This fits iPad only.

### Step 6: Shared backend and config

- **API base URL:** e.g. in `Config.swift` or `xcconfig`, with a Debug value (`http://127.0.0.1:8003`) and Release value (production). For device testing against Mac, use your Mac’s LAN IP and ensure the API allows that host.
- **Same .env on server:** The app doesn’t read `.env`; the backend does. Your existing `.env` (from 105) is for the API; the Swift app only needs the base URL and (optionally) feature flags.

### Step 7: What to build first (order)

1. **Xcode project** (SwiftUI, Universal).
2. **API client** (base URL, login, token in Keychain, Bearer header).
3. **Login + Health** (login screen, call health after login).
4. **Rankings list + detail** (iPhone-friendly).
5. **Events list** (read-only) on both iPhone and iPad.
6. **Device check:** Hide tournament entry point on iPhone; show on iPad.
7. **iPad Tournament Mode:** One screen that loads tournament data from API (e.g. director or tournament-wizard endpoints), then add bracket UI and score entry.

---

## 4. API Endpoints to Use (reference)

- Auth: `POST /api/v1/auth/login`, `GET /api/v1/auth/me` (with Bearer).
- Health: `GET /api/health` or `GET /api/v1/health`.
- Rankings: `GET /api/v1/rankings/wpba` (and similar for other lists).
- Tournaments/events: See `api/routes/tournaments.py`, `tournament_wizard`, `tournament_history`, and director routes for list/detail/bracket/score submission.

Use the same request/response shapes as the web frontend or Postman so the Swift app stays in sync with the API.

---

## 5. Optional: React Native Instead of Swift

If you prefer to **keep the existing React Native app** and only add iPad vs iPhone behavior:

- Use **Platform** and **Dimensions** (or `useWindowDimensions`) or **react-native-device-info** to get device type.
- **Conditionally render** the Tournament tab (or drawer item) only when `Platform.isPad` or when `Dimensions.get('window').width >= 768`.
- Use responsive layouts (e.g. different column counts or list/detail for wide screens) so iPhone stays single-column and iPad can show tournament mode and split views.

This avoids a second codebase but does not give you “Swift code”; it keeps one React Native codebase with device-aware UI.

---

## 6. Summary

| Goal | Action |
|------|--------|
| **Swift code for iOS** | New SwiftUI app in Xcode; shared API client; token in Keychain. |
| **Tournament mode iPad only** | Show tournament mode tab/screen only when `userInterfaceIdiom == .pad` (or regular horizontal size class). |
| **What fits on iPhone** | Login, Rankings (list/detail), Events (list/detail), Settings; no bracket or director tools. |
| **iPad** | Same as iPhone plus Tournament Mode (bracket, draw, score entry) using existing API. |

If you want, next we can turn this into a short **Swift code sketch** (e.g. `APIClient`, `Config`, and a minimal `ContentView` with device check and one Rankings list screen).
