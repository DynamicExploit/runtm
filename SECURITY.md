# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in Runtm, please report it responsibly:

1. **Do not** open a public GitHub issue
2. Email security concerns to: security@runtm.dev
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will respond within 48 hours and work with you to understand and address the issue.

## Security Measures (V0)

### Authentication
- All API calls require Bearer token authentication
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
- Memory per machine: 256 MB

### Egress Restrictions
- Deployed workloads have restricted egress by default
- No secrets/env injection in V0 (explicitly out of scope)

## Best Practices

1. Never commit API tokens or credentials
2. Use environment variables for sensitive configuration
3. Regularly rotate API tokens
4. Monitor deployment logs for suspicious activity

