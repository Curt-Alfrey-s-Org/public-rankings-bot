#!/bin/bash
################################################################################
# Alfa Rating System - Rollout Deployment Script
# Manages gradual deployment across phases with validation and monitoring
#
# Usage:
#   ./scripts/rollout_alfa.sh deploy --phase 1    # Deploy to Phase 1
#   ./scripts/rollout_alfa.sh validate --phase 1  # Validate Phase 1
#   ./scripts/rollout_alfa.sh metrics             # Show current metrics
#   ./scripts/rollout_alfa.sh schedule             # Show rollout schedule
################################################################################

set -e

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$PROJECT_ROOT/config/feature_flags.json"
ROLLOUT_DIR="$PROJECT_ROOT/rollout"
DEPLOYMENT_LOG="$ROLLOUT_DIR/deployment.log"
METRICS_FILE="$ROLLOUT_DIR/metrics_latest.json"

mkdir -p "$ROLLOUT_DIR"

# Logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$DEPLOYMENT_LOG"
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $*"
}

success() {
    echo -e "${GREEN}✓ $*${NC}"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] SUCCESS: $*" >> "$DEPLOYMENT_LOG"
}

error() {
    echo -e "${RED}✗ $*${NC}" >&2
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" >> "$DEPLOYMENT_LOG"
}

warning() {
    echo -e "${YELLOW}⚠ $*${NC}"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $*" >> "$DEPLOYMENT_LOG"
}

# Phase definitions
declare -A PHASES=(
    [0]="Pre-launch|0|No Alfa|Background computation only"
    [1]="Silent Canary|10|Compute but don't show|Weeks 1-2"
    [2]="Shadow Mode|25|API opt-in available|Weeks 3-4"
    [3]="Experimentation|50|A/B test with Fargo|Weeks 5-6"
    [4]="Controlled Expansion|75|Enable anomaly detection|Weeks 7-8"
    [5]="Full Production|100|Alfa primary, Fargo fallback|Week 9+"
)

# Phase success criteria
declare -A CRITERIA=(
    [1]="Brier<0.30|No errors|No anomalies"
    [2]="Brier<0.27|Fargo unchanged|No complaints"
    [3]="Brier>=Fargo|Satisfaction>80%|Statistically significant"
    [4]="Anomaly precision>80%|False positive<20%|Admin review complete"
    [5]="All tests pass|Performance stable|Documentation complete"
)

# Validate dependencies
check_dependencies() {
    local deps=("python3" "jq" "curl" "bc")
    for cmd in "${deps[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            error "$cmd is required but not installed"
            exit 1
        fi
    done
    success "All dependencies available"
}

# Show deployment schedule
show_schedule() {
    echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║          Alfa Rating System - Rollout Schedule          ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    for phase in 0 1 2 3 4 5; do
        IFS='|' read -r name percentage description notes <<< "${PHASES[$phase]}"
        printf "%-5s | %-25s | %3s%% | %-30s\n" "Phase $phase" "$name" "$percentage" "$description"
    done
    
    echo ""
    echo -e "${CYAN}Success Criteria by Phase:${NC}"
    for phase in 1 2 3 4 5; do
        echo "  Phase $phase: ${CRITERIA[$phase]}"
    done
}

# Validate phase prerequisites
validate_phase() {
    local target_phase=$1
    
    echo -e "${BLUE}Validating Phase $target_phase prerequisites...${NC}"
    
    # Check config file exists
    if [[ ! -f "$CONFIG_FILE" ]]; then
        error "Configuration file not found: $CONFIG_FILE"
        return 1
    fi
    
    # Verify JSON validity
    if ! jq empty "$CONFIG_FILE" 2>/dev/null; then
        error "Invalid JSON in $CONFIG_FILE"
        return 1
    fi
    
    # Python validation script
    python3 << PYTHON_EOF
import json
import sys

try:
    with open('$CONFIG_FILE', 'r') as f:
        config = json.load(f)
    
    phase = $target_phase
    
    # Phase-specific validations
    if phase >= 1:
        assert 'alfa_rating_enabled' in config, "alfa_rating_enabled flag required"
        assert 'alfa_rollback_enabled' in config, "alfa_rollback_enabled flag required"
        if not config['alfa_rollback_enabled'].get('enabled', True):
            print("WARNING: Rollback is disabled", file=sys.stderr)
    
    if phase >= 2:
        assert 'alfa_predictions_in_api' in config, "alfa_predictions_in_api flag required"
    
    if phase >= 4:
        assert 'alfa_anomaly_detection_enabled' in config, "alfa_anomaly_detection_enabled flag required"
    
    print(f"Phase {phase} prerequisites validated")
    
except AssertionError as e:
    print(f"Validation failed: {e}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Error validating configuration: {e}", file=sys.stderr)
    sys.exit(1)
PYTHON_EOF
    
    if [[ $? -eq 0 ]]; then
        success "Phase $target_phase prerequisites validated"
        return 0
    else
        error "Phase $target_phase validation failed"
        return 1
    fi
}

