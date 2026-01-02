# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2025-01-01

### Added

- Initial open source release
- **CLI**: `runtm` command-line tool for deploying AI-generated code
  - `runtm init` - Scaffold from templates (backend-service, static-site, web-app)
  - `runtm run` - Run projects locally with auto-detection (uses Bun if available)
  - `runtm deploy` - Deploy to live URLs with machine tiers
  - `runtm fix` - Auto-fix common project issues (lockfiles)
  - `runtm validate` - Validate projects before deployment
  - `runtm status` - Check deployment status
  - `runtm logs` - View build, deploy, and runtime logs with search/filtering
  - `runtm list` - List all deployments
  - `runtm search` - Search deployments by description/tags
  - `runtm destroy` - Destroy deployments
  - `runtm login/logout` - Authentication management
  - `runtm secrets set/get/list/unset` - Manage environment variables
  - `runtm domain add/status/remove` - Custom domain management
  - `runtm approve` - Apply agent-proposed changes
  - `runtm admin create-token/revoke-token/list-tokens` - Self-host token management
- **API**: FastAPI control plane for deployment management
- **Worker**: Build and deploy pipeline with Fly.io provider
- **Templates**: 
  - `backend-service` - Python FastAPI backend
  - `static-site` - Next.js static site
  - `web-app` - Fullstack Next.js + FastAPI
- **Features**:
  - Machine tiers (starter, standard, performance) with auto-stop
  - Environment variable management with secret redaction
  - Custom domain support with SSL certificates
  - Optional SQLite database with persistence
  - Optional authentication (web-app template)
  - Agent workflow support via `runtm.requests.yaml`
  - Lockfile validation and auto-fix

### Security

- Bearer token authentication for all API calls
- Rate limiting (10 deployments/hour per token)
- Artifact size limits (20 MB max)
- Build/deploy timeouts
- Secret redaction in logs

[Unreleased]: https://github.com/runtm-ai/runtm/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/runtm-ai/runtm/releases/tag/v0.1.0
