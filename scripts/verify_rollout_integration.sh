#!/bin/bash
################################################################################
# Alfa Rating Rollout - Integration Verification Script
# 
# Validates that all rollout system components are properly integrated
# and ready for production deployment.
#
# Usage:
#   ./scripts/verify_rollout_integration.sh
#   ./scripts/verify_rollout_integration.sh --fix-issues
################################################################################

set -e

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

ISSUES=()
WARNINGS=()
SUCCESSES=()

# Helper functions
success() {
    echo -e "${GREEN}✓${NC} $1"
    SUCCESSES+=("$1")
}

warning() {
    echo -e "${YELLOW}⚠${NC} $1"
    WARNINGS+=("$1")
}

error() {
    echo -e "${RED}✗${NC} $1"
    ISSUES+=("$1")
}

check_file() {
    local file=$1
    local description=$2
    
    if [[ -f "$file" ]]; then
        success "Found: $description ($file)"
        return 0
    else
        error "Missing: $description ($file)"
        return 1
    fi
}

check_directory() {
    local dir=$1
    local description=$2
    
    if [[ -d "$dir" ]]; then
        success "Found: $description ($dir)"
        return 0
    else
        error "Missing: $description ($dir)"
        return 1
    fi
}

# Main checks
main() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║     Alfa Rating Rollout - Integration Verification     ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    # Check Python modules
    echo -e "${BLUE}Checking Python Modules...${NC}"
    check_file "$PROJECT_ROOT/models/feature_flag_manager.py" "Feature Flag Manager"
    check_file "$PROJECT_ROOT/models/rollout_manager.py" "Rollout Manager"
    
    # Check API components
    echo ""
    echo -e "${BLUE}Checking API Components...${NC}"
    check_file "$PROJECT_ROOT/api/middleware/feature_flags.py" "Feature Flag Middleware"
    check_file "$PROJECT_ROOT/api/routes/admin.py" "Admin Routes"
    
    # Check configuration
    echo ""
    echo -e "${BLUE}Checking Configuration...${NC}"
    check_file "$PROJECT_ROOT/config/feature_flags.json" "Feature Flags Config"
    
    # Check database migrations
    echo ""
    echo -e "${BLUE}Checking Database Migrations...${NC}"
    check_file "$PROJECT_ROOT/database/migrations/rollout_tables.sql" "Rollout Tables Migration"
    
    # Check scripts
    echo ""
    echo -e "${BLUE}Checking Deployment Scripts...${NC}"
    check_file "$PROJECT_ROOT/scripts/rollout_alfa.sh" "Rollout Deploy Script"
    check_file "$PROJECT_ROOT/scripts/rollback_alfa.sh" "Rollback Script"
    
    # Check documentation
    echo ""
    echo -e "${BLUE}Checking Documentation...${NC}"
    check_file "$PROJECT_ROOT/docs/PRODUCTION_ROLLOUT_GUIDE.md" "Production Rollout Guide"
    check_file "$PROJECT_ROOT/docs/ROLLOUT_RUNBOOK.md" "Rollout Runbook"
    check_file "$PROJECT_ROOT/docs/FEATURE_FLAGS_REFERENCE.md" "Feature Flags Reference"
    check_file "$PROJECT_ROOT/docs/ROLLOUT_IMPLEMENTATION_GUIDE.md" "Implementation Guide"
    check_file "$PROJECT_ROOT/docs/ROLLOUT_ADMIN_QUICK_REFERENCE.md" "Admin Quick Reference"
    check_file "$PROJECT_ROOT/docs/ROLLOUT_DEPLOYMENT_CHECKLIST.md" "Deployment Checklist"
    
    # Check monitoring
    echo ""
    echo -e "${BLUE}Checking Monitoring Setup...${NC}"
    check_directory "$PROJECT_ROOT/../monitoring/grafana/dashboards" "Grafana Dashboards Directory"
    if [[ -d "$PROJECT_ROOT/../monitoring/grafana/dashboards" ]]; then
        [[ -f "$PROJECT_ROOT/../monitoring/grafana/dashboards/rollout_metrics.json" ]] && \
            success "Found: Rollout Metrics Dashboard" || \
            warning "Missing: Rollout Metrics Dashboard"
    fi
    
    # Verify Python syntax
    echo ""
    echo -e "${BLUE}Verifying Python Syntax...${NC}"
    python3 -m py_compile "$PROJECT_ROOT/models/feature_flag_manager.py" 2>/dev/null && \
        success "Python syntax OK: feature_flag_manager.py" || \
        error "Syntax error: feature_flag_manager.py"
    
    python3 -m py_compile "$PROJECT_ROOT/models/rollout_manager.py" 2>/dev/null && \
        success "Python syntax OK: rollout_manager.py" || \
        error "Syntax error: rollout_manager.py"
    
    # Verify JSON
    echo ""
    echo -e "${BLUE}Verifying JSON Configuration...${NC}"
    python3 -c "import json; json.load(open('$PROJECT_ROOT/config/feature_flags.json'))" 2>/dev/null && \
        success "JSON valid: feature_flags.json" || \
        error "JSON invalid: feature_flags.json"
    
    # Check feature flag structure
    echo ""
    echo -e "${BLUE}Checking Feature Flag Structure...${NC}"
    python3 << 'EOF'
import json
import sys

try:
    with open("$PROJECT_ROOT/config/feature_flags.json") as f:
        flags = json.load(f)
    
    required_flags = [
        "alfa_rating_enabled",
        "alfa_predictions_in_api",
        "alfa_anomaly_detection_enabled",
        "alfa_vs_fargo_comparison"
    ]
    
    for flag in required_flags:
        if flag in flags:
            print(f"✓ Found flag: {flag}")
        else:
            print(f"✗ Missing flag: {flag}")
            sys.exit(1)
except Exception as e:
    print(f"✗ Error checking flags: {e}")
    sys.exit(1)
EOF
    [[ $? -eq 0 ]] && success "All required flags present" || error "Missing required flags"
    
    # Summary
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}Successes: ${#SUCCESSES[@]}${NC}"
    
    if [[ ${#WARNINGS[@]} -gt 0 ]]; then
        echo -e "${YELLOW}Warnings: ${#WARNINGS[@]}${NC}"
    fi
    
    if [[ ${#ISSUES[@]} -gt 0 ]]; then
        echo -e "${RED}Issues: ${#ISSUES[@]}${NC}"
        echo ""
        for issue in "${ISSUES[@]}"; do
            echo -e "${RED}  - $issue${NC}"
        done
        return 1
    else
        echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
        echo ""
        echo -e "${GREEN}✓ All checks passed! Rollout system is ready for deployment.${NC}"
        return 0
    fi
}

main "$@"