# Deploy phase
deploy_phase() {
    local target_phase=$1
    
    log "Deploying Phase $target_phase"
    
    # Get phase info
    IFS='|' read -r name percentage description notes <<< "${PHASES[$target_phase]}"
    
    echo ""
    echo -e "${CYAN}Deploying Phase $target_phase: $name${NC}"
    echo "  Percentage: $percentage%"
    echo "  Description: $description"
    echo "  Timeline: $notes"
    echo ""
    
    # Validate
    if ! validate_phase "$target_phase"; then
        error "Phase $target_phase validation failed - aborting deployment"
        return 1
    fi
    
    # Update configuration
    log "Updating feature flags to Phase $target_phase ($percentage%)"
    
    python3 << PYTHON_EOF
import json
from datetime import datetime

try:
    with open('$CONFIG_FILE', 'r') as f:
        config = json.load(f)
    
    phase = $target_phase
    percentage = $percentage
    
    # Update percentage
    config['alfa_rating_enabled']['percentage'] = percentage
    
    # Update metadata
    config['metadata']['phase'] = phase
    config['metadata']['phase_name'] = '$name'
    config['metadata']['last_updated'] = datetime.utcnow().isoformat() + 'Z'
    
    # Enable phase-specific features
    if phase >= 2:
        config['alfa_predictions_in_api']['enabled'] = True
        print("  ✓ Enabled Alfa predictions in API")
    
    if phase >= 3:
        config['alfa_vs_fargo_comparison']['percentage'] = percentage
        print("  ✓ Enabled Alfa vs Fargo comparison")
    
    if phase >= 4:
        config['alfa_anomaly_detection_enabled']['enabled'] = True
        config['alfa_admin_dashboard_enabled']['enabled'] = True
        print("  ✓ Enabled anomaly detection")
        print("  ✓ Enabled admin dashboard")
    
    with open('$CONFIG_FILE', 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"Phase $target_phase deployed successfully")
    
except Exception as e:
    print(f"Deployment failed: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    exit(1)
PYTHON_EOF
    
    if [[ $? -eq 0 ]]; then
        success "Phase $target_phase deployed - $percentage% rollout"
        log "Phase $target_phase deployment completed"
        return 0
    else
        error "Phase $target_phase deployment failed"
        return 1
    fi
}

# Show current status
show_status() {
    echo -e "${CYAN}╔════════════════════════════════╗${NC}"
    echo -e "${CYAN}║    Current Rollout Status      ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════╝${NC}"
    echo ""
    
    if [[ ! -f "$CONFIG_FILE" ]]; then
        error "Configuration file not found"
        return 1
    fi
    
    python3 << PYTHON_EOF
import json

try:
    with open('$CONFIG_FILE', 'r') as f:
        config = json.load(f)
    
    percentage = config['alfa_rating_enabled'].get('percentage', 0)
    
    # Determine phase
    if percentage == 0:
        phase = 0
        phase_name = "Pre-launch"
    elif percentage <= 10:
        phase = 1
        phase_name = "Silent Canary"
    elif percentage <= 25:
        phase = 2
        phase_name = "Shadow Mode"
    elif percentage <= 50:
        phase = 3
        phase_name = "Experimentation"
    elif percentage <= 75:
        phase = 4
        phase_name = "Controlled Expansion"
    else:
        phase = 5
        phase_name = "Full Production"
    
    print(f"Current Phase: {phase} ({phase_name})")
    print(f"Rollout Percentage: {percentage}%")
    print("")
    print("Feature Flags:")
    for flag in ['alfa_rating_enabled', 'alfa_predictions_in_api', 'alfa_anomaly_detection_enabled']:
        if flag in config:
            if config[flag].get('type') == 'percentage':
                status = f"{config[flag].get('percentage', 0)}%"
            else:
                status = "Enabled" if config[flag].get('enabled') else "Disabled"
            print(f"  {flag}: {status}")
    
except Exception as e:
    print(f"Error reading status: {e}")
    exit(1)
PYTHON_EOF
}

# Show metrics
show_metrics() {
    echo -e "${CYAN}Alfa Rating Rollout Metrics${NC}"
    echo ""
    
    # This would read from metrics_latest.json or database
    if [[ -f "$METRICS_FILE" ]]; then
        jq '.' "$METRICS_FILE"
    else
        echo "No metrics available yet"
        echo "(Metrics collected after first deployment)"
    fi
}

# Main
main() {
    check_dependencies
    
    echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║    Alfa Rating System - Rollout Deployment Script      ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    case "${1:-}" in
        deploy)
            target_phase="${2:-1}"
            if ! [[ "$target_phase" =~ ^[0-5]$ ]]; then
                error "Invalid phase: $target_phase (must be 0-5)"
                exit 1
            fi
            
            echo -e "${YELLOW}Deploying Phase $target_phase${NC}"
            read -p "Continue? (yes/no): " confirm
            if [[ "$confirm" != "yes" ]]; then
                log "Deployment cancelled"
                exit 0
            fi
            
            deploy_phase "$target_phase" || exit 1
            show_status
            ;;
        
        validate)
            target_phase="${2:-1}"
            validate_phase "$target_phase" || exit 1
            ;;
        
        status)
            show_status
            ;;
        
        metrics)
            show_metrics
            ;;
        
        schedule)
            show_schedule
            ;;
        
        *)
            echo "Usage: $0 {deploy|validate|status|metrics|schedule} [phase]"
            echo ""
            echo "Commands:"
            echo "  deploy <phase>    Deploy to phase (0-5)"
            echo "  validate <phase>  Validate phase prerequisites"
            echo "  status            Show current rollout status"
            echo "  metrics           Show rollout metrics"
            echo "  schedule          Show deployment schedule"
            exit 1
            ;;
    esac
}

main "$@"
