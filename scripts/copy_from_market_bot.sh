#!/bin/bash
# Purpose: Copy non-trading files from market-pie5-bot to Rankings-Bot
# Usage: ./scripts/copy_from_market_bot.sh

set -e

echo "🤖 Copying general utilities from market-pie5-bot to Rankings-Bot"
echo "=================================================================="

MARKET_BOT="$HOME/market-bot/market-pie5-bot"
RANKINGS_BOT="$HOME/market-pie5-bot/Rankings-Bot"

if [ ! -d "$MARKET_BOT" ]; then
    echo "❌ Error: market-pie5-bot not found at $MARKET_BOT"
    exit 1
fi

cd "$RANKINGS_BOT"

# Backup
BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Copy function
copy_file() {
    local src="$MARKET_BOT/$1"
    local dest="$RANKINGS_BOT/$2"
    
    if [ -f "$src" ]; then
        mkdir -p "$(dirname $dest)"
        cp "$src" "$dest"
        echo "  ✅ $1 → $2"
    fi
}

# Copy general utilities (NON-trading)
copy_file "log_manager.py" "src/utils/log_manager.py"
copy_file "pytest.ini" "pytest.ini"
copy_file ".gitignore" ".gitignore.reference"

echo ""


echo ""
echo "📋 Copying GUI Framework..."
echo "============================"

# Copy GUI framework (will be adapted for rankings)
copy_file "gui.py" "gui_reference.py"

# Check for web GUI files
if [ -f "$MARKET_BOT/start_web_gui.sh" ]; then
    copy_file "start_web_gui.sh" "scripts/start_web_gui.sh"
fi

# Copy web assets if they exist
if [ -d "$MARKET_BOT/static" ]; then
    mkdir -p "static"
    rsync -av "$MARKET_BOT/static/" "static/" --exclude='*.pyc'
    echo "  ✅ Copied static assets"
fi

if [ -d "$MARKET_BOT/templates" ]; then
    mkdir -p "templates"
    rsync -av "$MARKET_BOT/templates/" "templates/" --exclude='*.pyc'
    echo "  ✅ Copied HTML templates"
fi

echo "✅ Done! Run: git status"
