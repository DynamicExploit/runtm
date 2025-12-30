#!/bin/bash
# Development helper script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load .env file if it exists (exports all variables)
load_env() {
    if [ -f "$PROJECT_ROOT/.env" ]; then
        set -a
        source "$PROJECT_ROOT/.env"
        set +a
        echo "✓ Loaded environment from .env"
    else
        echo "⚠ No .env file found. Copy infra/local.env.example to .env"
    fi
}

case "$1" in
    setup)
        echo "Setting up development environment..."
        cd "$PROJECT_ROOT"
        
        # Install packages in development mode
        pip install -e packages/shared[dev]
        pip install -e packages/api[dev]
        pip install -e packages/worker[dev]
        pip install -e packages/cli[dev]
        
        echo "Development environment ready!"
        ;;
    
    up)
        echo "Starting local services..."
        cd "$PROJECT_ROOT"
        load_env
        docker compose -f infra/docker-compose.yml --env-file .env up -d
        echo "Services started. API available at http://localhost:8000"
        ;;
    
    down)
        echo "Stopping local services..."
        cd "$PROJECT_ROOT"
        docker compose -f infra/docker-compose.yml --env-file .env down
        ;;
    
    restart)
        echo "Restarting services..."
        cd "$PROJECT_ROOT"
        load_env
        docker compose -f infra/docker-compose.yml --env-file .env down
        docker compose -f infra/docker-compose.yml --env-file .env up -d
        echo "Services restarted. API available at http://localhost:8000"
        ;;
    
    rebuild)
        echo "Rebuilding and restarting services..."
        cd "$PROJECT_ROOT"
        load_env
        docker compose -f infra/docker-compose.yml --env-file .env build
        docker compose -f infra/docker-compose.yml --env-file .env up -d
        echo "Services rebuilt and started. API available at http://localhost:8000"
        echo "Note: Database migrations are automatically applied on API startup."
        ;;
    
    reset-db)
        echo "Resetting database (drops all data and reapplies migrations)..."
        cd "$PROJECT_ROOT"
        load_env
        docker compose -f infra/docker-compose.yml --env-file .env down -v
        docker compose -f infra/docker-compose.yml --env-file .env up -d
        echo "Database reset complete. All data cleared and migrations applied."
        ;;
    
    logs)
        cd "$PROJECT_ROOT"
        docker compose -f infra/docker-compose.yml --env-file .env logs -f "${@:2}"
        ;;
    
    migrate)
        echo "Running database migrations..."
        cd "$PROJECT_ROOT/packages/api"
        alembic upgrade head
        ;;
    
    test)
        echo "Running tests..."
        cd "$PROJECT_ROOT"
        pytest "${@:2}"
        ;;
    
    lint)
        echo "Running linter..."
        cd "$PROJECT_ROOT"
        ruff check .
        ;;
    
    format)
        echo "Formatting code..."
        cd "$PROJECT_ROOT"
        ruff format .
        ;;
    
    *)
        echo "Usage: $0 {setup|up|down|restart|rebuild|reset-db|logs|migrate|test|lint|format}"
        echo ""
        echo "Commands:"
        echo "  setup    - Install packages in development mode"
        echo "  up       - Start local services (auto-loads .env, runs migrations)"
        echo "  down     - Stop local services"
        echo "  restart  - Restart services (auto-loads .env)"
        echo "  rebuild  - Rebuild and restart services (auto-loads .env)"
        echo "  reset-db - Reset database (drops all data, reapplies migrations)"
        echo "  logs     - View service logs (e.g., ./dev.sh logs worker)"
        echo "  migrate  - Run database migrations (manual, for local dev without docker)"
        echo "  test     - Run tests"
        echo "  lint     - Run linter"
        echo "  format   - Format code"
        echo ""
        echo "Note: Migrations are automatically applied when the API container starts."
        exit 1
        ;;
esac

