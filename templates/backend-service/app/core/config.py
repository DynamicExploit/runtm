"""Application configuration."""

import os
from dataclasses import dataclass


@dataclass
class Settings:
    """Application settings loaded from environment.

    Feature flags are set by runtm based on manifest features.
    """

    # Add your configuration here
    # Example:
    # my_api_key: str = os.environ.get("MY_API_KEY", "")

    debug: bool = os.environ.get("DEBUG", "false").lower() == "true"

    # Feature flags (set by runtm based on manifest)
    features_database: bool = os.environ.get("RUNTM_FEATURES_DATABASE", "false").lower() == "true"

    # Database config (only used if features_database=true)
    database_url: str = os.environ.get("DATABASE_URL", "sqlite:////data/app.db")


settings = Settings()
