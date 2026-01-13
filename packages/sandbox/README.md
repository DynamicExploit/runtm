# runtm-sandbox

OS-level isolated environments for AI coding agents.

Uses Anthropic's [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime) for fast, secure process isolation - the same technology used by Claude Code.

## Features

- **Fast startup** - <100ms (no containers)
- **OS-level isolation** - bubblewrap (Linux) / seatbelt (macOS)
- **Network filtering** - Domain allowlist proxy
- **Filesystem isolation** - Write restrictions to workspace only

## Installation

```bash
pip install runtm-sandbox
```

## Usage

```python
from runtm_sandbox import LocalSandboxProvider
from runtm_shared.types import SandboxConfig

provider = LocalSandboxProvider()

# Create a sandbox
sandbox = provider.create("sbx_123", SandboxConfig())

# Attach to sandbox (runs isolated shell)
exit_code = provider.attach("sbx_123")

# Clean up
provider.destroy("sbx_123")
```

## Requirements

- Python 3.11+
- sandbox-runtime (`npm install -g @anthropic-ai/sandbox-runtime`)
- bubblewrap (Linux only: `apt install bubblewrap`)
