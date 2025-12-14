"""Application logging setup."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from logview.config.schema import LoggingSettings

# Module-level logger for logview
logger = logging.getLogger("logview")

# Default log location
DEFAULT_LOG_DIR = Path.home() / ".config" / "logview"
DEFAULT_LOG_FILE = DEFAULT_LOG_DIR / "logview.log"


def setup_logging(settings: LoggingSettings | None = None) -> None:
    """Configure application logging based on settings.

    Args:
        settings: Logging configuration. Uses defaults if None.
    """
    # Import here to avoid circular imports
    from logview.config.schema import LoggingSettings

    if settings is None:
        settings = LoggingSettings()

    # Get log level
    level = getattr(logging, settings.level, logging.WARNING)

    # Determine log file path
    if settings.file:
        log_file = Path(os.path.expanduser(settings.file))
    else:
        log_file = DEFAULT_LOG_FILE

    # Ensure log directory exists
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Configure the logview logger
    logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create rotating file handler
    max_bytes = settings.max_size_mb * 1024 * 1024
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=settings.backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(level)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)

    # Add handler
    logger.addHandler(file_handler)

    # Don't propagate to root logger
    logger.propagate = False

    logger.info("Logging initialized at level %s, file: %s", settings.level, log_file)


def get_logger(name: str) -> logging.Logger:
    """Get a child logger for a specific module.

    Args:
        name: The module name (e.g., 'adapters.gcp').

    Returns:
        A logger instance.
    """
    return logging.getLogger(f"logview.{name}")
