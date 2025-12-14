"""Configuration file loader."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from logview.config.schema import Config

logger = logging.getLogger("logview.config.loader")


def get_default_config_path() -> Path:
    """Get the default configuration file path.

    Returns:
        Path to ~/.config/logview/config.json
    """
    return Path.home() / ".config" / "logview" / "config.json"


def load_config(path: Path | None = None) -> Config:
    """Load configuration from a JSON file.

    Args:
        path: Path to the config file. If None, uses the default path.

    Returns:
        Parsed Config object. Returns default config if file doesn't exist.
    """
    if path is None:
        path = get_default_config_path()

    if not path.exists():
        logger.info("Config file not found, using defaults: %s", path)
        return Config()

    logger.info("Loading config from %s", path)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    config = Config.model_validate(data)
    logger.info("Loaded config: %d contexts, logging level=%s", len(config.contexts), config.logging.level)
    return config


def save_config(config: Config, path: Path | None = None) -> None:
    """Save configuration to a JSON file.

    Args:
        config: The configuration to save.
        path: Path to save to. If None, uses the default path.
    """
    if path is None:
        path = get_default_config_path()

    logger.debug("Saving config to %s", path)

    # Ensure directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(config.model_dump(), f, indent=2)

    logger.info("Config saved to %s", path)
