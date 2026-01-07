# Runtm

[![License: AGPL v3](https://img.shields.io/badge/Server-AGPLv3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![License: Apache 2.0](https://img.shields.io/badge/CLI-Apache%202.0-green.svg)](https://opensource.org/licenses/Apache-2.0)
[![License: MIT](https://img.shields.io/badge/Templates-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Discord](https://img.shields.io/discord/1342243238748225556?logo=discord&logoColor=white&color=7289DA)](https://discord.com/invite/JUuCkUKc)

Runtime and control plane for agent-built software. Deploy AI-generated tools and apps to live URLs in minutes.

This repo powers our [hosted services](https://docs.runtm.com). Sign up at [app.runtm.com](https://app.runtm.com).

## Demo

https://github.com/user-attachments/assets/8d6d5ab8-a5c4-4a3d-8ef1-5d20b67ed3ee

## Installation

```bash
# Recommended
uv tool install runtm

# Alternative
pipx install runtm

# Or with pip
pip install runtm
```

## Quick Start

```bash
# Authenticate (get your free key at app.runtm.com)
runtm login

# Create a new project from a template
runtm init backend-service

# Run locally (auto-detects runtime, uses Bun if available)
runtm run

# Deploy to a live URL
runtm deploy
```

You get a live HTTPS endpoint on auto-stopping infrastructure. Machines spin down when idle and wake up on traffic.

## Templates

Runtm ships with three templates. Each deploys without edits out of the box.

| Template | Runtime | What it's for |
|----------|---------|---------------|
| `backend-service` | Python (FastAPI) | APIs, webhooks, agent backends |
| `static-site` | Node (Next.js) | Landing pages, docs, static content |
| `web-app` | Fullstack (Next.js + FastAPI) | Dashboards, portals, interactive apps |

```bash
runtm init backend-service   # or static-site, web-app
```

All templates include SQLite database support and can connect to external services via environment variables. The `web-app` template also supports authentication via Better Auth.

See the [templates docs](https://docs.runtm.com/templates/overview) for details.

## Key Commands

| Command | Description |
|---------|-------------|
| `runtm login` | Authenticate with your API key |
| `runtm init <template>` | Scaffold a new project |
| `runtm run` | Run locally |
| `runtm deploy` | Deploy to production |
| `runtm logs <id>` | View build, deploy, and runtime logs |
| `runtm status <id>` | Check deployment status |
| `runtm destroy <id>` | Tear down a deployment |

See the [CLI docs](https://docs.runtm.com/cli/overview) for the full command reference.

## How It Works

The CLI packages your project and sends it to the API. The API queues a build job, and a worker builds a container image and deploys it to the provider.

```
┌─────┐      ┌─────┐      ┌────────┐      ┌────────┐
│ CLI │ ──▶  │ API │ ──▶  │ Worker │ ──▶  │Provider│
└─────┘      └─────┘      └────────┘      └────────┘
```

Deployments go through states: `queued` → `building` → `deploying` → `ready` (or `failed`).

## Project Structure

```
packages/
  shared/     # Types, manifest schema, errors
  api/        # FastAPI control plane
  worker/     # Build + deploy pipeline
  cli/        # Python CLI (Typer)

templates/
  backend-service/
  static-site/
  web-app/
```

## Self-Hosting

Runtm can be fully self-hosted. See the [self-hosting guide](https://docs.runtm.com/self-hosting/overview) for setup instructions.

```bash
git clone https://github.com/runtm-ai/runtm.git
cd runtm
cp infra/local.env.example .env
docker compose -f infra/docker-compose.yml up -d
```

## Documentation

Full documentation at [docs.runtm.com](https://docs.runtm.com):

- [Quickstart](https://docs.runtm.com/quickstart)
- [CLI Reference](https://docs.runtm.com/cli/overview)
- [API Reference](https://docs.runtm.com/api/overview)
- [Templates](https://docs.runtm.com/templates/overview)
- [Features](https://docs.runtm.com/features/database) (database, auth, custom domains, machine tiers)
- [Self-Hosting](https://docs.runtm.com/self-hosting/overview)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

| Component | License |
|-----------|---------|
| Server (api, worker, infra) | [AGPLv3](packages/api/LICENSE) |
| CLI, Shared | [Apache-2.0](packages/cli/LICENSE) |
| Templates | [MIT](templates/LICENSE) |

## Support

For issues, questions, or feedback, [open an issue](https://github.com/runtm-ai/runtm/issues) or join our [Discord](https://discord.com/invite/JUuCkUKc).
