#!/bin/bash
# Analyze deployment performance and identify bottlenecks.
# Times scripts/build_frontend_with_docker.sh (requires Docker).

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$APP_ROOT"

echo "🔍 Deployment Performance Analysis"
echo "=================================="

START_TIME=$(date +%s)

if ! command -v docker &>/dev/null; then
  echo "ERROR: Docker required for build_frontend_with_docker.sh" >&2
  exit 1
fi

echo "⏱️  Timing frontend build (Docker)..."
FRONTEND_START=$(date +%s)
"$APP_ROOT/scripts/build_frontend_with_docker.sh" > /dev/null 2>&1
FRONTEND_END=$(date +%s)
FRONTEND_TIME=$((FRONTEND_END - FRONTEND_START))
echo "   Frontend build (containerized): ${FRONTEND_TIME}s"

echo "⏱️  Docker Build Estimation..."
echo "   Typical Docker image build: 120-180s (with layer caching)"
echo "   With --no-cache: 240-360s (full rebuild)"
echo "   Current system: $(nproc) CPU cores, $(free -h | grep '^Mem:' | awk '{print $7}') available RAM"

DOCKER_ESTIMATE=180
TOTAL_ESTIMATE=$((FRONTEND_TIME + DOCKER_ESTIMATE + 30))

echo ""
echo "📊 Performance Breakdown:"
echo "   Frontend build (Docker): ${FRONTEND_TIME}s"
echo "   Docker build (estimated): ${DOCKER_ESTIMATE}s"
echo "   Container startup: 30s"
echo "   ──────────────────────────────"
echo "   Total estimated: ${TOTAL_ESTIMATE}s (~$(echo "scale=1; $TOTAL_ESTIMATE/60" | bc) minutes)"

echo ""
echo "🎯 Optimization Recommendations:"
echo "   1. Use Docker layer caching (avoid --no-cache for normal deployments)"
echo "   2. Pre-build in CI with cache-from / registry mirrors where appropriate"
echo "   3. Use multi-stage builds for smaller images"
echo "   4. Enable Docker BuildKit for parallel builds"
echo "   5. Optimize Python dependencies (remove unused packages)"

END_TIME=$(date +%s)
ANALYSIS_TIME=$((END_TIME - START_TIME))
echo "   Analysis completed in ${ANALYSIS_TIME}s"
