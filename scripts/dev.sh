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

        # 1. Create/activate virtual environment
        if [ ! -d ".venv" ]; then
            echo "Creating virtual environment..."
            python3 -m venv .venv
        fi

        echo "Activating virtual environment..."
        source .venv/bin/activate

        # 2. Upgrade pip
        pip install --upgrade pip

        # 3. Install Python packages in development mode
        echo ""
        echo "Installing Python packages..."
        pip install -e packages/shared[dev]
        pip install -e packages/sandbox[dev]
        pip install -e packages/agents[dev]
        pip install -e packages/api[dev]
        pip install -e packages/worker[dev]
        pip install -e "packages/cli[dev,sandbox]"

        # 4. Install pre-commit hooks
        pip install pre-commit
        pre-commit install

        # 5. Install sandbox dependencies (bun, sandbox-runtime, claude)
        echo ""
        echo "Installing sandbox dependencies..."

        # Install Bun if not present
        if ! command -v bun &> /dev/null; then
            echo "  Installing Bun..."
            curl -fsSL https://bun.sh/install | bash
            export BUN_INSTALL="$HOME/.bun"
            export PATH="$BUN_INSTALL/bin:$PATH"
        else
            echo "  ✓ Bun already installed"
        fi

        # Install sandbox-runtime if not present
        if ! command -v srt &> /dev/null; then
            echo "  Installing sandbox-runtime..."
            if command -v bun &> /dev/null; then
                bun install -g @anthropic-ai/sandbox-runtime
            elif command -v npm &> /dev/null; then
                npm install -g @anthropic-ai/sandbox-runtime
            else
                echo "  ⚠ Could not install sandbox-runtime (no bun or npm)"
            fi
        else
            echo "  ✓ sandbox-runtime already installed"
        fi

        # Install Claude CLI if not present
        if ! command -v claude &> /dev/null; then
            echo "  Installing Claude Code CLI..."
            curl -fsSL https://claude.ai/install.sh | bash
        else
            echo "  ✓ Claude Code CLI already installed"
        fi

        echo ""
        echo "============================================"
        echo "Development environment ready!"
        echo ""
        echo "If this is your first time, reload your shell:"
        echo "  source ~/.zshrc   # or restart terminal"
        echo ""
        echo "Then run:"
        echo "  source .venv/bin/activate"
        echo "  runtm-dev start"
        echo "============================================"
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

    check)
        echo "Running all pre-commit checks..."
        cd "$PROJECT_ROOT"
        ruff check . && ruff format --check .
        echo "All checks passed!"
        ;;

    *)
        echo "Usage: $0 {setup|up|down|restart|rebuild|reset-db|logs|migrate|test|lint|format|check}"
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
        echo "  check    - Run all checks (lint + format check) without modifying files"
        echo ""
        echo "Note: Migrations are automatically applied when the API container starts."
        exit 1
        ;;
esac
