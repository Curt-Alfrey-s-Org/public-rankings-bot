# Rankings bot (public snapshot)

Open-source snapshot of a billiards rankings application, plus the USPBF site tree under `uspbf/`. This repository is not a continuation of private git history.

## Rankings

Tracks WPBA and WPA rankings. PostgreSQL stores data; Redis is the cache; a Celery worker runs beside the API. Compose file: `production/docker-compose.prod.yml` (the root `docker-compose.yml` includes it).

1. Copy `.env.example` to `.env`.
2. Set your own secrets, especially `POSTGRES_PASSWORD` and the bootstrap `*_PASSWORD` values required by compose.
3. Start the stack:

```bash
docker compose -f production/docker-compose.prod.yml up -d
```

The API is published on `127.0.0.1:8003` by default (`API_BIND_ADDR` overrides the bind address; container port stays `8003`).

License: MIT (`LICENSE` in the repo root).

## USPBF

Scrubbed snapshot of the United States Pro Billiards Federation site: static pages, nginx, WordPress, and MySQL. Compose file: `uspbf/docker-compose.yml`.

1. Copy `uspbf/env.example` to `uspbf/.env`.
2. Set your own MySQL passwords and `BOT_API_KEY` (must match the rankings API key if you proxy `/api`).
3. From the `uspbf/` directory:

```bash
docker compose up -d
```

Preview the site on host port **8089** (`8089:8089`).

USPBF did not ship with a LICENSE file; none was added.
