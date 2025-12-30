# runtm-cli

CLI for Runtm: deploy AI-generated code to live URLs.

## Installation

```bash
pip install runtm-cli
```

## Commands

| Command | Description |
|---------|-------------|
| `runtm init backend-service` | Scaffold from template |
| `runtm run` | Run project locally (auto-detects runtime) |
| `runtm validate` | Validate project before deployment |
| `runtm deploy [path]` | Deploy project to a live URL |
| `runtm status <id>` | Show deployment status |
| `runtm logs <id>` | Show logs (build, deploy, runtime) |
| `runtm list` | List all deployments |
| `runtm destroy <id>` | Destroy a deployment |

### Machine Tiers

All deployments use **auto-stop** for cost savings (machines stop when idle and start automatically on traffic).

| Tier | CPUs | Memory | Est. Cost | Use Case |
|------|------|--------|-----------|----------|
| **starter** (default) | 1 shared | 256MB | ~$2/month* | Simple tools, APIs |
| **standard** | 1 shared | 512MB | ~$5/month* | Most workloads |
| **performance** | 2 shared | 1GB | ~$10/month* | Full-stack apps |

*Costs are estimates for 24/7 operation. With auto-stop, costs are much lower for low-traffic services.

## Usage

```bash
# Initialize a new backend service project
runtm init backend-service

# Run locally (auto-detects runtime and port)
runtm run

# Validate before deploying
runtm validate

# Deploy to a live URL (uses starter tier by default)
runtm deploy

# Deploy with a specific tier
runtm deploy --tier standard
runtm deploy --tier performance

# Check deployment status
runtm status dep_abc123

# View logs
runtm logs dep_abc123
```

### Setting Machine Tier

You can specify the machine tier in two ways:

1. **Via CLI flag** (overrides manifest):
   ```bash
   runtm deploy --tier standard
   runtm deploy --tier performance
   ```

2. **In `runtm.yaml`** (persistent setting):
   ```yaml
   name: my-service
   template: backend-service
   runtime: python
   tier: standard  # Options: starter, standard, performance
   ```

## Redeployment (CI/CD)

Runtm supports automatic redeployment based on the project name in `runtm.yaml`. When you deploy a project with the same name as an existing deployment:

- The **existing infrastructure is updated** (same URL)
- A new **version** is created
- The **previous version** is marked as not latest

```bash
# First deploy - creates new deployment
runtm deploy                   # → v1, creates new URL

# Fix a bug, then redeploy - updates existing
runtm deploy                   # → v2, same URL, updated code

# Force a completely new deployment
runtm deploy --new             # → v1, new deployment, new URL
```

This enables CI/CD workflows where an agent or user can:
1. Build code
2. Deploy with `runtm deploy`
3. Find and fix bugs
4. Redeploy with `runtm deploy` (same command, updates in place)

## Logs

The `logs` command provides comprehensive access to build, deploy, and runtime logs.

```bash
# All logs (build + deploy + recent runtime)
runtm logs dep_abc123

# Filter by log type
runtm logs dep_abc123 --type runtime
runtm logs dep_abc123 --type build

# More runtime log lines
runtm logs dep_abc123 --lines 100

# Search logs
runtm logs dep_abc123 --search "error"
runtm logs dep_abc123 --search "error,warning,timeout"  # OR logic

# Pipe to grep (Heroku-style)
runtm logs dep_abc123 --raw | grep "error"

# JSON output for AI agents
runtm logs dep_abc123 --json
```

### Log Options

| Option | Short | Description |
|--------|-------|-------------|
| `--type TYPE` | `-t` | Filter: `build`, `deploy`, `runtime` |
| `--lines N` | `-n` | Runtime log lines (default: 20) |
| `--search TEXT` | `-s` | Filter by text, comma-separated, or regex |
| `--json` | | JSON output for programmatic access |
| `--raw` | | Raw output for piping to grep/awk |

## Configuration

The CLI stores configuration in `~/.runtm/config.yaml`:

```yaml
api_url: https://api.runtm.dev
token: your-api-token
```

Environment variables override config file:
- `RUNTM_API_URL` - API endpoint
- `RUNTM_TOKEN` - API token

## Development

```bash
# Install in editable mode
pip install -e ".[dev]"

# Configure CLI to use local API (add to ~/.zshrc or ~/.bashrc)
export RUNTM_API_URL=http://localhost:8000
export RUNTM_TOKEN=dev-token-change-in-production

# Run tests
pytest
```

