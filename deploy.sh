#!/bin/bash
# Rankings-Bot Production Start/Stop Helper
# Usage: ./deploy.sh [start|stop|restart|status|logs|health]
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="production/docker-compose.prod.yml"
ENV_FILE=".env"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[rankings-bot]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

case "$1" in
    start)
        print_status "Starting Rankings-Bot production stack..."
        cd "$PROJECT_ROOT"
        sudo docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --wait
        print_status "Services started (Compose --wait satisfied healthchecks). Status:"
        sudo docker ps -f name="rankings-bot" --format "table {{.Names}}\t{{.Status}}"
        ;;
    
    stop)
        print_status "Stopping Rankings-Bot production stack..."
        cd "$PROJECT_ROOT"
        sudo docker compose -f "$COMPOSE_FILE" down
        print_status "Services stopped."
        ;;
    
    restart)
        print_status "Restarting Rankings-Bot production stack..."
        cd "$PROJECT_ROOT"
        sudo docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" restart
        sudo docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --wait
        print_status "Services restarted (Compose --wait satisfied healthchecks)."
        ;;
    
    status)
        print_status "Rankings-Bot Service Status:"
        sudo docker ps -f name="rankings-bot" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        ;;
    
    logs)
        service="${2:-api}"
        case "$service" in
            api)
                print_status "Showing API logs (latest 50 lines)..."
                sudo docker logs rankings-bot-api --tail=50 -f
                ;;
            celery)
                print_status "Showing Celery worker logs (latest 50 lines)..."
                sudo docker logs rankings-bot-celery-worker --tail=50 -f
                ;;
            frontend)
                print_status "Showing Frontend logs (latest 50 lines)..."
                sudo docker logs rankings-bot-frontend --tail=50 -f
                ;;
            *)
                print_status "Showing all Rankings-Bot logs..."
                sudo docker logs rankings-bot-api --tail=20
                sudo docker logs rankings-bot-celery-worker --tail=20
                ;;
        esac
        ;;
    
    health)
        print_status "Checking Rankings-Bot Health..."
        echo
        echo "API Health:"
        curl -s http://localhost:8003/api/health | python3 -m json.tool 2>/dev/null || echo "API not responding"
        echo
        echo "Frontend Health:"
        curl -s -o /dev/null -w "Frontend status: %{http_code}\n" http://localhost:5176/
        echo
        print_status "Full Health Check:"
        curl -s http://localhost:8003/api/health/detailed | python3 -m json.tool 2>/dev/null || echo "Detailed health unavailable"
        ;;
    
    build)
        print_status "Building application images (no cache)..."
        cd "$PROJECT_ROOT"
        sudo docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build --no-cache
        print_status "Build complete."
        ;;
    
    *)
        echo "Rankings-Bot Production Helper"
        echo ""
        echo "Usage: $0 {start|stop|restart|status|logs|health|build}"
        echo ""
        echo "Commands:"
        echo "  start     - Start the production stack"
        echo "  stop      - Stop the production stack"
        echo "  restart   - Restart all services"
        echo "  status    - Show current container status"
        echo "  logs      - Show service logs (api|celery|frontend)"
        echo "  health    - Run health checks"
        echo "  build     - Build images without cache"
        echo ""
        echo "Examples:"
        echo "  $0 start"
        echo "  $0 logs api"
        echo "  $0 health"
        exit 1
        ;;
esac
