# Dependencies

All project dependencies are pinned in version-controlled files. The app is not I/O- or CPU-heavy; defaults favor **live updates** (short cache TTLs, frequent refetch).

## Python (Backend)

Production Docker image uses **requirements-api.txt** and **requirements-deps.txt** together.

### requirements-api.txt (FastAPI / API core)

| Package | Purpose |
|--------|---------|
| fastapi | API framework |
| uvicorn[standard] | ASGI server |
| python-multipart | Form/file uploads |
| pydantic[email] | Validation, settings |
| psutil | Process/memory checks |
| websockets | WebSocket support |
| pyjwt | JWT auth |
| passlib[bcrypt], bcrypt | Password hashing |
| python-docx | Director DOCX import |
| httpx | Async HTTP (AI Coach, external APIs) |
| sqlalchemy | ORM |
| psycopg2-binary | PostgreSQL driver |
| redis | Cache/session backend |
| celery[redis] | Background tasks |
| python-dotenv | Env from .env |

### requirements-deps.txt (Scrapers, data, payments)

| Package | Purpose |
|--------|---------|
| requests, aiohttp | HTTP clients |
| cryptography | Crypto utilities |
| httpx | HTTP (shared) |
| alembic | DB migrations |
| sendgrid | Email |
| beautifulsoup4, lxml | HTML parsing |
| selenium | Browser automation (scraping) |
| PyPDF2, pdfplumber | PDF (WPBA rankings) |
| pandas, numpy, openpyxl | Data handling |
| stripe | Payments |

### requirements.txt (Full local dev)

Used for local development. Includes the above plus scipy, scikit-learn, matplotlib, dash, plotly, Pillow, and optional trading/ML libs. **Not** used by the production Docker image.

## Frontend

Dependencies are in **frontend/package.json**. Install with `npm install` in `frontend/`.

### Production dependencies

| Package | Purpose |
|--------|---------|
| react, react-dom | UI |
| react-router-dom | Routing |
| @tanstack/react-query | Data fetching, cache, live refetch |
| axios | HTTP client |
| lucide-react | Icons |
| qrcode.react | QR codes |
| recharts | Charts (e.g. tournament performance trend) |
| zustand | Client state |
| @stripe/react-stripe-js, @stripe/stripe-js | Payments |

### Dev dependencies

TypeScript, Vite, ESLint, Tailwind, PostCSS, Vitest, Testing Library, PWA plugin. See `frontend/package.json` for versions.

## Live-update behavior

- **Backend:** Cache TTLs are short by default (60s). Override with env: `CACHE_TTL_SECONDS`, `CACHE_STALE_TTL_SECONDS` (tournament history, generic cache); `RANKINGS_CACHE_TTL_SECONDS` (rankings list).
- **Frontend:** React Query defaults use short `staleTime` and `refetchOnWindowFocus` so data refreshes when users return to a tab or on a timer.
- **WebSocket:** Live updates (e.g. rankings, cache invalidation) are pushed when data changes; no need to poll heavily.

## Adding or changing dependencies

1. **Python:** Add the package and version to the appropriate file (`requirements-api.txt`, `requirements-deps.txt`, or `requirements.txt`). Run `pip install -r requirements-api.txt -r requirements-deps.txt` (or the relevant file). Update this doc if the dependency is user-facing or operational.
2. **Frontend:** Run `npm install <package>` in `frontend/` so `package.json` and `package-lock.json` are updated. Add the package to the table above if it is a production dependency.
