"""Local configuration management for Runtm CLI."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, ConfigDict


# Default paths
CONFIG_DIR = Path.home() / ".runtm"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


class CLIConfig(BaseModel):
    """CLI configuration stored in ~/.runtm/config.yaml."""

    model_config = ConfigDict(extra="ignore")

    # API connection
    # Routes through Cloud Backend proxy which validates API keys
    # and forwards to internal OSS API with service token
    api_url: str = "https://app.runtm.com/api"
    token: Optional[str] = None

    # Cloud Backend URL (for API key validation during login)
    # The CLI validates user API keys against the Cloud Backend,
    # which is the public-facing auth layer.
    cloud_url: str = "https://app.runtm.com"

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
    1. Environment variables (RUNTM_API_URL, RUNTM_TOKEN)
    2. Config file (~/.runtm/config.yaml)
    3. Defaults

    Returns:
        CLIConfig instance
    """
    config_file = get_config_file()

    # Start with defaults
    config_data = {}

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
    if os.environ.get("RUNTM_TOKEN"):
        config_data["token"] = os.environ["RUNTM_TOKEN"]
    if os.environ.get("RUNTM_CLOUD_URL"):
        config_data["cloud_url"] = os.environ["RUNTM_CLOUD_URL"]

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

    # Only save token if it's set (don't write None)
    if config.token:
        data["token"] = config.token

    content = yaml.safe_dump(data, default_flow_style=False)
    config_file.write_text(content)


def get_token() -> Optional[str]:
    """Get API token from config or environment.

    Returns:
        API token if configured, None otherwise
    """
    config = load_config()
    return config.token


def set_token(token: str) -> None:
    """Set API token in config file.

    Args:
        token: API token to save
    """
    config = load_config()
    config.token = token
    save_config(config)


def clear_token() -> None:
    """Remove API token from config file."""
    config = load_config()
    config.token = None
    save_config(config)


def get_api_url() -> str:
    """Get API URL from config or environment.

    Returns:
        API URL
    """
    config = load_config()
    return config.api_url


def get_cloud_url() -> str:
    """Get Cloud Backend URL from config or environment.

    The Cloud Backend is the public-facing auth layer where users
    create/manage API keys. The CLI validates keys against this endpoint.

    Returns:
        Cloud Backend URL
    """
    config = load_config()
    return config.cloud_url


def get_config() -> dict:
    """Get configuration as a dictionary.

    Returns:
        Configuration dictionary with api_url, token, etc.
    """
    config = load_config()
    return {
        "api_url": config.api_url,
        "token": config.token,
        "default_template": config.default_template,
        "default_runtime": config.default_runtime,
    }

