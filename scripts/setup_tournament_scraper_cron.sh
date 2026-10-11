#!/bin/bash
# Tournament Scraper Hourly Cron Job Setup
# This script sets up a cron job to run the tournament scraper every hour

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PYTHON_SCRIPT="$PROJECT_ROOT/scripts/run_tournament_scraper_hourly.py"
VENV_PATH="$PROJECT_ROOT/venv"

# Detect Python command
if [ -f "$VENV_PATH/bin/python" ]; then
    PYTHON_CMD="$VENV_PATH/bin/python"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi

# Cron job entry (runs every hour at minute 0)
CRON_ENTRY="0 * * * * cd $PROJECT_ROOT && $PYTHON_CMD $PYTHON_SCRIPT >> $PROJECT_ROOT/logs/tournament_scraper_cron.log 2>&1"

echo "Setting up hourly tournament scraper cron job..."
echo ""
echo "Cron entry:"
echo "$CRON_ENTRY"
echo ""

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "run_tournament_scraper_hourly.py"; then
    echo "⚠️  Cron job already exists. Removing old entry..."
    crontab -l 2>/dev/null | grep -v "run_tournament_scraper_hourly.py" | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

if [ $? -eq 0 ]; then
    echo "✅ Cron job installed successfully!"
    echo ""
    echo "The tournament scraper will now run every hour."
    echo "Logs will be written to: $PROJECT_ROOT/logs/tournament_scraper.log"
    echo ""
    echo "To view current crontab:"
    echo "  crontab -l"
    echo ""
    echo "To remove the cron job:"
    echo "  crontab -e  (then delete the line containing 'run_tournament_scraper_hourly.py')"
    echo ""
    echo "To test the scraper manually:"
    echo "  cd $PROJECT_ROOT"
    echo "  $PYTHON_CMD $PYTHON_SCRIPT"
else
    echo "❌ Failed to install cron job"
    exit 1
fi
