"""Environment variable loading from project root .env file.

This module provides a centralized way to load environment variables from
a .env file in the project root, making it easy for any part of the codebase
to access configuration.

IMPORTANT: This module does NOT auto-load .env on import. The API and Worker
should explicitly call ensure_env_loaded() at startup. The CLI should NOT
call this as it runs in user projects and shouldn't load the monorepo's .env.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def find_project_root(start_path: Optional[Path] = None) -> Optional[Path]:
    """Find the project root directory.

    Looks for marker files like pyproject.toml, README.md, or .git directory
    to identify the project root.

    Args:
        start_path: Starting directory (defaults to current file's directory)

    Returns:
        Path to project root, or None if not found
    """
    if start_path is None:
        # Start from the directory containing this file (packages/shared/runtm_shared)
        # Go up to project root: packages/shared/runtm_shared -> packages/shared -> packages -> root
        start_path = Path(__file__).parent.parent.parent.parent

    current = Path(start_path).resolve()

    # Look for project root markers
    markers = ["pyproject.toml", "README.md", ".git", "infra/docker-compose.yml"]

    # Walk up the directory tree
    for parent in [current] + list(current.parents):
        for marker in markers:
            if (parent / marker).exists():
                return parent

    return None


def load_env_file(env_file: str = ".env", project_root: Optional[Path] = None) -> bool:
    """Load environment variables from .env file in project root.

    This function:
    1. Finds the project root directory
    2. Looks for .env file in the root
    3. Loads it using python-dotenv
    4. Works both locally and in Docker containers

    Args:
        env_file: Name of the env file (default: ".env")
        project_root: Optional project root path (auto-detected if not provided)

    Returns:
        True if .env file was found and loaded, False otherwise

    Example:
        >>> from runtm_shared.env import load_env_file
        >>> load_env_file()  # Loads .env from project root
        >>> import os
        >>> token = os.environ.get("FLY_API_TOKEN")
    """
    if project_root is None:
        project_root = find_project_root()

    if project_root is None:
        # If we can't find project root, try current working directory
        project_root = Path.cwd()

    env_path = project_root / env_file

    if env_path.exists():
        load_dotenv(env_path, override=False)  # Don't override existing env vars
        return True

    return False


# Track if .env has been loaded (used by ensure_env_loaded)
_loaded = False


def ensure_env_loaded() -> None:
    """Ensure .env file is loaded (idempotent).

    Call this explicitly in API and Worker startup. The CLI should NOT call
    this as it runs in user projects and shouldn't load the monorepo's .env.

    Can be called multiple times safely - only loads once.
    """
    global _loaded
    if not _loaded:
        load_env_file()
        _loaded = True


# NOTE: We intentionally do NOT auto-load .env on module import.
# The CLI runs in user projects and shouldn't load the monorepo's .env.
# API and Worker should call ensure_env_loaded() explicitly at startup.
