# Rankings bot (public snapshot)

Scrubbed snapshot of a billiards rankings application, plus the USPBF site tree under `uspbf/`. This repository is not a continuation of private git history.

The rankings app tracks rankings for the Women's Professional Billiards Association (WPBA) and the Women's World Pool-Billiard Association (WPA). PostgreSQL holds the data. Redis is the cache. A background worker runs beside the API.

## Rankings services

Production services are in `production/docker-compose.prod.yml`. The root `docker-compose.yml` only includes that file.

| Service | Image | Host publish |
|---------|-------|----------------|
| postgres | `postgres:15-alpine` | none (compose network only) |
| postgres-testcenter | `postgres:15-alpine` | none (compose network only) |
| redis | `redis:7-alpine` | none (compose network only) |
| rankings-bot-api | built from the root `Dockerfile` | `127.0.0.1:8003` (`API_BIND_ADDR` overrides the bind address; the container port stays `8003`) |
| rankings-bot-celery-worker | same image as the API | none (compose network only) |

Copy an env example to `.env` and set the database password and other required secrets there. Do not commit `.env`.

```bash
docker compose -f production/docker-compose.prod.yml up -d
```

## USPBF

`uspbf/` is a scrubbed snapshot of the United States Pro Billiards Federation site: static pages under `uspbf/nginx-config/site/`, an nginx image, WordPress, and MySQL. Compose file: `uspbf/docker-compose.yml`.

| Service | Image | Host publish |
|---------|-------|----------------|
| uspbf-nginx | built from `uspbf/nginx-config/Dockerfile` | `8089:8089` |
| wordpress | `wordpress:7.0.4-php8.3-apache` | none (compose network only) |
| db | `mysql:8.4` | none (compose network only) |

The nginx health check calls `http://localhost:8080/health` inside the container.

Copy `uspbf/env.example` to `uspbf/.env` and set database passwords there. Do not commit `.env`.

## License

The rankings tree includes the MIT `LICENSE` that shipped with that project. USPBF did not include a LICENSE file. None was added.
