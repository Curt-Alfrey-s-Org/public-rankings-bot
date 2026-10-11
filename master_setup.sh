#!/bin/bash
# Master Setup Script for Web GUI Bot
# Sets up Python backend + React frontend in one command
# Usage: ./master_setup.sh [--production]
#   --production  Skip interactive port config, build frontend for rankings-bot.example.com, print server steps

set -e

PRODUCTION=
for arg in "$@"; do
  [ "$arg" = "--production" ] || [ "$arg" = "-p" ] && PRODUCTION=1 && break
done

echo "=========================================="
echo "  Master Web GUI Bot Setup${PRODUCTION:+ (production)}"
echo "=========================================="
echo ""

# Check Python3
echo "Checking Python3..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found. Please install Python 3.8+"
    exit 1
fi
PYTHON_VERSION=$(python3 --version)
echo "✅ Found $PYTHON_VERSION"
echo ""

# Check Node/npm
echo "Checking Node.js and npm..."
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js 16+"
    exit 1
fi
if ! command -v npm &> /dev/null; then
    echo "❌ npm not found. Please install npm"
    exit 1
fi
NODE_VERSION=$(node --version)
NPM_VERSION=$(npm --version)
echo "✅ Found Node $NODE_VERSION"
echo "✅ Found npm $NPM_VERSION"
echo ""

# Configure ports (skip in production; use default 8003)
if [ -z "$PRODUCTION" ]; then
  echo "=========================================="
  echo "  Port Configuration"
  echo "=========================================="
  echo ""
  echo "Running port configuration script..."
  if [ -f "scripts/configure_ports.sh" ]; then
      chmod +x scripts/configure_ports.sh
      ./scripts/configure_ports.sh
  else
      echo "⚠️  scripts/configure_ports.sh not found, skipping port config"
  fi
  echo ""
else
  echo "Production mode: skipping interactive port config (API will use 8003)."
  echo ""
fi

# Setup Python virtual environment
echo "=========================================="
echo "  Setting up Python environment"
echo "=========================================="
echo ""

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install Python dependencies
echo ""
echo "Installing bot dependencies (requirements.txt)..."
pip install -r requirements.txt

echo ""
echo "Installing API dependencies (requirements-api.txt)..."
pip install -r requirements-api.txt

echo ""
echo "✅ Python packages installed"
echo ""

# Verify Postgres DATABASE_URL (schema via Docker compose + alembic)
echo "Checking database configuration..."
if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
if [ -z "${DATABASE_URL:-}" ]; then
  echo "⚠️  DATABASE_URL not set. For production: copy .env.example, set DATABASE_URL, use Docker Compose."
else
  python3 -c "from database import get_engine; get_engine(); print('Postgres DATABASE_URL OK')"
  echo "✅ DATABASE_URL configured (Postgres only)"
fi
echo ""

# Setup Frontend
echo "=========================================="
echo "  Setting up Frontend"
echo "=========================================="
echo ""

if [ -d "frontend" ]; then
    cd frontend
    echo "Installing npm packages..."
    npm install
    echo "✅ Frontend packages installed"
    if [ -n "$PRODUCTION" ]; then
      echo ""
      echo "Building frontend for production (same-origin API/WS)..."
      VITE_API_URL= VITE_WS_URL= npm run build
      echo "✅ Frontend built to frontend/dist"
    fi
    cd ..
else
    echo "⚠️  frontend/ directory not found, skipping npm install"
fi

echo ""
echo "=========================================="
echo "  ✅ Setup Complete!"
echo "=========================================="
echo ""

if [ -n "$PRODUCTION" ]; then
  echo "Production next steps (on this Ubuntu server):"
  echo ""
  echo "1. Start the API (with CORS for rankings-bot.example.com):"
  echo "   export CORS_ORIGINS=\"https://rankings-bot.example.com,http://rankings-bot.example.com\""
  echo "   export API_PORT=8003"
  echo "   source venv/bin/activate"
  echo "   python3 -m uvicorn api.main:app --host 0.0.0.0 --port \$API_PORT"
  echo ""
  echo "2. Deploy: run ./scripts/full_deploy.sh --force-docker (see docs/DEPLOY_WEBSITE.md)."
  echo ""
  echo "3. Keep API running: use Docker Compose (production/docker-compose.prod.yml) or screen/tmux."
  echo ""
else
  echo "Next steps:"
  echo ""
  echo "  Run from THIS directory (the one that has venv/, frontend/, scripts/)."
  echo "  If you cloned the full repo with a Rankings-Bot subfolder, run:  cd Rankings-Bot   first."
  echo ""
  echo "1. Optional: copy .env.example to .env and set JWT_SECRET, ADMIN_*, DIRECTOR_* (and optional SMTP/WEBHOOK_URL; see .env.example)."
  echo ""
  echo "2. Start the API backend:"
  echo "   source venv/bin/activate"
  echo "   ./start_api.sh"
  echo "   # or:  ./scripts/start_api.sh"
  echo ""
  echo "3. Start the frontend (in a new terminal):"
  echo "   cd frontend"
  echo "   npm start"
  echo "   # or:  npm run dev"
  echo ""
  echo "4. Open browser to the URL Vite shows (e.g. http://localhost:5174)"
  echo ""
  echo "5. Optional: desktop icon (ICON_README.md), scheduled refresh (docs/SCHEDULED_REFRESH.md)."
  echo ""
fi