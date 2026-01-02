# Contributing to Runtm

Thank you for your interest in contributing to Runtm—the runtime + control plane for agent-built software!

🌐 **Website:** [runtm.com](https://runtm.com) · **Try it free:** [app.runtm.com](https://app.runtm.com)

This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites

- Python 3.9+
- Docker & Docker Compose
- Git
- Fly.io account + API token (for deployment testing)

### Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/runtm.git
   cd runtm
   ```

3. Copy environment template and configure:
   ```bash
   cp infra/local.env.example .env
   # Edit .env and add your FLY_API_TOKEN
   ```

4. Install packages using the dev script:
   ```bash
   ./scripts/dev.sh setup
   ```

   Or manually:
   ```bash
   pip install -e packages/shared[dev]
   pip install -e packages/api[dev]
   pip install -e packages/worker[dev]
   pip install -e packages/cli[dev]
   ```

5. Set up pre-commit hooks:
   ```bash
   pip install pre-commit
   pre-commit install
   ```

### Running Local Services

Start the full local stack (API, worker, database, Redis):

```bash
./scripts/dev.sh up
```

Configure CLI to use local API:
```bash
export RUNTM_API_URL=http://localhost:8000
export RUNTM_API_KEY=dev-token-change-in-production
```

### Dev Script Commands

The `./scripts/dev.sh` helper automatically loads your `.env` file:

| Command | Description |
|---------|-------------|
| `./scripts/dev.sh setup` | Install all packages in dev mode |
| `./scripts/dev.sh up` | Start local services (auto-loads .env) |
| `./scripts/dev.sh down` | Stop local services |
| `./scripts/dev.sh restart` | Restart services (auto-loads .env) |
| `./scripts/dev.sh rebuild` | Rebuild images and restart (after code changes) |
| `./scripts/dev.sh logs [service]` | View logs (e.g., `logs worker`) |
| `./scripts/dev.sh test` | Run tests |
| `./scripts/dev.sh lint` | Run linter |
| `./scripts/dev.sh format` | Format code |

## Code Style

We use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting:

```bash
# Check for issues
./scripts/dev.sh lint
# or: ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
./scripts/dev.sh format
# or: ruff format .
```

## Testing

Run tests with pytest:

```bash
# All tests via dev script
./scripts/dev.sh test

# All tests directly
pytest

# Specific package
pytest packages/api/tests
pytest packages/shared/tests
pytest packages/cli/tests

# With coverage
pytest --cov=runtm_api packages/api/tests
```

## Project Structure

```
packages/
  shared/     # Canonical contracts: manifest schema, types, errors
  api/        # FastAPI control plane
  worker/     # Build + deploy worker (Fly.io provider)
  cli/        # Python CLI (Typer)
  dashboard/  # Next.js admin dashboard

templates/
  backend-service/  # Python FastAPI backend
  static-site/      # Next.js static site
  web-app/          # Fullstack Next.js + FastAPI

infra/
  docker-compose.yml  # Local development stack
```

## Pull Request Process

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/my-feature
   ```

2. Make your changes and ensure:
   - Tests pass: `./scripts/dev.sh test`
   - Linting passes: `./scripts/dev.sh lint`
   - Code is formatted: `./scripts/dev.sh format`

3. Commit with a clear message:
   ```bash
   git commit -m "feat: add new deployment status endpoint"
   ```

4. Push and open a Pull Request

## Commit Message Format

We follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `chore:` Maintenance tasks
- `refactor:` Code refactoring
- `test:` Test additions/changes

## Architecture Guidelines

- **Shared Package**: Canonical contracts only (types, schemas, errors)
- **API Package**: HTTP layer, no business logic in routes
- **Worker Package**: Build/deploy pipeline, provider abstractions
- **CLI Package**: User interface, wraps API client
- **Dashboard**: Admin UI (Next.js + shadcn/ui)

### Key Files

| File | Purpose |
|------|---------|
| `packages/shared/runtm_shared/manifest.py` | Deployment manifest schema (Pydantic) |
| `packages/shared/runtm_shared/types.py` | Shared type definitions |
| `packages/shared/runtm_shared/errors.py` | Error hierarchy |
| `packages/api/runtm_api/routes/deployments.py` | Deployment API endpoints |
| `packages/worker/runtm_worker/jobs/deploy.py` | Build/deploy job logic |
| `packages/worker/runtm_worker/providers/fly.py` | Fly.io provider implementation |
| `packages/cli/runtm_cli/main.py` | CLI command definitions |

### Adding a New CLI Command

1. Create command function in `packages/cli/runtm_cli/commands/`
2. Export from `packages/cli/runtm_cli/commands/__init__.py`
3. Register in `packages/cli/runtm_cli/main.py`
4. Add tests in `packages/cli/tests/`

### Adding a Provider

1. Create provider in `packages/worker/runtm_worker/providers/`
2. Implement the `DeploymentProvider` interface
3. Register in provider factory

## Questions?

- Open a GitHub issue or discussion for any questions about contributing
- Visit [runtm.com](https://runtm.com) to learn more about Runtm
- Try Runtm for free at [app.runtm.com](https://app.runtm.com)

