#!/bin/bash
#
# Staging Deployment Script for Alfa Rating System
# Automates: build, database setup, container startup, health checks, testing
#
# Usage: ./scripts/deploy_staging.sh [--no-cache] [--skip-tests] [--keep-data]
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_ROOT/logs/staging_deployment.log"
DOCKER_COMPOSE_FILE="$PROJECT_ROOT/docker-compose-staging.yml"
DOCKER_BUILD_CONTEXT="$PROJECT_ROOT"
DOCKER_IMAGE_NAME="alfa-api:staging"
DOCKER_FILE="$PROJECT_ROOT/Dockerfile"

# Test configuration
TEST_TIMEOUT=300  # 5 minutes
HEALTH_CHECK_TIMEOUT=10

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
NO_CACHE=${1:-}
SKIP_TESTS=${2:-}
KEEP_DATA=${3:-}

# ============================================================================
# Logging Functions
# ============================================================================

log_header() {
    echo -e "${BLUE}================================================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================================================================${NC}"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}✓ $1${NC}"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✓ $1" >> "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠ $1" >> "$LOG_FILE"
}

log_error() {
    echo -e "${RED}✗ $1${NC}"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✗ $1" >> "$LOG_FILE"
}

# ============================================================================
# Prerequisites Check
# ============================================================================

check_prerequisites() {
    log_header "Checking Prerequisites"
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker not found. Please install Docker."
        exit 1
    fi
    log_success "Docker is available"
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose not found"
        exit 1
    fi
    log_success "Docker Compose is available"
    
    # Check required files
    if [ ! -f "$DOCKER_COMPOSE_FILE" ]; then
        log_error "docker-compose-staging.yml not found"
        exit 1
    fi
    log_success "docker-compose file found"
    
    if [ ! -f "$DOCKER_FILE" ]; then
        log_error "Dockerfile not found"
        exit 1
    fi
    log_success "Dockerfile found"
    
    # Check tunnel_network exists
    if ! docker network ls | grep -q tunnel_network; then
        log_warning "tunnel_network doesn't exist - creating it"
        docker network create tunnel_network || true
    fi
    log_success "tunnel_network available"
    
    # Create logs directory
    mkdir -p "$(dirname "$LOG_FILE")"
    mkdir -p "$PROJECT_ROOT/logs"
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Deployment started" >> "$LOG_FILE"
}

# ============================================================================
# Build Docker Image
# ============================================================================

build_docker_image() {
    log_header "Building Docker Image"
    
    BUILD_ARGS="--build-arg LOG_LEVEL=DEBUG"
    if [ "$NO_CACHE" == "--no-cache" ]; then
        BUILD_ARGS="$BUILD_ARGS --no-cache"
        log_warning "Building without cache (longer build time)"
    fi
    
    echo "Building: $DOCKER_IMAGE_NAME"
    echo "Context: $DOCKER_BUILD_CONTEXT"
    echo "Dockerfile: $DOCKER_FILE"
    
    if docker build $BUILD_ARGS \
        -f "$DOCKER_FILE" \
        -t "$DOCKER_IMAGE_NAME" \
        "$DOCKER_BUILD_CONTEXT" 2>&1 | tee -a "$LOG_FILE"; then
        log_success "Docker image built: $DOCKER_IMAGE_NAME"
    else
        log_error "Docker build failed"
        exit 1
    fi
}

# ============================================================================
# Pull Model Files
# ============================================================================

pull_model_files() {
    log_header "Verifying Model Files"
    
    MODELS_DIR="$PROJECT_ROOT/models"
    
    if [ ! -d "$MODELS_DIR" ]; then
        log_warning "models/ directory not found"
        mkdir -p "$MODELS_DIR"
    fi
    
    # Check for required model files
    required_models=(
        "alfa_logistic_regression.pkl"
        "alfa_anomaly_detection_v2.py"
        "alfa_hyperparameter_search_results.json"
        "alfa_anomaly_thresholds_optimized.json"
    )
    
    for model in "${required_models[@]}"; do
        if [ -f "$MODELS_DIR/$model" ]; then
            log_success "Found: $model"
        else
            log_warning "Missing: $model (will use defaults)"
        fi
    done
}

# ============================================================================
# Start Containers
# ============================================================================

start_containers() {
    log_header "Starting Containers"
    
    # Stop any existing staging containers
    log_warning "Stopping any existing staging containers..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" down || true
    sleep 2
    
    if [ "$KEEP_DATA" != "--keep-data" ]; then
        log_warning "Removing staging volumes (clean slate)"
        docker-compose -f "$DOCKER_COMPOSE_FILE" down -v || true
    else
        log_success "Keeping existing staging data"
    fi
    
    sleep 1
    
    # Start containers; health is verified in perform_health_checks() (HTTP / pg_isready), not fixed delays
    echo "Starting containers from: $DOCKER_COMPOSE_FILE"
    if docker-compose -f "$DOCKER_COMPOSE_FILE" up -d 2>&1 | tee -a "$LOG_FILE"; then
        log_success "Containers started"
    else
        log_error "Failed to start containers"
        exit 1
    fi
}

# ============================================================================
# Health Checks
# ============================================================================

