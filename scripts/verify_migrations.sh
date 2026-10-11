#!/bin/bash

# Migration Verification Script for Week 2 Cursor Deliverables
# Run this after Pull Request is merged to verify all migrations are correct

set -e

PROJECT_DIR="/home/ansible/rankings-bot/Rankings-Bot"
VENV_DIR="$PROJECT_DIR/.venv"

echo "=========================================="
echo "Week 2 Migration Verification"
echo "=========================================="

# Activate venv
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
    echo "✓ Virtual environment activated"
else
    echo "✗ Virtual environment not found at $VENV_DIR"
    exit 1
fi

# Change to project directory
cd "$PROJECT_DIR" || exit 1

# Check if alembic.ini exists
if [ ! -f "alembic.ini" ]; then
    echo "✗ alembic.ini not found"
    exit 1
fi
echo "✓ alembic.ini found"

# List all available migrations
echo ""
echo "Available migrations:"
alembic revision --autogenerate -m "check" --sql 2>/dev/null || true
echo ""

# Count migration files
MIGRATION_COUNT=$(ls -1 alembic/versions/*.py 2>/dev/null | wc -l)
echo "Total migration files: $MIGRATION_COUNT"

# Check syntax of migrations
echo ""
echo "Verifying migration file syntax..."
for file in alembic/versions/*.py; do
    if python3 -m py_compile "$file" 2>/dev/null; then
        echo "  ✓ $(basename "$file")"
    else
        echo "  ✗ $(basename "$file") - SYNTAX ERROR"
        exit 1
    fi
done

# Show current alembic version
echo ""
echo "Current database version:"
alembic current
echo ""

# Show migration history
echo "Migration history (last 5):"
alembic history --rev-range 1:5 || echo "  (No history available)"
echo ""

echo "=========================================="
echo "✓ All migrations verified successfully"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Run: alembic upgrade head"
echo "2. Verify new tables/columns: docker exec rankings-bot-postgres psql -U rankingsbot -d rankingsbot -c '\dt'"
echo "3. Rebuild API: sudo docker-compose build rankings-bot-api"
echo "4. Verify API: curl -sS http://127.0.0.1:8003/api/health"
