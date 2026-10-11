#!/bin/bash
# Sync Rankings Bot code to the server. Build and run happen ON THE SERVER.
# Run from Rankings-Bot app root (the directory that has frontend/, api/, venv/).
#
# Usage:
#   ./scripts/deploy.sh ansible@HOST   # rsync code to HOST; then on server run ./scripts/build_on_server.sh --restart

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$APP_ROOT"

SSH_TARGET="${1:-}"
if [ -z "$SSH_TARGET" ]; then
  echo "Usage: $0 ansible@192.0.2.20"
  echo ""
  echo "Syncs code to the server. The entire bot runs on the server:"
  echo "  On server: cd ~/rankings-bot && ./scripts/build_on_server.sh --restart"
  echo ""
  echo "See web-sites-server/DEPLOY_NOW.md for full steps."
  exit 0
fi

REMOTE_DIR="rankings-bot"
echo "=========================================="
echo "  Rankings Bot — Sync to server"
echo "=========================================="
echo "App root: $APP_ROOT"
echo "Target:   $SSH_TARGET (~/$REMOTE_DIR/Rankings-Bot/)"
echo ""

# Reuse one SSH connection (avoids "Connection closed" when server limits sessions)
SSH_CONTROL="/tmp/rsync-deploy-$$"
cleanup_ssh() { ssh -O exit -o ControlPath="$SSH_CONTROL" "$SSH_TARGET" 2>/dev/null || true; }
trap cleanup_ssh EXIT
echo "Opening SSH connection to $SSH_TARGET..."
ssh -o ControlMaster=yes -o ControlPath="$SSH_CONTROL" -o ControlPersist=60 -o ConnectTimeout=10 "$SSH_TARGET" "mkdir -p ~/$REMOTE_DIR && echo OK" || {
  echo "SSH failed. Fix login (e.g. ssh-copy-id $SSH_TARGET) then re-run."
  exit 1
}

echo "Syncing code to $SSH_TARGET (frontend is built ON THE SERVER)..."
if ! rsync -avz --delete -e "ssh -o ControlPath=$SSH_CONTROL" \
  --exclude 'node_modules' \
  --exclude 'venv' \
  --exclude '.git' \
  --exclude 'frontend/dist' \
  --exclude 'rankings.db' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  "$APP_ROOT/" "$SSH_TARGET:~/$REMOTE_DIR/Rankings-Bot/"; then
  echo "rsync failed. Create remote dir: ssh $SSH_TARGET 'mkdir -p ~/rankings-bot' then re-run."
  exit 1
fi

echo ""
echo "✅ Code synced. Next ON THE SERVER (SSH to $SSH_TARGET):"
echo ""
echo "  cd ~/rankings-bot"
echo "  chmod +x scripts/build_on_server.sh"
echo "  ./scripts/build_on_server.sh --restart"
echo ""
echo "  (One-time: ./master_setup.sh --production, configure .env, alembic upgrade head. See docs/CLOUDFLARE_TUNNEL_NGINX.md)"
