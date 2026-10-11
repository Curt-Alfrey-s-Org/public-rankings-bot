#!/usr/bin/env bash
# Reclaim disk space: show / usage, prune Docker build cache (and optional image prunes).
#
# Usage:
#   ./scripts/cleanup_docker_disk.sh [--aggressive] [--images] [--all-images]
#
# Flags:
#   --aggressive   Remove all build cache layers: docker builder prune -af
#                  (default is docker builder prune -f — keeps recent cache).
#   --images       Also run docker image prune -f (dangling images only).
#   --all-images   DANGEROUS: docker image prune -a (all unused images). Never run unattended.
#                  Requires CLEANUP_DOCKER_CONFIRM_ALL_IMAGES=1 when stdin is not a TTY,
#                  or interactive confirmation (type YES).
#
# Environment (same as flags):
#   CLEANUP_DOCKER_AGGRESSIVE=1       → same as --aggressive
#   CLEANUP_DOCKER_IMAGES=1           → same as --images
#   CLEANUP_DOCKER_CONFIRM_ALL_IMAGES=1 → allow --all-images without TTY (required for automation)
#
# If docker is missing or the daemon is unreachable, Docker steps are skipped (exit 0).

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

aggressive=0
images=0
all_images=0
for arg in "$@"; do
  case "$arg" in
    --aggressive) aggressive=1 ;;
    --images) images=1 ;;
    --all-images) all_images=1 ;;
    -h|--help)
      sed -n '1,25p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg (use --help)" >&2
      exit 2
      ;;
  esac
done

[ "${CLEANUP_DOCKER_AGGRESSIVE:-0}" = "1" ] && aggressive=1
[ "${CLEANUP_DOCKER_IMAGES:-0}" = "1" ] && images=1

echo "=== Root filesystem (/) ==="
df -h / || true
echo ""

avail_kb=$(df -Pk / 2>/dev/null | awk 'NR==2 {print $4}' || true)
usepct=$(df -Pk / 2>/dev/null | awk 'NR==2 {gsub(/%/,"",$5); print $5}' || true)
warn=0
if [ -n "${usepct:-}" ] && [ "${usepct:-0}" -ge 90 ] 2>/dev/null; then
  warn=1
fi
if [ -n "${avail_kb:-}" ] && [ "${avail_kb:-999999999}" -le $((2 * 1024 * 1024)) ] 2>/dev/null; then
  warn=1
fi
if [ "$warn" -eq 1 ]; then
  echo "WARNING: Low space on / — use ≥90% and/or ≤2GiB free. Prune Docker cache, logs, or old artifacts." >&2
fi

DOCKER=""
if command -v docker &>/dev/null; then
  if docker info &>/dev/null; then
    DOCKER="docker"
  elif command -v sudo &>/dev/null && sudo docker info &>/dev/null; then
    DOCKER="sudo docker"
  fi
fi

if [ -z "$DOCKER" ]; then
  echo "Docker not available or daemon not reachable; skipping Docker prune steps." >&2
  exit 0
fi

if [ "$aggressive" -eq 1 ]; then
  echo "Pruning Docker build cache (aggressive: builder prune -af)..."
  $DOCKER builder prune -af
else
  echo "Pruning Docker build cache (builder prune -f, keeps recent)..."
  $DOCKER builder prune -f
fi

if [ "$images" -eq 1 ]; then
  echo "Pruning dangling Docker images (image prune -f)..."
  $DOCKER image prune -f
fi

if [ "$all_images" -eq 1 ]; then
  echo "WARNING: docker image prune -a removes ALL unused images (not referenced by containers)." >&2
  echo "         This can force large re-downloads on the next build/pull." >&2
  if [ "${CLEANUP_DOCKER_CONFIRM_ALL_IMAGES:-}" != "1" ]; then
    if [ -t 0 ]; then
      read -r -p "Type YES to continue: " _confirm
      if [ "${_confirm:-}" != "YES" ]; then
        echo "Aborted (--all-images requires YES or CLEANUP_DOCKER_CONFIRM_ALL_IMAGES=1)." >&2
        exit 1
      fi
    else
      echo "Refusing non-interactive --all-images without CLEANUP_DOCKER_CONFIRM_ALL_IMAGES=1." >&2
      exit 1
    fi
  fi
  echo "Pruning all unused Docker images (image prune -a -f)..."
  $DOCKER image prune -a -f
fi

echo "[OK] cleanup_docker_disk.sh finished."
exit 0
