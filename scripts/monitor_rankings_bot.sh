#!/bin/bash
# Basic monitoring wrapper: health check + log tail on failure.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

HEALTHCHECK_SCRIPT="${PROJECT_ROOT}/scripts/healthcheck.sh"
LOG_TAIL_LINES="${LOG_TAIL_LINES:-200}"
API_CONTAINER="${API_CONTAINER:-rankings-bot-api}"

if ! bash "${HEALTHCHECK_SCRIPT}"; then
  echo "[monitor] Healthcheck failed. Tailing API logs..."
  sudo docker logs "${API_CONTAINER}" 2>&1 | tail -n "${LOG_TAIL_LINES}"
  exit 1
fi

echo "[monitor] Healthcheck passed."
