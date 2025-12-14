"""LogView - A testable, responsive log viewer TUI."""

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def _read_version() -> str:
    """Read version from package metadata or VERSION file.

    For installed packages, uses importlib.metadata.
    For development, falls back to VERSION file.
    """
    # Try importlib.metadata first (works for installed packages)
    try:
        return version("logview")
    except PackageNotFoundError:
        pass

    # Fall back to VERSION file (development mode)
    version_file = Path(__file__).parent.parent.parent / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()

    return "0.0.0"  # Last resort fallback


__version__ = _read_version()
