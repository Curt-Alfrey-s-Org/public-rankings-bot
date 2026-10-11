# Rankings Bot - React Frontend

Modern React + Vite frontend for Rankings Bot (WPBA/WPA rankings display).

## Setup

### Prerequisites
- Node.js 18+
- npm

### Install and run

```bash
npm install
npm run dev
# or: npm start
```

Open the URL Vite prints (e.g. http://localhost:5174). The app talks to the API at `http://localhost:8003` by default.

## Rankings UI

- **Rankings** (default route): WPBA/WPA tabs, search, sortable table, pagination, Export CSV, Refresh, last-updated time.
- **Player detail**: Click a row to open a modal with current rank/points and history for both associations.
- **Settings**: Appearance and app settings.
- **Logs**: API logs viewer.
- **System**: Health and self-test.

### Key components

| Path | Purpose |
|------|--------|
| `src/pages/Rankings.tsx` | Main rankings page (tabs, search, pagination, refresh, export). |
| `src/components/RankingsTable.tsx` | Sortable table (rank, name, country, points); desktop + mobile layout. |
| `src/components/PlayerDetailModal.tsx` | Modal for one player’s WPBA/WPA current + history. |
| `src/api/rankings.ts` | API client: `getWPBA`, `getWPA`, `getPlayer`, `refresh`, `getLastUpdate`. |

### Project structure

```
frontend/
├── src/
│   ├── components/     # RankingsTable, PlayerDetailModal, Sidebar, etc.
│   ├── pages/          # Rankings, Settings, Logs, System
│   ├── api/            # rankings.ts, client.ts, system, etc.
│   ├── hooks/          # useBotStatus, useWebSocket
│   └── App.tsx
├── public/
└── package.json
```

## API

- **Dev:** frontend expects API at `http://localhost:8003` (see `src/api/client.ts`).
- **Production:** same origin or set base URL via env if needed.

## Scripts

- `npm run dev` / `npm start` – dev server (Vite, port 5174)
- `npm run build` – production build to `dist/`
- `npm run preview` – serve production build
