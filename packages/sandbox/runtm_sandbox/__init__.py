"""Runtm Sandbox - OS-level isolated environments for AI coding agents.

Uses Anthropic's sandbox-runtime (bubblewrap on Linux, seatbelt on macOS)
for fast, secure process isolation. Same technology as Claude Code.
"""

__version__ = "0.1.0"

from runtm_sandbox.providers.base import SandboxProvider
from runtm_sandbox.providers.local import LocalSandboxProvider

__all__ = [
    "SandboxProvider",
    "LocalSandboxProvider",
]
