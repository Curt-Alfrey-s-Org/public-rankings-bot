#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./mac_bugfix_flow.sh bugfix/short-name "Fix rankings parse edge case"
#
# Optional env vars:
#   RUN_BACKEND_TESTS=1
#   RUN_FRONTEND_TESTS=1
#   RUN_MOBILE_TESTS=1

BRANCH_NAME="${1:-}"
COMMIT_MSG="${2:-}"

if [[ -z "${BRANCH_NAME}" || -z "${COMMIT_MSG}" ]]; then
  echo "Usage: $0 <branch-name> <commit-message>"
  exit 1
fi

if [[ ! -d ".git" ]]; then
  echo "Error: run from repo root."
  exit 1
fi

echo "==> Fetching latest..."
git fetch origin

echo "==> Switching to main and updating..."
git checkout main
git pull --ff-only origin main

echo "==> Creating branch: ${BRANCH_NAME}"
git checkout -b "${BRANCH_NAME}"

echo "==> Branch ready."
echo "Now make your code changes, then rerun this script section manually or continue below."
echo

if [[ "${RUN_BACKEND_TESTS:-0}" == "1" ]]; then
  echo "==> RUN_BACKEND_TESTS=1: backend pytest suite was removed from this repo; skipping."
fi

if [[ "${RUN_FRONTEND_TESTS:-0}" == "1" ]]; then
  echo "==> Running frontend checks..."
  (cd frontend && npm run lint && npm run build) || {
    echo "Frontend checks failed. Fix before commit."
    exit 1
  }
fi

if [[ "${RUN_MOBILE_TESTS:-0}" == "1" ]]; then
  echo "==> Running mobile checks..."
  (cd mobile && npm run ios:pods) || {
    echo "Mobile checks failed. Fix before commit."
    exit 1
  }
fi

echo "==> Git status:"
git status --short

echo "==> Staging all changes..."
git add .

echo "==> Committing..."
git commit -m "${COMMIT_MSG}"

echo "==> Pushing branch..."
git push -u origin "${BRANCH_NAME}"

echo
echo "Done. Create PR with:"
echo "  gh pr create --fill"
echo "or open GitHub in browser and create PR from ${BRANCH_NAME} -> main."
