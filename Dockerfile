# syntax=docker/dockerfile:1
# Rankings Bot API — thin app layer FROM rankings-bot-base.
#
# All heavy layers (apt chromium + docker CLI + pinned pip wheels) live in
# Dockerfile.base. A code change rebuilds only this image (~5-10s) because
# the base is already cached locally / pulled from the LAN registry mirror.
#
# Build via bake (preferred):
#   docker buildx bake --file ../alfa-ai/deploy/cluster/docker-bake.hcl rankings-bot-app
#
# Local build (ensure base exists first):
#   docker build -f Dockerfile.base -t rankings-bot-base:local .
#   docker build -t rankings-bot:local .

ARG BASE_TAG=local
FROM rankings-bot-base:${BASE_TAG}

WORKDIR /app

# Application code — only layer that rebuilds on commits.
COPY api/ /app/api/
COPY scrapers/ /app/scrapers/
COPY database/ /app/database/
COPY scripts/ /app/scripts/
COPY alembic/ /app/alembic/
COPY alembic.ini /app/
COPY config/ /app/config/
# ML models (pickled scikit-learn models + model modules) used by api/config/model_loader.py
# and the predict routes; previously missing from the image (review 2026-09-25).
COPY models/ /app/models/
COPY *.py /app/
RUN mkdir -p /app/frontend/dist /app/logs \
    && chown -R 1000:1000 /app/logs

ARG BUILD_HASH=unknown
LABEL org.opencontainers.image.revision=$BUILD_HASH
RUN echo "$BUILD_HASH" > /app/.build-hash

# COPY preserves source perms. Force a+rx so non-root container user (HOST_UID) can
# read AND execute helpers; bash <script> needs read perm. Plain `chmod +x` keeps the
# 700 source mode as 711 in the image, breaking Admin "Update website" with
# "bash: build_frontend_with_docker.sh: Permission denied" (POSIX chmod(1)).
RUN chmod a+rx /app/scripts/docker-api-cmd.sh \
  && find /app/scripts -maxdepth 1 -type f -name '*.sh' -exec chmod a+rx {} +

EXPOSE 8003
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8003/api/health || exit 1

# Multi-worker Uvicorn — see scripts/docker-api-cmd.sh, UVICORN_WORKERS, docs/ENV_VARS.md
CMD ["/app/scripts/docker-api-cmd.sh"]
