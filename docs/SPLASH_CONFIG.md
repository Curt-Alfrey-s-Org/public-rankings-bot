# Splash Configuration — Single Source of Truth

**Purpose:** Prevent splash title and config from flipping between values. One source of truth, no fallbacks.

---

## Single Source of Truth

**`config/splash_config.json`** is the only source for splash screen configuration (title, media, type).

- **Title:** Must be `"Pro Billiards Software"` (or whatever is in the config). Do not hardcode alternatives elsewhere.
- **API:** Reads from `config/splash_config.json`. No default fallback when file is missing or invalid.
- **Frontend:** Uses only what the API returns. No fallback when the API fails.

---

## No Fallbacks Policy

**If config fails, fix the error — do not fall back to another value.**

| Layer | Wrong (fallback) | Right |
|-------|-------------------|-------|
| API | Return default dict when file missing | Raise `HTTPException(503)` with clear message |
| Frontend | `title \|\| 'Pro Billiards Software'` when API fails | Show error UI: "Failed to load configuration" |
| Client | Treat splash-config 404 as "use defaults" | Let error propagate; show actual failure |

**Rationale:** Fallbacks hide misconfiguration (missing mount, wrong path, proxy 404). Operators must fix the root cause.

---

## API Behavior

- **GET `/api/splash-config`** — Returns config from `config/splash_config.json`.
- **Missing file** → `503 Service Unavailable` — "Ensure config/splash_config.json exists and is mounted."
- **Invalid JSON** → `503` — "Fix config/splash_config.json."
- **Read error** → `503` — "Cannot read splash configuration."

---

## Frontend Behavior

- **Loading** — Show "Loading…" while fetching.
- **Success** — Use `splashConfig.title`, `splashConfig.splash_url`, etc. directly. No `||` fallbacks.
- **Error (404, 503, network)** — Show error UI: "Failed to load configuration. Ensure the API is running and config/splash_config.json exists. Fix the error and refresh."

---

## Deployment Requirements

- **Config mount:** Docker Compose must mount `./config:/app/config` for the API container.
- **File:** `config/splash_config.json` must exist and be valid JSON with required fields: `splash_url`, `splash_type`, `splash_use_scraped_media`, `title`.

### `splash_media_revision` (cache-busting media URLs)

The API also returns **`splash_media_revision`** (integer, server-owned). On each admin **PATCH** to `/api/splash-config`, the API **increments** this value and persists it in the JSON file. The login splash appends it as a query parameter (`smr=…`) on `splash_url` and scraped slideshow URLs so browsers and CDNs do not keep serving **old bytes** when the path is unchanged but the file on disk was replaced.

- If a server’s config file predates this field, revision starts at **0** until the first admin save (then it increments).
- **Nginx:** `location ^~ /assets/video/` uses **`Cache-Control: private, no-cache, must-revalidate`** so splash video is not treated like long-lived immutable hashed assets.

---

## When Adding or Changing Splash Logic

1. **Do not** add fallback values for title, splash_url, or splash_type.
2. **Do not** special-case 404 on splash-config to "use defaults."
3. **Do** ensure config is mounted in all compose files that run the API.
4. **Do** surface errors so operators can fix them.

---

## Related

- [DOCKER_POSTGRES_ONLY.md](DOCKER_POSTGRES_ONLY.md) — Similar no-fallback principle for Postgres
- [CODING_STANDARDS.md](../.github/CODING_STANDARDS.md) — Error handling, HTTP status codes
