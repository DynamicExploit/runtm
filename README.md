# Runtm

> Runtm: deploy AI-generated tools and apps to live URLs in minutes.

Runtm is an open-source runtime that turns AI-generated code into live, governed endpoints. One command → deployed URL.

## Quick Start

```bash
# Install the CLI
pip install runtm-cli

# Initialize a new backend service project
runtm init backend-service

# Run locally (auto-detects runtime)
runtm run

# Deploy to a live URL
runtm deploy
```

## Architecture

```
packages/
  shared/     # Canonical contracts: manifest schema, types, errors
  api/        # FastAPI control plane
  worker/     # Build + deploy worker (Fly.io provider)
  cli/        # Python CLI (Typer)

templates/
  backend-service/  # Python FastAPI backend (API, webhooks, agents)
  static-site/      # Next.js static site (landing pages, docs)
  web-app/          # Fullstack Next.js + FastAPI (dashboards, apps)

infra/
  docker-compose.yml  # Local development stack
```

## Development

### Prerequisites

- Python 3.9+
- Docker & Docker Compose
- Fly.io account + API token (for deployments)

### Local Setup

```bash
# Clone the repository
git clone https://github.com/runtm-ai/runtm.git
cd runtm

# Copy environment template and configure
cp infra/local.env.example .env
# Edit .env and add your FLY_API_TOKEN

# Install packages in development mode
./scripts/dev.sh setup

# Start local services (auto-loads .env)
./scripts/dev.sh up

# Configure CLI to use local API
export RUNTM_API_URL=http://localhost:8000
export RUNTM_TOKEN=dev-token-change-in-production
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

### Running Tests

```bash
# Run all tests
./scripts/dev.sh test

# Run specific package tests
pytest packages/shared/tests
pytest packages/api/tests
```

### Linting

```bash
# Check code style
./scripts/dev.sh lint

# Format code
./scripts/dev.sh format
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `runtm init backend-service` | Scaffold from template |
| `runtm run` | Run project locally (auto-detects runtime) |
| `runtm validate` | Validate project before deployment |
| `runtm deploy [path]` | Deploy project to a live URL |
| `runtm status <id>` | Show deployment status |
| `runtm logs <id>` | Show logs (build, deploy, and runtime) |
| `runtm list` | List all deployments |
| `runtm destroy <id>` | Destroy a deployment |
| `runtm login` | Authenticate with Runtm |
| `runtm secrets set/get/list/unset` | Manage environment secrets |
| `runtm approve` | Apply agent-proposed changes |

### Machine Tiers

Runtm supports three machine tiers, all with **auto-stop enabled** for cost savings (machines stop when idle and start automatically on traffic):

| Tier | CPUs | Memory | Est. Cost | Use Case |
|------|------|--------|-----------|----------|
| **starter** (default) | 1 shared | 256MB | ~$2/month* | Simple tools, APIs |
| **standard** | 1 shared | 512MB | ~$5/month* | Most workloads |
| **performance** | 2 shared | 1GB | ~$10/month* | Full-stack apps |

*Costs are estimates for 24/7 operation. With auto-stop, costs are much lower for low-traffic services.

**Usage:**

```bash
# Deploy with default starter tier
runtm deploy

# Deploy with standard tier
runtm deploy --tier standard

# Deploy with performance tier for full-stack apps
runtm deploy --tier performance
```

You can also set the tier in `runtm.yaml`:

```yaml
name: my-service
template: backend-service
runtime: python
tier: standard  # Options: starter, standard, performance
```

## Environment Variables & Secrets

Runtm provides a simple, secure way to manage environment variables and secrets for your deployments.

### Declaring Environment Variables

Define required env vars in your `runtm.yaml`:

```yaml
name: my-service
template: backend-service
runtime: python
tier: starter

env_schema:
  - name: DATABASE_URL
    type: url
    required: true
    secret: true
    description: "PostgreSQL connection string"
  - name: API_KEY
    type: string
    required: true
    secret: true
  - name: LOG_LEVEL
    type: string
    required: false
    default: "info"
```

**Supported types:** `string`, `url`, `number`, `boolean`

### Managing Secrets

```bash
# Set a secret (stored in .env.local, gitignored)
runtm secrets set DATABASE_URL=postgres://...

# List all env vars and their status
runtm secrets list

# Get a secret value
runtm secrets get DATABASE_URL

# Remove a secret
runtm secrets unset DATABASE_URL
```

### Security Features

- **`.env.local` is auto-gitignored** - Secrets never get committed
- **`.env.local` is auto-cursorignored** - AI agents can't see secret values
- **Secrets are redacted from logs** - Values marked `secret: true` are replaced with `[REDACTED]`
- **Deploy-time validation** - Missing required env vars block deployment

### Connections (Named Secret Bundles)

Group related env vars as named connections:

```yaml
env_schema:
  - name: SUPABASE_URL
    type: url
    required: true
  - name: SUPABASE_ANON_KEY
    type: string
    required: true
    secret: true

connections:
  - name: supabase
    env_vars: [SUPABASE_URL, SUPABASE_ANON_KEY]
```

### Agent-Proposed Changes

AI agents can propose features, env vars, and connections via `runtm.requests.yaml`:

```yaml
# runtm.requests.yaml (created by AI agent)
requested:
  features:
    database: true
    auth: true
    reason: "Building a SaaS app with user accounts"
  env_vars:
    - name: AUTH_SECRET
      type: string
      secret: true
      required: true
      reason: "Required for auth session signing"
    - name: STRIPE_API_KEY
      secret: true
      required: true
      reason: "Needed for payment processing"
  egress_allowlist:
    - "api.stripe.com"
notes:
  - "Adding auth and Stripe integration"
```

