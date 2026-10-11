# setup.sh
#!/bin/bash
# Rankings Bot Setup Script
# Sets up environment on fresh Linux Mint (or Ubuntu/Debian) install

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Rankings Bot Setup${NC}"
echo -e "${GREEN}========================================${NC}\n"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Step 1: Check if running as root
if [ "$EUID" -eq 0 ]; then 
    echo -e "${RED}ERROR: Do not run this script as root/sudo${NC}"
    echo "Run it as your normal user. It will prompt for sudo when needed."
    exit 1
fi

# Step 2: Update package list
echo -e "${YELLOW}[1/8] Updating package list...${NC}"
sudo apt-get update -qq

# Step 3: Install Python3 if not present
echo -e "${YELLOW}[2/8] Checking Python3...${NC}"
if ! command -v python3 &> /dev/null; then
    echo "Python3 not found. Installing..."
    sudo apt-get install -y python3
else
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}✓ Found: $PYTHON_VERSION${NC}"
fi

# Step 4: Install pip if not present
echo -e "${YELLOW}[3/8] Checking pip...${NC}"
if ! command -v pip3 &> /dev/null; then
    echo "pip3 not found. Installing..."
    sudo apt-get install -y python3-pip
else
    PIP_VERSION=$(pip3 --version)
    echo -e "${GREEN}✓ Found: $PIP_VERSION${NC}"
fi

# Step 5: Install python3-venv if not present
echo -e "${YELLOW}[4/8] Checking python3-venv...${NC}"
if ! dpkg -l | grep -q python3-venv; then
    echo "python3-venv not found. Installing..."
    sudo apt-get install -y python3-venv
else
    echo -e "${GREEN}✓ python3-venv is installed${NC}"
fi

# Step 6: Create virtual environment
echo -e "${YELLOW}[5/8] Creating virtual environment...${NC}"
if [ -d "venv" ]; then
    echo "Virtual environment already exists. Skipping..."
else
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Step 7: Activate virtual environment and install dependencies
echo -e "${YELLOW}[6/8] Installing Python dependencies...${NC}"
source venv/bin/activate

# Upgrade pip first
pip install --upgrade pip > /dev/null 2>&1

# Install requirements (backend + API; both needed for start_api.sh)
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo -e "${GREEN}✓ Bot dependencies installed${NC}"
else
    echo -e "${RED}ERROR: requirements.txt not found${NC}"
    exit 1
fi
if [ -f "requirements-api.txt" ]; then
    pip install -r requirements-api.txt
    echo -e "${GREEN}✓ API dependencies installed (FastAPI, uvicorn, auth)${NC}"
else
    echo -e "${YELLOW}⚠ requirements-api.txt not found; API may not start. Install manually if needed.${NC}"
fi

# Step 8: Verify Postgres DATABASE_URL (schema via Docker compose + alembic, not local .db files)
echo -e "${YELLOW}[7/8] Checking database configuration...${NC}"
if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
if [ -z "${DATABASE_URL:-}" ]; then
  echo -e "${YELLOW}⚠ DATABASE_URL not set. For production use Docker Compose (see production/docker-compose.prod.yml).${NC}"
  echo -e "${YELLOW}  Copy .env.example to .env and set DATABASE_URL, then run: alembic upgrade head${NC}"
else
  python3 -c "from database import get_engine; get_engine(); print('✓ Postgres DATABASE_URL OK')"
  echo -e "${GREEN}✓ DATABASE_URL configured (Postgres only; no SQLite)${NC}"
fi

# Step 9: Optional frontend (Node/npm)
echo -e "${YELLOW}[8/8] Checking frontend (optional)...${NC}"
if [ -d "frontend" ] && [ -f "frontend/package.json" ] && command -v npm &> /dev/null; then
    (cd frontend && npm install --no-audit --no-fund)
    echo -e "${GREEN}✓ Frontend dependencies installed${NC}"
else
    echo -e "${YELLOW}⚠ Frontend or npm not found. Skip or install Node.js and run: cd frontend && npm install${NC}"
fi

# Deactivate virtual environment
deactivate

# Final instructions
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "To use the Rankings Bot:"
echo ""
echo "1. Optional: copy .env.example to .env and set JWT_SECRET, ADMIN_*, DIRECTOR_* (and optional SMTP/WEBHOOK_URL; see .env.example)."
echo ""
echo "2. Activate virtual environment:"
echo -e "   ${YELLOW}source venv/bin/activate${NC}"
echo ""
echo "3. Start the bot server (API + web app):"
echo -e "   ${YELLOW}./start_api.sh${NC}"
echo "   Then in another terminal:  cd frontend && npm run dev   (or use the desktop icon if installed)"
echo ""
echo ""
echo "5. Optional: scheduled refresh — see docs/SCHEDULED_REFRESH.md (cron)."
echo "   Desktop icon:  see ICON_README.md or rankings-bot.desktop"
echo ""
echo -e "${GREEN}Happy ranking! 🎱${NC}"
