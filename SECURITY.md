# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in Runtm, please report it responsibly:

1. **Do not** open a public GitHub issue
2. Email security concerns to: security@runtm.com
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will respond within 48 hours and work with you to understand and address the issue.

## Security Measures (V0)

### Authentication
- All API calls require Bearer token authentication
- Tokens are hashed with versioned peppers (supports rotation)
- Tokens should be treated as secrets and never committed to version control

### Rate Limiting
- 10 deployments per hour per token
- Rate limits help prevent abuse and resource exhaustion

### Artifact Limits
- Maximum artifact size: 20 MB
- Protects against zip bombs and resource exhaustion

### Build/Deploy Limits
- Build timeout: 10 minutes
- Deploy timeout: 5 minutes
- Machine tiers with resource limits:
  - Starter: 1 shared CPU, 256 MB memory
  - Standard: 1 shared CPU, 512 MB memory
  - Performance: 2 shared CPUs, 1 GB memory

### Secrets Management
- Secrets stored locally in `.env.local` (never on Runtm servers)
- `.env.local` is auto-added to `.gitignore` and `.cursorignore`
- Secrets marked `secret: true` in `env_schema` are redacted from logs
- Secrets are injected directly to deployment provider at deploy time

### Egress Restrictions
- Deployed workloads have restricted egress by default
- Egress allowlist can be configured in `runtm.yaml`

## Best Practices

1. **Never commit credentials**: Use `runtm secrets set` to store sensitive values
2. **Use env_schema**: Declare required env vars with `secret: true` for proper redaction
3. **Regularly rotate API tokens**: Use `runtm logout` and `runtm login` to refresh
4. **Monitor deployment logs**: Use `runtm logs <id>` to review build and runtime output
5. **Review agent requests**: Use `runtm approve --dry-run` before applying changes

## Secret Storage Architecture

```
                    ┌─────────────────────────────┐
                    │      .env.local (local)     │
                    │   DATABASE_URL=postgres://  │
                    │   API_KEY=sk-xxx            │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │       runtm deploy          │
                    │  (reads .env.local once)    │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │    Fly.io Secrets API       │
                    │  (injected to machine env)  │
                    └─────────────────────────────┘

Runtm servers NEVER store or see secret values.
```

