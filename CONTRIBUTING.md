# Contributing to Runtm

Thank you for your interest in contributing to Runtm! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites

- Python 3.9+
- Docker & Docker Compose
- Git

### Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/runtm.git
   cd runtm
   ```

3. Install development dependencies:
   ```bash
   pip install -e packages/shared[dev]
   pip install -e packages/api[dev]
   pip install -e packages/worker[dev]
   pip install -e packages/cli[dev]
   ```

4. Set up pre-commit hooks:
   ```bash
   pip install pre-commit
   pre-commit install
   ```

## Code Style

We use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting:

```bash
# Check for issues
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

## Testing

Run tests with pytest:

```bash
# All tests
pytest

# Specific package
pytest packages/api/tests

# With coverage
pytest --cov=runtm_api packages/api/tests
```

## Pull Request Process

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/my-feature
   ```

2. Make your changes and ensure:
   - Tests pass: `pytest`
   - Linting passes: `ruff check .`
   - Code is formatted: `ruff format .`

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

## Questions?

Open a GitHub issue or discussion for any questions about contributing.

