#!/bin/bash
# Rankings Bot Desktop Launcher (local dev only: host Vite + API).
# Production deploy: Docker Compose + scripts/build_frontend_with_docker.sh (see docs/PRODUCTION_DEPLOYMENT.md).

set -e

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
API_PORT=8003
FRONTEND_PORT=5174
LOCK_FILE="/tmp/rankings-bot-browser-open.lock"
LOCK_TIMEOUT=10
BROWSER_OPENED=false

# Repo root (this file lives under scripts/archive/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$APP_ROOT"

# Timestamp function
timestamp() {
    date '+%Y-%m-%d %H:%M:%S'
}

# Log function with timestamp
log() {
    echo -e "${2}[$(timestamp)] $1${NC}"
}

# Cleanup function
cleanup() {
    log "Shutting down Rankings Bot..." "$YELLOW"
    
    # Kill API server
    if [ -n "$API_PID" ] && kill -0 $API_PID 2>/dev/null; then
        log "Stopping API server (PID: $API_PID)..." "$YELLOW"
        kill $API_PID 2>/dev/null || true
        wait $API_PID 2>/dev/null || true
    fi
    
    # Kill frontend server
    if [ -n "$FRONTEND_PID" ] && kill -0 $FRONTEND_PID 2>/dev/null; then
        log "Stopping frontend server (PID: $FRONTEND_PID)..." "$YELLOW"
        kill $FRONTEND_PID 2>/dev/null || true
        wait $FRONTEND_PID 2>/dev/null || true
    fi
    
    # Remove lock file
    if [ -f "$LOCK_FILE" ]; then
        rm -f "$LOCK_FILE"
    fi
    
    log "Rankings Bot stopped" "$GREEN"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM EXIT

# Print banner
echo "======================================================================="
log "Rankings Bot Launcher" "$BLUE"
echo "======================================================================="

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    log "ERROR: Virtual environment not found. Run setup.sh first." "$RED"
    exit 1
fi

# Activate virtual environment
log "Activating virtual environment..." "$BLUE"
source .venv/bin/activate

# Load environment variables from .env (required for PostgreSQL DATABASE_URL)
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# PostgreSQL is required; API and load_initial_data need DATABASE_URL
if [ -z "${DATABASE_URL:-}" ]; then
    log "ERROR: DATABASE_URL is not set." "$RED"
    log "Copy .env.example to .env and set DATABASE_URL to your PostgreSQL connection string." "$YELLOW"
    log "Example: postgresql://rankingsbot_user:PASSWORD@rankings-bot-postgres:5432/rankingsbot" "$YELLOW"
    exit 1
fi

# Check if PostgreSQL is reachable
check_db_connect() {
    python3 -c "
import os, sys, socket
url = os.environ.get('DATABASE_URL', '')
if not url or not url.startswith('postgresql'):
    sys.exit(1)
import re
m = re.search(r'@([^:/]+):?(\d+)?/', url)
if not m:
    sys.exit(1)
host, port = m.group(1), int(m.group(2) or 5432)
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(4)
try:
    s.connect((host, port))
    s.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null
}

# Ensure PostgreSQL is running: if Docker Compose is available and DATABASE_URL points at localhost, start postgres
if command -v docker >/dev/null 2>&1 && [ -f "docker-compose.yml" ]; then
    if echo "${DATABASE_URL:-}" | grep -qE '@(localhost|127\.0\.0\.1)(:[0-9]+)?/'; then
        log "Ensuring PostgreSQL is running (docker compose up -d postgres)..." "$BLUE"
        docker compose up -d postgres 2>/dev/null || true
        log "Waiting for PostgreSQL to accept connections (up to 30s)..." "$YELLOW"
        for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do
            if check_db_connect; then
                log "PostgreSQL is running and reachable." "$GREEN"
                break
            fi
            sleep 1
        done
    fi
fi

if ! check_db_connect; then
    log "ERROR: PostgreSQL is not reachable at the host:port in DATABASE_URL." "$RED"
    log "  - If using Docker: ensure docker compose is available and run 'docker compose up -d postgres'." "$YELLOW"
    log "  - If using a local server: start PostgreSQL and ensure DATABASE_URL host/port match." "$YELLOW"
    log "  - Docker: use rankings-bot-postgres:5432 (no host port). See docs/DOCKER_POSTGRES_ONLY.md." "$YELLOW"
    exit 1
fi

# Check if database has data (PostgreSQL check)
if python3 -c "
import sys
sys.path.insert(0, '.')
from database import get_database_manager
try:
    db = get_database_manager()
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM rankings')
    count = cursor.fetchone()[0]
    conn.close()
    print(f'Database has {count} rankings')
    exit(0 if count > 0 else 1)
except:
    exit(1)  # Database not accessible
"; then
    log "Database has existing data - skipping initial data load." "$GREEN"
else
    log "Database not found or empty. Loading initial data..." "$YELLOW"
    if ! python3 scripts/load_initial_data.py; then
        log "Warning: load_initial_data failed (see above). API may still start if tables exist." "$YELLOW"
    fi
fi

# Check if API port is available
if lsof -Pi :$API_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    log "ERROR: Port $API_PORT is already in use" "$RED"
    log "Another instance may be running. Use 'lsof -i :$API_PORT' to check." "$YELLOW"
    exit 1
fi

# Check if frontend port is available
if lsof -Pi :$FRONTEND_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    log "ERROR: Port $FRONTEND_PORT is already in use" "$RED"
    log "Another instance may be running. Use 'lsof -i :$FRONTEND_PORT' to check." "$YELLOW"
    exit 1
fi

# Start API server in background
log "Starting API server on port $API_PORT..." "$BLUE"
export API_PORT=$API_PORT
python3 -m uvicorn api.main:app --host 0.0.0.0 --port $API_PORT --reload > /tmp/rankings-bot-api.log 2>&1 &
API_PID=$!
log "API server started (PID: $API_PID)" "$GREEN"

# Wait for API to be ready
log "Waiting for API to be ready..." "$YELLOW"
for i in {1..30}; do
    if curl -s http://localhost:$API_PORT/api/health > /dev/null 2>&1; then
        log "API is ready!" "$GREEN"
        break
    fi
    if [ $i -eq 30 ]; then
        log "ERROR: API failed to start within 30 seconds" "$RED"
        # Surface root cause: show whether process died and last lines of API log
        if ! kill -0 $API_PID 2>/dev/null; then
            log "API process (PID $API_PID) has exited (crashed)." "$RED"
        else
            log "API process is still running but /api/health did not respond (port not bound or startup hung)." "$YELLOW"
        fi
        if [ -f /tmp/rankings-bot-api.log ]; then
            log "Last 40 lines of API log (/tmp/rankings-bot-api.log):" "$YELLOW"
            echo "----------------------------------------"
            tail -n 40 /tmp/rankings-bot-api.log
            echo "----------------------------------------"
            log "Full log: cat /tmp/rankings-bot-api.log" "$YELLOW"
        else
            log "No API log found at /tmp/rankings-bot-api.log" "$YELLOW"
        fi
        exit 1
    fi
    sleep 1
done

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    log "ERROR: npm is not installed. Please install Node.js and npm." "$RED"
    exit 1
fi

# Install frontend dependencies if needed
if [ ! -d "frontend/node_modules" ]; then
    log "Installing frontend dependencies..." "$YELLOW"
    cd frontend
    npm install
    cd ..
fi

# Start frontend server in background
log "Starting frontend server on port $FRONTEND_PORT..." "$BLUE"
cd frontend
npm run dev > /tmp/rankings-bot-frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..
log "Frontend server started (PID: $FRONTEND_PID)" "$GREEN"

# Wait for frontend to be ready
log "Waiting for frontend to be ready..." "$YELLOW"
for i in {1..30}; do
    if curl -s http://localhost:$FRONTEND_PORT > /dev/null 2>&1; then
        log "Frontend is ready!" "$GREEN"
        break
    fi
    if [ $i -eq 30 ]; then
        log "ERROR: Frontend failed to start within 30 seconds" "$RED"
        if ! kill -0 $FRONTEND_PID 2>/dev/null; then
            log "Frontend process (PID $FRONTEND_PID) has exited (crashed)." "$RED"
        else
            log "Frontend process is still running but port $FRONTEND_PORT did not respond." "$YELLOW"
        fi
        if [ -f /tmp/rankings-bot-frontend.log ]; then
            log "Last 40 lines of frontend log (/tmp/rankings-bot-frontend.log):" "$YELLOW"
            echo "----------------------------------------"
            tail -n 40 /tmp/rankings-bot-frontend.log
            echo "----------------------------------------"
            log "Full log: cat /tmp/rankings-bot-frontend.log" "$YELLOW"
        else
            log "No frontend log found at /tmp/rankings-bot-frontend.log" "$YELLOW"
        fi
        exit 1
    fi
    sleep 1
done

# Duplicate tab prevention
SHOULD_OPEN_BROWSER=true

# Check 1: Lock file with timeout
if [ -f "$LOCK_FILE" ]; then
    # Get lock file age (cross-platform: try Linux stat -c first, then BSD stat -f)
    if stat -c %Y "$LOCK_FILE" >/dev/null 2>&1; then
        LOCK_TIME=$(stat -c %Y "$LOCK_FILE")
    else
        LOCK_TIME=$(stat -f %m "$LOCK_FILE")
    fi
    LOCK_AGE=$(($(date +%s) - $LOCK_TIME))
    
    if [ $LOCK_AGE -lt $LOCK_TIMEOUT ]; then
        log "Browser recently opened (lock file age: ${LOCK_AGE}s). Skipping..." "$YELLOW"
        SHOULD_OPEN_BROWSER=false
    else
        log "Lock file expired (age: ${LOCK_AGE}s). Cleaning up..." "$YELLOW"
        rm -f "$LOCK_FILE"
    fi
fi

# Check 2: Browser opening process detection
if $SHOULD_OPEN_BROWSER; then
    if pgrep -f "xdg-open.*5174|gnome-open.*5174|kde-open.*5174" > /dev/null 2>&1; then
        log "Browser opening process detected. Skipping..." "$YELLOW"
        SHOULD_OPEN_BROWSER=false
    fi
fi

# Check 3: Port connection check (ss or netstat for port 5174)
if $SHOULD_OPEN_BROWSER; then
    # Try ss first (modern tool), fallback to netstat
    if command -v ss &> /dev/null; then
        if ss -tn | grep ':5174.*ESTAB' > /dev/null 2>&1; then
            log "Active connection to port 5174 detected. Skipping..." "$YELLOW"
            SHOULD_OPEN_BROWSER=false
        fi
    elif command -v netstat &> /dev/null; then
        if netstat -tn | grep ':5174.*ESTABLISHED' > /dev/null 2>&1; then
            log "Active connection to port 5174 detected. Skipping..." "$YELLOW"
            SHOULD_OPEN_BROWSER=false
        fi
    fi
fi

# Open browser if all checks passed
if $SHOULD_OPEN_BROWSER; then
    log "Opening browser..." "$BLUE"
    
    # Create lock file
    touch "$LOCK_FILE"
    BROWSER_OPENED=true
    
    # Open browser
    if command -v xdg-open &> /dev/null; then
        xdg-open "http://localhost:$FRONTEND_PORT" &
    elif command -v gnome-open &> /dev/null; then
        gnome-open "http://localhost:$FRONTEND_PORT" &
    elif command -v kde-open &> /dev/null; then
        kde-open "http://localhost:$FRONTEND_PORT" &
    else
        log "WARNING: Could not detect browser launcher. Please open http://localhost:$FRONTEND_PORT manually." "$YELLOW"
    fi
    
    log "Browser opened at http://localhost:$FRONTEND_PORT" "$GREEN"
else
    log "Browser already connected. Visit http://localhost:$FRONTEND_PORT" "$BLUE"
fi

echo "======================================================================="
log "Rankings Bot is running!" "$GREEN"
log "API: http://localhost:$API_PORT" "$BLUE"
log "Frontend: http://localhost:$FRONTEND_PORT" "$BLUE"
log "Press Ctrl+C to stop" "$YELLOW"
echo "======================================================================="

# Keep script running
wait
