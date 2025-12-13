"""Configuration file loader."""

from __future__ import annotations

import json
from pathlib import Path

from logview.config.schema import Config


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
        return Config()

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    return Config.model_validate(data)


def save_config(config: Config, path: Path | None = None) -> None:
    """Save configuration to a JSON file.

    Args:
        config: The configuration to save.
        path: Path to save to. If None, uses the default path.
    """
    if path is None:
        path = get_default_config_path()

    # Ensure directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(config.model_dump(), f, indent=2)
