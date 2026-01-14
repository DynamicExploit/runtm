# runtm

CLI for Runtm – sandboxes where AI agents build and deploy.

**Website:** [runtm.com](https://runtm.com) · **Docs:** [docs.runtm.com](https://docs.runtm.com) · **Sign up:** [app.runtm.com](https://app.runtm.com)

## Installation

**Recommended (uv):**
```bash
uv tool install runtm
```

**Alternative (pipx):**
```bash
pipx install runtm
```

**From PyPI (pip):**
```bash
pip install runtm
```

### Upgrading

```bash
# Upgrade to latest version (uv)
uv tool upgrade runtm

# Or force reinstall
uv tool install runtm --force

# With pipx
pipx upgrade runtm

# With pip
pip install --upgrade runtm
```

## Quick Start

```bash
# 1. Authenticate with Runtm
runtm login

# 2. Spin up a sandbox and start building
runtm init backend-service

# 3. Deploy to a live URL
runtm deploy
```

You get a live HTTPS endpoint. Machines auto-stop when idle and wake on traffic.

## Commands

| Command | Description |
|---------|-------------|
| `runtm login` | Authenticate with Runtm API |
| `runtm logout` | Remove saved credentials |
| `runtm doctor` | Check CLI setup and diagnose issues |
| `runtm start` | Start a sandbox session (interactive menu) |
| `runtm attach [id]` | Attach to a sandbox (defaults to active) |
| `runtm prompt "..."` | Send a prompt to the agent |
| `runtm init` | Initialize a new project from template |
| `runtm run` | Run project locally (auto-detects runtime) |
| `runtm validate` | Validate project before deployment |
| `runtm deploy [path]` | Deploy project to a live URL |
| `runtm status <id>` | Show deployment status |
| `runtm logs <id>` | Show logs (build, deploy, runtime) |
| `runtm list` | List all deployments |
| `runtm destroy <id>` | Destroy a deployment |
| `runtm config set/get/list` | Manage CLI configuration |

### Authentication

Get your free API key at **[app.runtm.com](https://app.runtm.com)**. The CLI will prompt you to authenticate on first use.

```bash
# Manual login
runtm login

# Login with token directly
runtm login --token runtm_sk_xxx

# Check auth status
runtm doctor

# Logout
runtm logout
```

**Token storage:**
- Primary: `~/.runtm/credentials` file (0o600 permissions)
- Optional: System keychain (if `keyring` package installed)

**Environment variable override:**
```bash
export RUNTM_API_KEY=runtm_sk_xxx  # Overrides stored token
```

### Configuration

```bash
# Set API URL (for self-hosting)
runtm config set api_url=https://self-hosted.example.com/api

# Get a config value
runtm config get api_url

# List all config values
runtm config list

# Reset to defaults
runtm config reset
```

**Config file:** `~/.runtm/config.yaml`

**Environment variables:**
- `RUNTM_API_URL` - API endpoint (overrides config)
- `RUNTM_API_KEY` - API key (overrides stored token)

### Troubleshooting

```bash
# Check CLI setup and diagnose issues
runtm doctor
```

Example output:
```
runtm v0.2.6
  API URL:      https://app.runtm.com/api
  Auth storage: keychain (api_token@app.runtm.com)
  Auth status:  ✓ Authenticated as user@example.com
  Connectivity: ✓ API reachable (142ms)

  Ready to deploy! Run: runtm init
```

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
# Spin up a sandbox
runtm init

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

This enables workflows where an agent can:
1. Build code
2. Deploy with `runtm deploy`
3. Find and fix bugs using logs
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

## Development

```bash
# Install in editable mode with sandbox support
pip install -e ".[dev,sandbox]"
pip install -e ../sandbox
pip install -e ../agents

# Use the development CLI (avoids conflicts with PyPI version)
runtm-dev start                    # Start sandbox session
runtm-dev prompt "Build an API"    # Send prompt to agent
runtm-dev list                     # List sessions

# Configure CLI to use local API (add to ~/.zshrc or ~/.bashrc)
export RUNTM_API_URL=http://localhost:8000
export RUNTM_API_KEY=dev-token-change-in-production

# Run tests
pytest
```

### `runtm` vs `runtm-dev`

| CLI | Source | Use Case |
|-----|--------|----------|
| `runtm` | PyPI (`pip install runtm`) | Production use |
| `runtm-dev` | Local `.venv/` | Development (includes sandbox/agents) |

If you have the PyPI version installed globally, use `runtm-dev` to ensure you're running your local development code with full sandbox support.
