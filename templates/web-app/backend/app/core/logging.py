"""Logging configuration."""

import logging
import sys


def setup_logging(debug: bool = False) -> None:
    """Configure application logging.
    
    Args:
        debug: Enable debug level logging
    """
    level = logging.DEBUG if debug else logging.INFO
    
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    
    # Reduce noise from uvicorn access logs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

