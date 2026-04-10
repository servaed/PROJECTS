"""Logging configuration for the application."""

import logging
import sys
from src.config.settings import settings


def setup_logging() -> None:
    """Configure root logger. Call once at application startup."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    fmt = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
    logging.basicConfig(stream=sys.stdout, level=level, format=fmt, force=True)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Use module __name__ as the name."""
    return logging.getLogger(name)
