"""Tests for CLI configuration."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from runtm_cli.config import (
    DEFAULT_API_URL,
    VALID_CONFIG_KEYS,
    CLIConfig,
    get_config_value,
    load_config,
    reset_config,
    save_config,
    set_config_value,
)


def test_default_config():
    """Default config should have expected values."""
    config = CLIConfig()
    assert config.api_url == DEFAULT_API_URL
    assert config.default_template == "backend-service"
    assert config.default_runtime == "python"


def test_config_from_env():
    """Config should load api_url from environment."""
    with patch.dict(
        os.environ,
        {
            "RUNTM_API_URL": "https://custom.api.dev",
        },
    ):
        # Clear cached config
        with patch("runtm_cli.config.CONFIG_FILE", Path("/nonexistent")):
            config = load_config()
            assert config.api_url == "https://custom.api.dev"


def test_save_and_load_config():
    """Config should round-trip through save/load."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "config.yaml"

        with patch("runtm_cli.config.CONFIG_FILE", config_file):
            with patch("runtm_cli.config.CONFIG_DIR", Path(temp_dir)):
                # Save config
                config = CLIConfig(
                    api_url="https://test.api.dev",
                    default_template="web-app",
                )
                save_config(config)

                # Clear env vars that would override
                with patch.dict(os.environ, {}, clear=True):
                    loaded = load_config()
                    assert loaded.api_url == "https://test.api.dev"
                    assert loaded.default_template == "web-app"


def test_set_and_get_config_value():
    """set_config_value and get_config_value should work correctly."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "config.yaml"

        with patch("runtm_cli.config.CONFIG_FILE", config_file):
            with patch("runtm_cli.config.CONFIG_DIR", Path(temp_dir)):
                # Set a value
                set_config_value("api_url", "https://custom.api.dev")

                # Get the value back
                with patch.dict(os.environ, {}, clear=True):
                    value = get_config_value("api_url")
                    assert value == "https://custom.api.dev"


def test_reset_config():
    """reset_config should restore defaults."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "config.yaml"

        with patch("runtm_cli.config.CONFIG_FILE", config_file):
            with patch("runtm_cli.config.CONFIG_DIR", Path(temp_dir)):
                # Set a custom value
                set_config_value("api_url", "https://custom.api.dev")

                # Reset config
                reset_config()

                # Should be back to default
                with patch.dict(os.environ, {}, clear=True):
                    config = load_config()
                    assert config.api_url == DEFAULT_API_URL


def test_valid_config_keys():
    """VALID_CONFIG_KEYS should contain expected keys."""
    assert "api_url" in VALID_CONFIG_KEYS
    assert "default_template" in VALID_CONFIG_KEYS
    assert "default_runtime" in VALID_CONFIG_KEYS


def test_invalid_config_key_raises():
    """Setting an invalid config key should raise ValueError."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "config.yaml"

        with patch("runtm_cli.config.CONFIG_FILE", config_file):
            with patch("runtm_cli.config.CONFIG_DIR", Path(temp_dir)):
                try:
                    set_config_value("invalid_key", "value")
                    raise AssertionError("Should have raised ValueError")
                except ValueError as e:
                    assert "Invalid config key" in str(e)
