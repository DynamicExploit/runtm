"""Application configuration."""

import os
from dataclasses import dataclass


@dataclass
class Settings:
    """Application settings loaded from environment.

    Feature flags are set by runtm based on manifest features.
    """

    # Server configuration
    debug: bool = os.environ.get("DEBUG", "false").lower() == "true"

    # CORS settings - allow frontend origin
    cors_origins: list[str] = None

    # Feature flags (set by runtm based on manifest)
    features_database: bool = os.environ.get("RUNTM_FEATURES_DATABASE", "false").lower() == "true"
    features_auth: bool = os.environ.get("RUNTM_FEATURES_AUTH", "false").lower() == "true"

    # Database config (only used if features_database=true)
    database_url: str = os.environ.get("DATABASE_URL", "sqlite:////data/app.db")

    def __post_init__(self):
        if self.cors_origins is None:
            # Default to allowing all origins in development
            origins_str = os.environ.get("CORS_ORIGINS", "*")
            self.cors_origins = [o.strip() for o in origins_str.split(",")]


settings = Settings()
