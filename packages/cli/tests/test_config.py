"""Tests for CLI configuration."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from runtm_cli.config import CLIConfig, load_config, save_config


def test_default_config():
    """Default config should have expected values."""
    config = CLIConfig()
    assert config.api_url == "https://api.runtm.dev"
    assert config.token is None
    assert config.default_template == "backend-service"


def test_config_from_env():
    """Config should load from environment."""
    with patch.dict(os.environ, {
        "RUNTM_API_URL": "https://custom.api.dev",
        "RUNTM_TOKEN": "my-token",
    }):
        # Clear cached config
        with patch("runtm_cli.config.CONFIG_FILE", Path("/nonexistent")):
            config = load_config()
            assert config.api_url == "https://custom.api.dev"
            assert config.token == "my-token"


def test_save_and_load_config():
    """Config should round-trip through save/load."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "config.yaml"

        with patch("runtm_cli.config.CONFIG_FILE", config_file):
            with patch("runtm_cli.config.CONFIG_DIR", Path(temp_dir)):
                # Save config
                config = CLIConfig(
                    api_url="https://test.api.dev",
                    token="test-token",
                )
                save_config(config)

                # Clear env vars that would override
                with patch.dict(os.environ, {}, clear=True):
                    loaded = load_config()
                    assert loaded.api_url == "https://test.api.dev"
                    assert loaded.token == "test-token"

