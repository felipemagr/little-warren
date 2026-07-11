"""Loguru logging configuration."""

import sys

from loguru import logger


def configure_logging(level: str = "INFO") -> None:
    """Configure the global loguru logger with a concise console sink."""
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - {message}",
    )
