# Mobile app expansion plan

The native mobile app (Expo/React Native in `mobile/`) currently has **Rankings** and **Settings (Log out + Open full website)**. This doc outlines how to add the rest of the web app’s features with a clear layout and where to start.

---

## 1. How other apps handle many menu items

Apps with many sections (e.g. 8–12 items) typically use one or more of:

| Pattern | Description | Examples |
|--------|-------------|----------|
| **Drawer (hamburger)** | Main content full-screen; swipe or tap menu icon to open a side panel with all links. Panel can collapse/expand. | Gmail, Slack, many enterprise apps. |
| **Bottom tab bar (4–5 items) + “More”** | Primary actions in a fixed bottom bar; “More” opens a list or second screen with the rest. | iOS Settings (older), many banking apps. |
| **Bottom tabs + drawer** | Bottom bar for 4–5 main sections (Home, Rankings, Tournaments, …); drawer for full menu, profile, settings. | Common in sports/league apps. |
| **Collapsible sections** | One long menu with section headers (e.g. “Rankings”, “Tournaments”, “Admin”) that expand/collapse. | Settings-style screens. |

**Recommendation for this app:** Use **drawer (hamburger) for the full menu** so directors see the same structure as the web sidebar (Home, Rankings, Movement, Tournaments, Player Performance, AI Coach, Head-to-Head, Covert Ops, Settings). Add a **bottom bar** for the 3–4 most-used items (e.g. Home, Rankings, Tournaments, Settings) so key screens are one tap away. Drawer content can mirror `frontend/src/components/Sidebar.tsx` (filter by role: admin-only items for admin/super_admin).

**Hiding / expanding:** Drawer is “hidden” by default and “expanded” when opened (overlay or push). On tablet (e.g. `useWindowDimensions().width >= 600`) the drawer can be optionally always-visible (split layout) for more space.

---

## 2. Phone vs tablet: Tournament Wizard and director tools

- **Tournament Wizard, New Tournament, Director mode, Score keeper** are not practical on a small phone screen. The **web app** shows a message in the Tournaments section on narrow viewports: *“Tournament Wizard, New Tournament, Director mode, and Score keeper work best on a tablet or desktop.”*
- **Mobile app:** When we add a Tournaments section, either:
  - **Option A:** Show a single “Tournaments” screen that lists History, Upcoming, Current, etc., with a banner: *“For Tournament Wizard and director tools, use a tablet or browser.”* Tapping “New Tournament” or “Director mode” can open the full website in the browser or show the same message.
  - **Option B:** Omit Wizard / Director / Score keeper from the native app entirely on phone; only add them for tablet (e.g. in a future “tablet layout” that shows more).

Start with **Option A** so directors see the message and can open the site from the app (we already have “Open full website” in Settings).

---

## 3. Where to start (phased plan)

| Phase | Scope | Notes |
|-------|--------|------|
| **0 (done)** | Rankings, Settings (Log out, Open full website), bottom tabs, safe areas, pull-to-refresh. | Current state. |
| **1** | **Drawer menu + Home** | Add a drawer (hamburger) that lists the same items as the web sidebar (Home, Rankings, Movement, Tournaments, Player Performance, AI Coach, Head-to-Head, Covert Ops [admin], Settings). Implement **Home** screen (e.g. news links, upcoming tournaments summary). Keep bottom bar: Home, Rankings, Settings (and optionally “More” that opens the drawer). |
| **2** | **Movement + Tournaments list** | Movement screen (recent ranking changes). Tournaments: one screen with links or list (History, Upcoming, Current, etc.) **plus the “use tablet or browser” message** for Wizard/Director/Score keeper. |
| **3** | **Player Performance, Head-to-Head** | Read-only or simplified versions; reuse API. |
| **4** | **AI Coach, Covert Ops, full Settings** | AI Coach: upload or link to flow. Covert Ops: admin-only. Settings: sub-pages (appearance, health, etc.) or “Open full website” for advanced. |
| **5** | **Tablet layout (optional)** | Use `width >= 600` (or similar) to show drawer always visible, more columns, and optionally Tournament Wizard/Director on tablet. |

**Start with Phase 1:** drawer + Home screen. That establishes the navigation pattern and gives directors one place to see the full menu.

---

## 3b. Director tab (web, tablet, mobile)

Add a new **top-level** menu item **Director** (same level as Home, Rankings, Tournaments, etc.) on web, tablet, and mobile. Move **all** director-related items into it:

| In Director tab | Description |
|----------------|-------------|
| Data input | Enter or upload rankings and tournament data (Director/Admin) |
| Director mode | Bracket, tables, call table, DQ, assign, enter scores |
| Score keeper mode | My table — enter scores and run timers |
| New Tournament | Tournament Wizard (create new tournament) |
| **Tournament Player Management** | Manage tournament players |

**Tournaments** tab then contains only: Tournament History, Future Tournaments, Current Tournaments, Bracket (view), Leaderboard. Mobile still has bracket info, history, leaderboard, and score keeper (under Director or via Tournaments as appropriate). See CHECKLIST.md and Roadmap.md.

---

## 4. Technical references

- **Drawer in React Navigation:** [Drawer navigator](https://reactnavigation.org/docs/drawer-navigator/) (install `@react-navigation/drawer`). Use with a stack or bottom tabs so the main screens stay the same and the drawer opens over or beside them.
- **Responsive layout:** `useWindowDimensions()` (already used in `mobile/App.js`). Use a breakpoint (e.g. 600px) to switch between “phone” (drawer overlay) and “tablet” (drawer always visible if desired).
- **Web sidebar structure:** `Rankings-Bot/frontend/src/components/Sidebar.tsx` — `allMenuItems` and filtering by `isAdmin` / `isSuperAdmin` for Covert Ops. Mirror this in the drawer menu items and roles.

---

## 5. Checklist / roadmap linkage

- **CHECKLIST.md** (repo root): “Mobile app expansion” section with Phase 1–4 items; check off as screens are added.
- **Roadmap.md:** Add a short “Mobile app expansion” phase that points to this doc and the checklist.
- **Tournaments (web):** Message for small screens is in `frontend/src/pages/TournamentsLayout.tsx` (directors see “use tablet or browser” on phone).

---

## 6. Summary

- **Tournament section (web):** Directors on a phone see a message in the Tournaments area: use tablet or browser for Tournament Wizard and director tools.
- **Mobile expansion:** Add a drawer for the full menu and build screens in order: Home → Movement + Tournaments (with message) → Player Performance / Head-to-Head → AI Coach / Covert Ops / Settings.
- **Layout:** Drawer (hamburger) + bottom bar for main items; hide/expand drawer; on tablet optionally keep drawer open and add Wizard/Director later.
- **Where to start:** Phase 1 in this doc (drawer + Home screen); track progress in CHECKLIST and Roadmap.
