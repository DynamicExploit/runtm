"""Dependency checking and installation for sandbox runtime.

Handles lazy installation of:
- Bun (or Node.js as fallback)
- sandbox-runtime (@anthropic-ai/sandbox-runtime)
- Claude Code CLI
- bubblewrap (Linux only)
"""

from __future__ import annotations

import platform
import shutil
import subprocess

import structlog

logger = structlog.get_logger()


def check_bun() -> bool:
    """Check if Bun or Node.js is available.

    Returns:
        True if bun or node is found in PATH.
    """
    return shutil.which("bun") is not None or shutil.which("node") is not None


def check_srt() -> bool:
    """Check if sandbox-runtime (srt) is installed.

    Returns:
        True if srt binary is found in PATH.
    """
    return shutil.which("srt") is not None


def check_claude() -> bool:
    """Check if Claude Code CLI is installed.

    Returns:
        True if claude binary is found in PATH.
    """
    return shutil.which("claude") is not None


def check_bwrap() -> bool:
    """Check if bubblewrap is installed (Linux only).

    Returns:
        True if bwrap binary is found in PATH.
    """
    return shutil.which("bwrap") is not None


def get_missing_deps() -> list[tuple[str, callable]]:
    """Get list of missing dependencies.

    Returns:
        List of (name, install_function) tuples for missing deps.
    """
    missing: list[tuple[str, callable]] = []

    if not check_bun():
        missing.append(("Bun runtime", install_bun))

    if not check_srt():
        missing.append(("sandbox-runtime", install_srt))

    if not check_claude():
        missing.append(("Claude Code CLI", install_claude))

    # Only check for bubblewrap on Linux
    if platform.system() == "Linux" and not check_bwrap():
        missing.append(("bubblewrap", install_bwrap))

    return missing


def install_bun() -> bool:
    """Install Bun - single binary, faster than npm.

    Uses the official bun.sh installer script.

    Returns:
        True if installation succeeded.
    """
    logger.info("Installing Bun runtime")
    try:
        result = subprocess.run(
            ["sh", "-c", "curl -fsSL https://bun.sh/install | bash"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            logger.info("Bun installed successfully")
            return True
        else:
            logger.error("Bun installation failed", stderr=result.stderr)
            return False
    except Exception as e:
        logger.error("Bun installation error", error=str(e))
        return False


def install_srt() -> bool:
    """Install sandbox-runtime from npm.

    Prefers bun (faster) over npm.

    Returns:
        True if installation succeeded.
    """
    logger.info("Installing sandbox-runtime")

    # Prefer bun, fall back to npm
    if shutil.which("bun"):
        cmd = ["bun", "install", "-g", "@anthropic-ai/sandbox-runtime"]
    elif shutil.which("npm"):
        cmd = ["npm", "install", "-g", "@anthropic-ai/sandbox-runtime"]
    else:
        logger.error("No package manager available (need bun or npm)")
        return False

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("sandbox-runtime installed successfully")
            return True
        else:
            logger.error("sandbox-runtime installation failed", stderr=result.stderr)
            return False
    except Exception as e:
        logger.error("sandbox-runtime installation error", error=str(e))
        return False


def install_claude() -> bool:
    """Install Claude Code CLI using native installer.

    Uses the official claude.ai installer script which handles
    platform detection, PATH setup, etc.

    Returns:
        True if installation succeeded.
    """
    logger.info("Installing Claude Code CLI")
    try:
        result = subprocess.run(
            ["sh", "-c", "curl -fsSL https://claude.ai/install.sh | bash"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            logger.info("Claude Code CLI installed successfully")
            return True
        else:
            logger.error("Claude Code CLI installation failed", stderr=result.stderr)
            return False
    except Exception as e:
        logger.error("Claude Code CLI installation error", error=str(e))
        return False


def install_bwrap() -> bool:
    """Install bubblewrap (Linux only).

    Detects the package manager and installs accordingly.

    Returns:
        True if installation succeeded.
    """
    logger.info("Installing bubblewrap")

    # Detect package manager and install
    if shutil.which("apt"):
        cmd = ["sudo", "apt", "install", "-y", "bubblewrap"]
    elif shutil.which("dnf"):
        cmd = ["sudo", "dnf", "install", "-y", "bubblewrap"]
    elif shutil.which("pacman"):
        cmd = ["sudo", "pacman", "-S", "--noconfirm", "bubblewrap"]
    elif shutil.which("apk"):
        cmd = ["sudo", "apk", "add", "bubblewrap"]
    else:
        logger.error("No supported package manager found for bubblewrap")
        return False

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("bubblewrap installed successfully")
            return True
        else:
            logger.error("bubblewrap installation failed", stderr=result.stderr)
            return False
    except Exception as e:
        logger.error("bubblewrap installation error", error=str(e))
        return False


def ensure_sandbox_deps(
    auto_approve: bool = False,
    _skip_prompt: bool = False,
) -> bool:
    """Ensure all sandbox dependencies are installed.

    Checks for required dependencies and optionally installs them.

    Args:
        auto_approve: If True, install without prompting.
        _skip_prompt: Internal flag for testing - skip interactive prompt.

    Returns:
        True if all dependencies are available (installed or already present).
    """
    missing = get_missing_deps()

    if not missing:
        logger.debug("All sandbox dependencies present")
        return True

    logger.info("Missing sandbox dependencies", missing=[name for name, _ in missing])

    # If not auto-approving and we're skipping the prompt, return False
    if not auto_approve and _skip_prompt:
        return False

    # If not auto-approving, we would prompt here
    # For now, if not auto_approve, we return False (CLI will handle prompting)
    if not auto_approve:
        return False

    # Install missing dependencies
    for name, install_fn in missing:
        logger.info("Installing dependency", name=name)
        if not install_fn():
            logger.error("Failed to install dependency", name=name)
            return False
        logger.info("Installed dependency", name=name)

    # Verify all deps are now present
    still_missing = get_missing_deps()
    if still_missing:
        logger.error(
            "Some dependencies still missing after installation",
            missing=[name for name, _ in still_missing],
        )
        return False

    logger.info("All sandbox dependencies installed successfully")
    return True