Review and apply with one command:

```bash
# Preview changes
runtm approve --dry-run

# Apply changes to manifest
runtm approve

# Set required secrets
runtm secrets set AUTH_SECRET=$(openssl rand -base64 32)
runtm secrets set STRIPE_API_KEY=sk_xxx
```

This workflow allows agents to propose changes (including enabling database/auth features) while keeping humans in the approval loop.

## Viewing Logs

Runtm provides comprehensive log access for debugging and monitoring deployments.

### Basic Usage

```bash
# View all logs (build + deploy + recent runtime)
runtm logs dep_abc123

# View only runtime logs
runtm logs dep_abc123 --type runtime

# View only build logs
runtm logs dep_abc123 --type build

# View more runtime log lines (default: 20)
runtm logs dep_abc123 --lines 100
```

### Searching and Filtering

```bash
# Single keyword search
runtm logs dep_abc123 --search "error"

# Multiple keywords (OR logic)
runtm logs dep_abc123 --search "error,warning,failed"

# Regex patterns
runtm logs dep_abc123 --search "HTTP.*[45]\d\d"
```

### Pipe-Friendly Output (Heroku-style)

```bash
# Raw output for piping to grep
runtm logs dep_abc123 --raw | grep "error"

# Filter by log type AND keyword
runtm logs dep_abc123 --raw | grep "\[RUNTIME\]" | grep -i "database"

# Advanced filtering with regex
runtm logs dep_abc123 --raw | grep -E "error|timeout|failed"
```

### JSON Output for AI Agents

```bash
# JSON output for programmatic access
runtm logs dep_abc123 --json

# Parse with jq
runtm logs dep_abc123 --json | jq '.logs[] | select(.type == "runtime")'

# Python example
python -c "
import subprocess, json
result = subprocess.run(['runtm', 'logs', 'dep_abc123', '--json'], capture_output=True, text=True)
logs = json.loads(result.stdout)
for log in logs['logs']:
    if 'error' in log['content'].lower():
        print(f'Error in {log[\"type\"]}: {log[\"content\"][:100]}...')
"
```

### Log Options Reference

| Option | Short | Description |
|--------|-------|-------------|
| `--type TYPE` | `-t` | Filter by type: `build`, `deploy`, `runtime` |
| `--lines N` | `-n` | Number of runtime log lines (default: 20) |
| `--search TEXT` | `-s` | Filter logs by text, comma-separated, or regex |
| `--json` | | Output as JSON for programmatic access |
| `--raw` | | Raw output for piping to grep/awk |
| `--follow` | `-f` | Follow logs in real-time (coming soon) |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v0/deployments` | List deployments |
| POST | `/v0/deployments` | Create deployment (supports `?tier=starter|standard|performance`) |
| GET | `/v0/deployments/:id` | Get deployment status |
| GET | `/v0/deployments/:id/logs` | Get build/deploy logs |
| DELETE | `/v0/deployments/:id` | Destroy deployment |

### Creating Deployments

```bash
# Create deployment with tier override
curl -X POST "https://api.runtm.dev/v0/deployments?tier=performance" \
  -H "Authorization: Bearer $RUNTM_TOKEN" \
  -F "manifest=@runtm.yaml" \
  -F "artifact=@artifact.zip"
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `RUNTM_API_TOKEN` | API authentication token | Yes |
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `REDIS_URL` | Redis connection string | Yes |
| `FLY_API_TOKEN` | Fly.io API token | Yes (worker) |
| `ARTIFACT_STORAGE_PATH` | Local artifact storage path | Yes |

## Optional Features

Runtm templates support optional features that can be enabled in `runtm.yaml`.

### Database (SQLite with Persistence)

Enable persistent SQLite storage for your deployments:

```yaml
# runtm.yaml
features:
  database: true
```

This automatically:
- Creates a persistent Fly volume at `/data`
- Initializes SQLite with WAL mode for better performance
- Auto-runs migrations on startup

**Usage in backend code:**

```python
from fastapi import Depends
from sqlalchemy.orm import Session
from app.db import Base, get_db

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

@router.get("/items")
def get_items(db: Session = Depends(get_db)):
    return db.query(Item).all()
```

**External PostgreSQL:** Set `DATABASE_URL` env var to use external Postgres instead of SQLite.

> ⚠️ **SQLite limitation:** Single writer only. For horizontal scaling, use external PostgreSQL.

### Authentication (web-app only)

Enable user authentication with Better Auth:

```yaml
# runtm.yaml
features:
  database: true  # Required
  auth: true

env_schema:
  - name: AUTH_SECRET
    type: string
    required: true
    secret: true
```

Generate a secret: `openssl rand -base64 32`

**Frontend usage:**

```tsx
// Protect routes
import { AuthGuard } from "@/components/auth";
<AuthGuard><ProtectedContent /></AuthGuard>

// Client-side hooks
import { useSession, signIn, signOut } from "@/lib/auth-client";
```

**Included components:** `LoginForm`, `SocialButtons`, `MagicLinkForm`, `AuthGuard`

## Guardrails (V0)

- Artifact size: 20 MB max
- Build timeout: 10 minutes
- Deploy timeout: 5 minutes
- Machine tiers: starter (256MB, 1 CPU), standard (512MB, 1 CPU), performance (1GB, 2 CPUs)
- All machines use auto-stop for cost savings
- Max deployments/hour: 10 per token

## License

MIT

