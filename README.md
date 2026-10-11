# Rankings bot (public snapshot)

Tracks rankings for the Women's Professional Billiards Association (WPBA) and the Women's World Pool-Billiard Association (WPA). PostgreSQL holds the data. Redis is the cache. A background worker runs beside the API.

Production services are in `production/docker-compose.prod.yml`. The root `docker-compose.yml` only includes that file.

| Service | Host publish |
|---------|----------------|
| postgres | none (compose network) |
| postgres-testcenter | none (compose network) |
| redis | none (compose network) |
| rankings-bot-api | `127.0.0.1:8003` |
| celery-worker | none (compose network) |

## Configure before you run

Copy the env example to `.env` and set the database password there. Do not commit `.env`.

This public repository currently contains this note only.
