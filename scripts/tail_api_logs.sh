#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="${CONTAINER_NAME:-rankings-bot-api}"
TAIL_LINES="${TAIL_LINES:-200}"

# Always use sudo for Docker so the script works without the user being in the docker group
DOCKER_CMD=(sudo docker)
if ! "${DOCKER_CMD[@]}" info >/dev/null 2>&1; then
  echo "Docker is not available (sudo docker failed). Start Docker or check permissions." >&2
  exit 2
fi

"${DOCKER_CMD[@]}" logs --timestamps --tail "$TAIL_LINES" -f "$CONTAINER_NAME"
