"""Local configuration management for Runtm CLI.

Configuration is stored in ~/.runtm/config.yaml.
Token storage is handled separately by auth.py (keychain/file).

Config keys:
- api_url: API endpoint (default: https://app.runtm.com/api)
- default_template: Default template for init
- default_runtime: Default runtime
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

# Default paths
CONFIG_DIR = Path.home() / ".runtm"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

# Default API URL
DEFAULT_API_URL = "https://app.runtm.com/api"

# Valid config keys that can be set via `runtm config set`
VALID_CONFIG_KEYS = {"api_url", "default_template", "default_runtime"}


class CLIConfig(BaseModel):
    """CLI configuration stored in ~/.runtm/config.yaml.

    Note: Token is stored separately via auth.py (keychain or credentials file).
    """

    model_config = ConfigDict(extra="ignore")

    # API endpoint
    api_url: str = DEFAULT_API_URL

    # Default settings
    default_template: str = "backend-service"
    default_runtime: str = "python"


def get_config_dir() -> Path:
    """Get the config directory path."""
    return CONFIG_DIR


def get_config_file() -> Path:
    """Get the config file path."""
    return CONFIG_FILE


def ensure_config_dir() -> Path:
    """Ensure config directory exists.

    Returns:
        Path to config directory
    """
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def load_config() -> CLIConfig:
    """Load configuration from file and environment.

    Priority (highest to lowest):
    1. Environment variables (RUNTM_API_URL)
    2. Config file (~/.runtm/config.yaml)
    3. Defaults

    Returns:
        CLIConfig instance
    """
    config_file = get_config_file()

    # Start with defaults
    config_data: dict[str, Any] = {}

    # Load from file if exists
    if config_file.exists():
        try:
            content = config_file.read_text()
            file_data = yaml.safe_load(content)
            if isinstance(file_data, dict):
                config_data.update(file_data)
        except Exception:
            pass  # Use defaults if file is invalid

    # Override with environment variables
    if os.environ.get("RUNTM_API_URL"):
        config_data["api_url"] = os.environ["RUNTM_API_URL"]

    return CLIConfig.model_validate(config_data)


def save_config(config: CLIConfig) -> None:
    """Save configuration to file.

    Args:
        config: Configuration to save
    """
    ensure_config_dir()
    config_file = get_config_file()

    data = {
        "api_url": config.api_url,
        "default_template": config.default_template,
        "default_runtime": config.default_runtime,
    }

    content = yaml.safe_dump(data, default_flow_style=False)
    config_file.write_text(content)


def get_api_url() -> str:
    """Get API URL from config or environment.

    Returns:
        API URL
    """
    config = load_config()
    return config.api_url


def set_api_url(api_url: str) -> None:
    """Set API URL in config file.

    Args:
        api_url: API URL to save
    """
    config = load_config()
    config.api_url = api_url
    save_config(config)


def get_config() -> dict:
    """Get configuration as a dictionary.

    Returns:
        Configuration dictionary with api_url, default_template, etc.
    """
    config = load_config()
    return {
        "api_url": config.api_url,
        "default_template": config.default_template,
        "default_runtime": config.default_runtime,
    }


def set_config_value(key: str, value: str) -> None:
    """Set a single config value.

    Args:
        key: Config key (api_url, default_template, default_runtime)
        value: Value to set

    Raises:
        ValueError: If key is not a valid config key
    """
    if key not in VALID_CONFIG_KEYS:
        valid_keys = ", ".join(sorted(VALID_CONFIG_KEYS))
        raise ValueError(f"Invalid config key: {key}. Valid keys: {valid_keys}")

    config = load_config()
    setattr(config, key, value)
    save_config(config)


def get_config_value(key: str) -> str | None:
    """Get a single config value.

    Args:
        key: Config key to get

    Returns:
        Config value or None if key doesn't exist

    Raises:
        ValueError: If key is not a valid config key
    """
    if key not in VALID_CONFIG_KEYS:
        valid_keys = ", ".join(sorted(VALID_CONFIG_KEYS))
        raise ValueError(f"Invalid config key: {key}. Valid keys: {valid_keys}")

    config = load_config()
    return getattr(config, key, None)


def reset_config() -> None:
    """Reset configuration to defaults."""
    config = CLIConfig()
    save_config(config)


# Legacy compatibility - these delegate to auth.py
# Kept for backward compatibility with older scripts


def get_token() -> str | None:
    """Get API token (delegates to auth.py).

    DEPRECATED: Use runtm_cli.auth.get_token() instead.
    """
    from runtm_cli.auth import get_token as auth_get_token

    return auth_get_token()


def set_token(token: str) -> None:
    """Set API token (delegates to auth.py).

    DEPRECATED: Use runtm_cli.auth.set_token() instead.
    """
    from runtm_cli.auth import set_token as auth_set_token

    auth_set_token(token)


def clear_token() -> None:
    """Clear API token (delegates to auth.py).

    DEPRECATED: Use runtm_cli.auth.clear_token() instead.
    """
    from runtm_cli.auth import clear_token as auth_clear_token

    auth_clear_token()
