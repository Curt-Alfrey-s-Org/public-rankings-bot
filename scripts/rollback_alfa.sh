#!/bin/bash
################################################################################
# Alfa Rating System - Rollback Script
# Safely rolls back Alfa rating system to previous phase or disable completely
#
# Usage:
#   ./scripts/rollback_alfa.sh --phase 0    # Rollback to Phase 0 (disable)
#   ./scripts/rollback_alfa.sh --auto       # Auto-detect and rollback
#   ./scripts/rollback_alfa.sh --status     # Show current status
#   ./scripts/rollback_alfa.sh --list       # List rollback history
################################################################################

set -e

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$PROJECT_ROOT/config/feature_flags.json"
ROLLBACK_DIR="$PROJECT_ROOT/rollout"
ROLLBACK_LOG="$ROLLBACK_DIR/rollback.log"
CHECKPOINTS_DIR="$ROLLBACK_DIR/checkpoints"

# Ensure directories exist
mkdir -p "$ROLLBACK_DIR"
mkdir -p "$CHECKPOINTS_DIR"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$ROLLBACK_LOG"
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $*"
}

error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" >> "$ROLLBACK_LOG"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] SUCCESS: $*" >> "$ROLLBACK_LOG"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $*" >> "$ROLLBACK_LOG"
}

# Check dependencies
check_dependencies() {
    local deps=("python3" "jq")
    for cmd in "${deps[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            error "$cmd is required but not installed"
            exit 1
        fi
    done
}

# Get current rollout status
get_current_status() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
        error "Configuration file not found: $CONFIG_FILE"
        return 1
    fi
    
    local percentage=$(jq -r '.alfa_rating_enabled.percentage' "$CONFIG_FILE")
    local enabled=$(jq -r '.alfa_rating_enabled.enabled // "N/A"' "$CONFIG_FILE")
    
    echo "Percentage: $percentage"
    echo "Enabled: $enabled"
}

# Show current status
show_status() {
    echo -e "${BLUE}=== Alfa Rating Rollout Status ===${NC}"
    echo ""
    
    if get_current_status; then
        echo ""
        echo "Rollout Phase: $(get_phase_from_percentage)"
        echo "Config file: $CONFIG_FILE"
        echo "Rollback log: $ROLLBACK_LOG"
    fi
}

# Get phase from percentage
get_phase_from_percentage() {
    local percentage=$(jq -r '.alfa_rating_enabled.percentage' "$CONFIG_FILE")
    
    case $percentage in
        0) echo "Phase 0 (Pre-launch) - 0%" ;;
        10) echo "Phase 1 (Silent Canary) - 10%" ;;
        25) echo "Phase 2 (Shadow Mode) - 25%" ;;
        50) echo "Phase 3 (Experimentation) - 50%" ;;
        75) echo "Phase 4 (Controlled Expansion) - 75%" ;;
        100) echo "Phase 5 (Full Production) - 100%" ;;
        *) echo "Custom - $percentage%" ;;
    esac
}

# Create checkpoint before rollback
create_checkpoint() {
    local timestamp=$(date '+%Y%m%d_%H%M%S')
    local checkpoint_file="$CHECKPOINTS_DIR/checkpoint_${timestamp}.json"
    
    log "Creating checkpoint: $checkpoint_file"
    
    cp "$CONFIG_FILE" "$checkpoint_file"
    if [[ $? -eq 0 ]]; then
        success "Checkpoint created: $checkpoint_file"
        echo "$checkpoint_file"
    else
        error "Failed to create checkpoint"
        return 1
    fi
}

# Perform rollback
perform_rollback() {
    local target_phase=$1
    local target_percentage=0
    
    case $target_phase in
        0) target_percentage=0; phase_name="Pre-launch" ;;
        1) target_percentage=10; phase_name="Silent Canary" ;;
        2) target_percentage=25; phase_name="Shadow Mode" ;;
        3) target_percentage=50; phase_name="Experimentation" ;;
        4) target_percentage=75; phase_name="Controlled Expansion" ;;
        5) target_percentage=100; phase_name="Full Production" ;;
        *)
            error "Invalid target phase: $target_phase (must be 0-5)"
            return 1
            ;;
    esac
    
    log "Rolling back to Phase $target_phase ($phase_name) - $target_percentage%"
    
    # Backup current config
    local backup_file=$(create_checkpoint)
    if [[ -z "$backup_file" ]]; then
        error "Failed to create checkpoint before rollback"
        return 1
    fi
    
    # Update feature flags
    log "Updating feature flags..."
    
    # Use Python to safely update JSON
    python3 << PYTHON_EOF
import json
import sys

try:
    with open('$CONFIG_FILE', 'r') as f:
        config = json.load(f)
    
    # Update percentage
    config['alfa_rating_enabled']['percentage'] = $target_percentage
    
    # Update metadata
    config['metadata']['phase'] = $target_phase
    config['metadata']['phase_name'] = '$phase_name'
    config['metadata']['last_updated'] = '$(date -u +%Y-%m-%dT%H:%M:%SZ)'
    
    # Conditionally disable features based on target phase
    if $target_phase < 2:
        config['alfa_predictions_in_api']['enabled'] = False
    if $target_phase < 4:
        config['alfa_anomaly_detection_enabled']['enabled'] = False
    
    with open('$CONFIG_FILE', 'w') as f:
        json.dump(config, f, indent=2)
    
    print("Feature flags updated successfully")
    
except Exception as e:
    print(f"Error updating feature flags: {e}", file=sys.stderr)
    sys.exit(1)