wait_for_health() {
    local service=$1
    local endpoint=$2
    local timeout=${3:-$HEALTH_CHECK_TIMEOUT}
    local start_time=$(date +%s)
    
    echo -n "Waiting for $service..."
    
    while true; do
        current_time=$(date +%s)
        elapsed=$((current_time - start_time))
        
        if [ $elapsed -gt $timeout ]; then
            echo ""
            log_error "$service health check timed out after ${timeout}s"
            return 1
        fi
        
        # Health check logic based on service
        case "$service" in
            "postgres")
                if docker exec alfa-staging-postgres pg_isready -U rankings -d rankings_staging &> /dev/null; then
                    echo " OK"
                    return 0
                fi
                ;;
            "redis")
                if docker exec alfa-staging-redis redis-cli ping &> /dev/null; then
                    echo " OK"
                    return 0
                fi
                ;;
            "api")
                if curl -s http://localhost:8006/api/health &> /dev/null; then
                    echo " OK"
                    return 0
                fi
                ;;
            "prometheus")
                if curl -s http://localhost:9090/-/healthy &> /dev/null; then
                    echo " OK"
                    return 0
                fi
                ;;
            *)
                echo " UNKNOWN"
                return 1
                ;;
        esac
        
        echo -n "."
        sleep 2
    done
}

perform_health_checks() {
    log_header "Performing Health Checks"
    
    # Check if we can reach docker socket
    if ! docker ps &> /dev/null; then
        log_error "Cannot reach Docker daemon"
        exit 1
    fi
    
    # PostgreSQL
    if wait_for_health "postgres" "" 30; then
        log_success "PostgreSQL is healthy"
    else
        log_error "PostgreSQL failed health check"
        docker logs alfa-staging-postgres | tail -20 >> "$LOG_FILE"
        exit 1
    fi
    
    # Redis
    if wait_for_health "redis" "" 10; then
        log_success "Redis is healthy"
    else
        log_error "Redis failed health check"
        exit 1
    fi
    
    # Alfa API
    if wait_for_health "api" "" 60; then
        log_success "Alfa API is healthy"
    else
        log_error "Alfa API failed health check"
        docker logs alfa-api-staging | tail -50 >> "$LOG_FILE"
        exit 1
    fi
    
    # Prometheus
    if wait_for_health "prometheus" "" 15; then
        log_success "Prometheus is healthy"
    else
        log_warning "Prometheus health check timeout (may still be initializing)"
    fi
}

# ============================================================================
# Run Staging Tests
# ============================================================================

run_staging_tests() {
    if [ "$SKIP_TESTS" == "--skip-tests" ]; then
        log_warning "Skipping post-deploy checks as requested"
        return 0
    fi
    log_header "Staging tests"
    log_warning "Automated pytest suite was removed from this repo; use API health and manual checks."
    return 0
}

# ============================================================================
# Update Prometheus Configuration
# ============================================================================

update_prometheus_config() {
    log_header "Updating Prometheus Configuration"
    
    PROM_CONFIG="$PROJECT_ROOT/staging/prometheus/prometheus.yml"
    
    if [ ! -f "$PROM_CONFIG" ]; then
        log_warning "Prometheus config not found: $PROM_CONFIG"
        return 0
    fi
    
    # Reload Prometheus config
    if curl -X POST http://localhost:9090/-/reload 2>/dev/null; then
        log_success "Prometheus configuration reloaded"
    else
        log_warning "Could not reload Prometheus (may not be accessible yet)"
    fi
}

# ============================================================================
# Generate Deployment Status
# ============================================================================

generate_status_report() {
    log_header "Deployment Status Summary"
    
    READY=1
    
    # Check containers
    echo "Container Status:"
    for container in alfa-staging-postgres alfa-staging-redis alfa-api-staging alfa-prometheus-staging alfa-grafana-staging; do
        if docker ps --filter "name=$container" --filter "status=running" -q | grep -q .; then
            echo -e "  ${GREEN}✓${NC} $container is running"
        else
            echo -e "  ${RED}✗${NC} $container is NOT running"
            READY=0
        fi
    done
    
    # Check services
    echo ""
    echo "Service Endpoints:"
    if curl -s http://localhost:8006/api/health &> /dev/null; then
        echo -e "  ${GREEN}✓${NC} Alfa API: http://localhost:8006"
    else
        echo -e "  ${RED}✗${NC} Alfa API: http://localhost:8006 (not responding)"
        READY=0
    fi
    
    if curl -s http://localhost:9090 &> /dev/null; then
        echo -e "  ${GREEN}✓${NC} Prometheus: http://localhost:9090"
    else
        echo -e "  ${RED}✗${NC} Prometheus: http://localhost:9090 (not responding)"
    fi
    
    if curl -s http://localhost:3000 &> /dev/null; then
        echo -e "  ${GREEN}✓${NC} Grafana: http://localhost:3000"
    else
        echo -e "  ${RED}✗${NC} Grafana: http://localhost:3000 (not responding)"
    fi
    
    echo ""
    if [ $READY -eq 1 ]; then
        log_success "✓ STAGING ENVIRONMENT READY"
        echo ""
        echo "Next steps:"
        echo "1. Configure Grafana dashboards: http://localhost:3000 (admin/admin123)"
        echo "2. Review Prometheus alerts: http://localhost:9090/alerts"
        echo "3. Run load tests and validation"
        echo "4. When ready for production: docker-compose -f docker-compose-staging.yml push"
        return 0
    else
        log_warning "⚠ Some services are not ready. Check logs above."
        return 1
    fi
}

# ============================================================================
# Main Execution Flow
# ============================================================================

main() {
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║  Alfa Rating System - Staging Deployment Script               ║"
    echo "║  Environment: Staging | Network: tunnel_network               ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    check_prerequisites
    build_docker_image
    pull_model_files
    start_containers
    perform_health_checks
    run_staging_tests
    update_prometheus_config
    generate_status_report
    
    FINAL_STATUS=$?
    
    log_header "Deployment Complete"
    echo "Log file: $LOG_FILE"
    echo "Review: tail -f $LOG_FILE"
    
    exit $FINAL_STATUS
}

# Run main function
main "$@"
