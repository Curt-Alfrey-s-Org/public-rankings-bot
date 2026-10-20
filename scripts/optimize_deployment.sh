#!/bin/bash
# Optimize deployment performance for rankings bot
# Addresses the 450-500 second deployment time issue

set -e

echo "🚀 Optimizing Rankings Bot Deployment Performance"

# 1. Analyze current system resources
echo "📊 System Resource Analysis:"
echo "CPU Cores: $(nproc)"
echo "Memory: $(free -h | grep '^Mem:' | awk '{print $2 " total, " $7 " available"}')"
echo "Disk: $(df -h / | tail -1 | awk '{print $4 " available"}')"

# 2. Optimize Docker build performance
echo "🐳 Optimizing Docker Build Performance..."

# Create optimized Dockerfile with better layer caching
cat > Dockerfile.optimized << 'EOF'
# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

# Environment variables for better pip performance
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_INPUT=1 \
    PIP_DEFAULT_TIMEOUT=300 \
    PIP_ROOT_USER_ACTION=ignore \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Single layer for system dependencies (rarely changes)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy and install Python dependencies first (changes infrequently)
COPY requirements-api.txt requirements-deps.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt -r requirements-deps.txt

# Copy application code (changes frequently)
COPY api/ /app/api/
COPY scrapers/ /app/scrapers/
COPY database/ /app/database/
COPY scripts/ /app/scripts/
COPY alembic/ /app/alembic/
COPY alembic.ini *.py /app/
RUN mkdir -p /app/frontend/dist

EXPOSE 8003
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8003/api/health || exit 1

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8003"]
EOF

# 3. Optimize frontend build
echo "⚛️  Optimizing Frontend Build..."

# Create optimized vite config for faster builds
cat > frontend/vite.config.optimized.js << 'EOF'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    target: 'esnext',
    minify: 'esbuild',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          ui: ['lucide-react', '@tanstack/react-query'],
          utils: ['axios', 'zustand']
        }
      }
    },
    chunkSizeWarningLimit: 1000
  },
  server: {
    host: true
  }
})
EOF

# 4. Optimize Docker Compose for performance
echo "📦 Optimizing Docker Compose..."

# Create performance-optimized docker-compose
cat > docker-compose.performance.yml << 'EOF'
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: rankingsbot
      POSTGRES_USER: rankingsbot_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    # No ports: Postgres is Docker-network-only
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-db.sql:/docker-entrypoint-initdb.d/01-init.sql:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-rankingsbot_user} -d ${POSTGRES_DB:-rankingsbot}"]
      interval: 5s
      timeout: 3s
      retries: 3
      start_period: 5s
    networks:
      - rankings-bot-network
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M

  redis:
    image: redis:7-alpine
    ports:
      - '127.0.0.1:6379:6379'
    volumes:
      - redis_data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3
      start_period: 2s
    networks:
      - rankings-bot-network
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 256M
        reservations:
          cpus: '0.25'
          memory: 128M

  rankings-bot-api:
    build:
      context: .
      dockerfile: Dockerfile.optimized
      args:
        BUILDKIT_INLINE_CACHE: 1
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER:-rankingsbot_user}:${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}@postgres:5432/${POSTGRES_DB:-rankingsbot}
      CELERY_BROKER_URL: redis://redis:6379/0
      REDIS_URL: redis://redis:6379/0
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      - '127.0.0.1:8003:8003'
    volumes:
      - ./frontend/dist:/app/frontend/dist:ro
      - ./logs:/app/logs
      - ./pools_coaching_frames:/app/pools_coaching_frames
      - ./config:/app/config
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8003/api/health"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 10s
    networks:
      - rankings-bot-network
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G

  celery-worker:
    build:
      context: .
      dockerfile: Dockerfile.optimized
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER:-rankingsbot_user}:${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}@postgres:5432/${POSTGRES_DB:-rankingsbot}
      CELERY_BROKER_URL: redis://redis:6379/0
      REDIS_URL: redis://redis:6379/0
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./logs:/app/logs
      - ./pools_coaching_frames:/app/pools_coaching_frames
      - ./config:/app/config
    restart: unless-stopped
    networks:
      - rankings-bot-network
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M

volumes:
  postgres_data:
  redis_data:

networks:
  rankings-bot-network:
    driver: bridge
EOF

# 5. Create deployment timing analysis script
echo "⏱️  Creating Deployment Analysis Script..."

cat > scripts/analyze_deployment_performance.sh << 'EOF'
#!/bin/bash
# Analyze deployment performance (times build_frontend_with_docker.sh; requires Docker).
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$APP_ROOT"
echo "🔍 Deployment Performance Analysis"
echo "=================================="
START_TIME=$(date +%s)
if ! command -v docker &>/dev/null; then
  echo "ERROR: Docker required." >&2
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
echo "   2. Pre-build in CI with cache-from where appropriate"
echo "   3. Use multi-stage builds for smaller images"
echo "   4. Enable Docker BuildKit for parallel builds"
echo "   5. Optimize Python dependencies (remove unused packages)"
END_TIME=$(date +%s)
ANALYSIS_TIME=$((END_TIME - START_TIME))
echo "   Analysis completed in ${ANALYSIS_TIME}s"
EOF

chmod +x scripts/analyze_deployment_performance.sh

# 6. Update full_deploy.sh to use optimizations
echo "🔧 Updating full_deploy.sh for better performance..."

# Backup original
cp scripts/full_deploy.sh scripts/full_deploy.sh.backup

# Add performance optimizations
sed -i 's/--no-cache//g' scripts/full_deploy.sh
sed -i 's/DOCKER_BUILDKIT=0/DOCKER_BUILDKIT=1/g' scripts/full_deploy.sh

# 7. Create summary
echo ""
echo "✅ Deployment Optimization Complete!"
echo ""
echo "🚀 Performance Improvements:"
echo "   • Removed --no-cache for faster builds"
echo "   • Enabled BuildKit for parallel builds"
echo "   • Optimized resource allocation"
echo "   • Created performance analysis tools"
echo ""
echo "📈 Expected Results:"
echo "   • First deployment: 450-500s (current)"
echo "   • Subsequent deployments: 90-150s (with caching)"
echo "   • CI/CD deployments: 60-90s (optimized)"
echo ""
echo "🛠️  Available Tools:"
echo "   • scripts/analyze_deployment_performance.sh - Performance analysis"
echo "   • docker-compose.performance.yml - Optimized compose file"
echo "   • Dockerfile.optimized - Optimized Docker build"
echo ""
echo "🎯 Next Steps:"
echo "   1. Test with: ./scripts/full_deploy.sh (no --no-cache)"
echo "   2. Analyze with: ./scripts/analyze_deployment_performance.sh"
echo "   3. For production: use docker-compose.performance.yml"