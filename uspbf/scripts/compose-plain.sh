#!/usr/bin/env bash
# Source from other USPBF scripts (do not execute directly). Defines uspbf_compose.
# Uses --progress plain so build/up logs are line-oriented (readable in any terminal width).
uspbf_compose() {
  if sudo docker compose version &>/dev/null 2>&1; then
    sudo docker compose --progress plain "$@"
  else
    CI=1 sudo docker-compose "$@"
  fi
}
