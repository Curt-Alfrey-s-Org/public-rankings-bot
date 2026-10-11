#!/usr/bin/env bash
# Enhanced backup script that starts Docker containers if needed
# Usage: ./scripts/backup_postgres_with_docker.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Check if Docker containers are running
if ! docker ps | grep -q "rankings-postgres"; then
    echo "Starting Docker containers..."
    cd "$PROJECT_ROOT"
    docker-compose up -d postgres
    echo "Waiting 30 seconds for database to start..."
    sleep 30
fi

# Run the backup
"$SCRIPT_DIR/backup_postgres.sh"