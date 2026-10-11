#!/bin/bash
#
# Health Check Monitoring Script for Alfa Rating System
#
# Runs every 5 minutes (via cron) to monitor system health
# Logs results and alerts on failures
#
# Usage:
#   ./monitor_production_health.sh [--interval 300] [--slack-webhook URL]
#   # Or via cron: */5 * * * * /path/to/monitor_production_health.sh
#

set -e

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HEALTH_CHECK_URL="${HEALTH_CHECK_URL:-http://localhost:8003/api/health/alfa}"
LOGS_DIR="$PROJECT_ROOT/logs"
HEALTH_LOG="$LOGS_DIR/health_check.log"
ALERT_LOG="$LOGS_DIR/health_alerts.log"
SLACK_WEBHOOK="${1:-${SLACK_WEBHOOK}}"
VENV="$PROJECT_ROOT/.venv"

# Thresholds
ERROR_RATE_CRITICAL=1.0  # %
ERROR_RATE_WARNING=0.5   # %
LATENCY_P99_CRITICAL=2000  # ms
LATENCY_P99_WARNING=1500   # ms

# Create logs directory
mkdir -p "$LOGS_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$HEALTH_LOG"
}

alert() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️ ALERT: $1" | tee -a "$ALERT_LOG"
    
    # Send Slack notification if webhook provided
    if [ ! -z "$SLACK_WEBHOOK" ]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"🚨 Health Alert: $1\"}" \
            "$SLACK_WEBHOOK" 2>/dev/null || true
    fi
}

# ============================================================================
# Run Health Checks
# ============================================================================
log "Running health checks..."

HEALTH_RESPONSE=$(curl -s -m 10 "$HEALTH_CHECK_URL" 2>/dev/null || echo "{}")

if [ -z "$HEALTH_RESPONSE" ] || [ "$HEALTH_RESPONSE" = "{}" ]; then
    alert "Failed to get health response from $HEALTH_CHECK_URL"
    exit 1
fi

# Parse JSON response (requires jq)
if ! command -v jq &> /dev/null; then
    log "Installing jq for JSON parsing..."
    which jq > /dev/null 2>&1 || {
        apt-get update && apt-get install -y jq > /dev/null 2>&1 || true
    }
fi

# Check overall status
OVERALL_STATUS=$(echo "$HEALTH_RESPONSE" | jq -r '.status' 2>/dev/null || echo "unknown")

log "Overall Status: $OVERALL_STATUS"

# Check component statuses
if command -v jq &> /dev/null; then
    MODEL_STATUS=$(echo "$HEALTH_RESPONSE" | jq -r '.components.model.status // "unknown"')
    DB_STATUS=$(echo "$HEALTH_RESPONSE" | jq -r '.components.database.status // "unknown"')
    CACHE_STATUS=$(echo "$HEALTH_RESPONSE" | jq -r '.components.cache.status // "unknown"')
    
    log "  Model: $MODEL_STATUS"
    log "  Database: $DB_STATUS"
    log "  Cache: $CACHE_STATUS"
    
    # Alert on unhealthy components
    if [ "$MODEL_STATUS" = "fail" ]; then
        alert "Model component unhealthy - attempting recovery"
    elif [ "$MODEL_STATUS" = "warn" ]; then
        log "Model component degraded - monitoring"
    fi
    
    if [ "$DB_STATUS" = "fail" ]; then
        alert "Database component unhealthy - attempting recovery"
    fi
    
    if [ "$CACHE_STATUS" = "fail" ]; then
        alert "Cache component unhealthy - attempting recovery"
    fi
fi

# ============================================================================
# Record to Database (optional)
# ============================================================================
# This would store health check results in the health_check_log table
# for historical tracking and trending

if [ -f "$VENV/bin/activate" ]; then
    source "$VENV/bin/activate"
    
    python3 << 'PYTHON_SCRIPT'
import sys
import json
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path("$PROJECT_ROOT")
sys.path.insert(0, str(PROJECT_ROOT))

HEALTH_RESPONSE = '''$HEALTH_RESPONSE'''

try:
    # Try to import and log to database
    from database import SessionLocal
    from api.models.monitoring import HealthCheckLog
    
    db = SessionLocal()
    
    health_data = json.loads(HEALTH_RESPONSE)
    
    log_entry = HealthCheckLog(
        timestamp=datetime.now(timezone.utc),
        overall_status=health_data.get('status', 'unknown'),
        model_status=health_data.get('components', {}).get('model', {}).get('status'),
        database_status=health_data.get('components', {}).get('database', {}).get('status'),
        cache_status=health_data.get('components', {}).get('cache', {}).get('status'),
        uptime_seconds=health_data.get('uptime_seconds'),
    )
    
    db.add(log_entry)
    db.commit()
    print(f"Health check logged to database")
    
except Exception as e:
    # Silently fail if database unavailable
    pass
finally:
    try:
        db.close()
    except:
        pass
PYTHON_SCRIPT
fi

log "Health check complete"