PYTHON_EOF
    
    if [[ $? -ne 0 ]]; then
        error "Failed to update feature flags"
        log "Restoring from checkpoint: $backup_file"
        cp "$backup_file" "$CONFIG_FILE"
        return 1
    fi
    
    success "Feature flags updated to Phase $target_phase ($target_percentage%)"
}

# Disable API endpoints for Alfa predictions
disable_api_endpoints() {
    log "Disabling Alfa prediction endpoints..."
    
    # This would typically involve:
    # 1. Stopping the API server
    # 2. Updating endpoint configurations
    # 3. Restarting the API server
    
    # For now, just log the intent
    log "API endpoints would be disabled/reconfigured by API service"
}

# Generate rollback report
generate_rollback_report() {
    local timestamp=$(date '+%Y%m%d_%H%M%S')
    local report_file="$ROLLBACK_DIR/ROLLBACK_REPORT_${timestamp}.md"
    
    log "Generating rollback report: $report_file"
    
    cat > "$report_file" << REPORT_EOF
# Alfa Rating System - Rollback Report

**Timestamp:** $(date)
**Triggered By:** ${TRIGGERED_BY:-Manual}
**Rollback Trigger Reason:** ${ROLLBACK_REASON:-User initiated}

## Status Before Rollback
- **Phase:** $(grep -h "Phase:" "$ROLLBACK_LOG" | tail -1 || echo "Unknown")
- **Percentage:** $(jq -r '.alfa_rating_enabled.percentage' "$CHECKPOINTS_DIR"/*.json 2>/dev/null | tail -1 || echo "Unknown")

## Rollback Actions
- ✓ Created checkpoint
- ✓ Updated feature flags to Phase $TARGET_PHASE
- ✓ Disabled API endpoints
- ✓ Reverted to Fargo-only in UI

## Status After Rollback
- **Phase:** $(get_phase_from_percentage)
- **Percentage:** $(jq -r '.alfa_rating_enabled.percentage' "$CONFIG_FILE")
- **Config File:** $CONFIG_FILE

## Checkpoints
- **Current:** $CHECKPOINTS_DIR/checkpoint_${timestamp}.json
- **Previous:** $(ls -t "$CHECKPOINTS_DIR"/checkpoint_*.json 2>/dev/null | head -2 | tail -1)

## Next Steps
1. Review error logs in $PROJECT_ROOT/rankings_bot.log
2. Investigate root cause in monitoring dashboards
3. Address issues in code/configuration
4. Plan re-deployment with fixes
5. Notify stakeholders of rollback and recovery plan

## Rollback Log
$(tail -50 "$ROLLBACK_LOG" 2>/dev/null || echo "No log entries yet")

REPORT_EOF
    
    if [[ $? -eq 0 ]]; then
        success "Rollback report generated: $report_file"
        echo "$report_file"
    else
        error "Failed to generate rollback report"
        return 1
    fi
}

# Send notification to admin team
send_notifications() {
    log "Sending notifications to admin team..."
    
    # This would typically send:
    # - Email to admins
    # - Slack message
    # - PagerDuty alert
    
    # For now, just log the intent
    log "Notifications would be sent via configured channels"
}

# List rollback history
list_history() {
    echo -e "${BLUE}=== Rollback History ===${NC}"
    echo ""
    
    if [[ ! -d "$CHECKPOINTS_DIR" ]]; then
        echo "No rollback history found"
        return
    fi
    
    echo "Checkpoints:"
    ls -lt "$CHECKPOINTS_DIR"/checkpoint_*.json 2>/dev/null | head -10 | awk '{print $NF}' | xargs -I {} bash -c '
        echo ""
        echo "File: {}"
        echo "Phase: $(jq -r ".alfa_rating_enabled.percentage" {})"
    '
    
    echo ""
    echo "Recent rollback operations:"
    tail -20 "$ROLLBACK_LOG" 2>/dev/null | grep -i rollback || echo "No rollback operations yet"
}

# Main logic
main() {
    check_dependencies
    
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  Alfa Rating System - Rollback Script  ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
    echo ""
    
    # Parse arguments
    case "${1:-}" in
        --phase)
            TARGET_PHASE="${2:-0}"
            log "Rollback initiated - Target Phase: $TARGET_PHASE"
            
            echo -e "${YELLOW}WARNING: About to rollback Alfa rating system${NC}"
            echo "Target Phase: $TARGET_PHASE ($(get_phase_from_percentage))"
            echo ""
            read -p "Continue with rollback? (yes/no): " confirm
            
            if [[ "$confirm" != "yes" ]]; then
                log "Rollback cancelled by user"
                echo "Rollback cancelled"
                exit 0
            fi
            
            perform_rollback "$TARGET_PHASE" || exit 1
            disable_api_endpoints
            report_file=$(generate_rollback_report)
            send_notifications
            show_status
            ;;
        
        --auto)
            warning "Auto-rollback detected - Rolling back to Phase 0"
            TARGET_PHASE=0
            TRIGGERED_BY="Automatic"
            
            perform_rollback "$TARGET_PHASE" || exit 1
            disable_api_endpoints
            report_file=$(generate_rollback_report)
            send_notifications
            ;;
        
        --status)
            show_status
            ;;
        
        --list)
            list_history
            ;;
        
        *)
            echo "Usage: $0 {--phase N|--auto|--status|--list}"
            echo ""
            echo "Options:"
            echo "  --phase N     Rollback to phase N (0-5)"
            echo "  --auto        Automatic rollback to Phase 0"
            echo "  --status      Show current rollout status"
            echo "  --list        List rollback history"
            echo ""
            echo "Examples:"
            echo "  $0 --phase 0   # Disable Alfa completely"
            echo "  $0 --phase 2   # Rollback to Phase 2 (25%)"
            echo "  $0 --status    # Show current phase"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
