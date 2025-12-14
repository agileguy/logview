"""Log file discovery service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DiscoveredLog:
    """A discovered log file."""

    path: Path
    name: str
    size_bytes: int
    readable: bool


# File extensions to skip (compressed/binary)
SKIP_EXTENSIONS = {
    ".gz",
    ".bz2",
    ".xz",
    ".zip",
    ".tar",
    ".7z",
    ".rar",
    ".db",
    ".sqlite",
    ".journal",
}

# Common log file names (without extension)
COMMON_LOG_NAMES = {
    "syslog",
    "messages",
    "auth",
    "kern",
    "daemon",
    "mail",
    "cron",
    "boot",
    "dmesg",
    "secure",
    "access",
    "error",
    "debug",
}


def _is_likely_text_file(path: Path) -> bool:
    """Check if a file is likely a text file by reading first few bytes."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(512)
            if not chunk:
                return True  # Empty file

            # Check for null bytes (binary indicator)
            if b"\x00" in chunk:
                return False

            # Check if mostly printable ASCII or UTF-8
            try:
                chunk.decode("utf-8")
                return True
            except UnicodeDecodeError:
                # Try latin-1 as fallback
                try:
                    chunk.decode("latin-1")
                    # Check if mostly printable
                    printable_count = sum(
                        1 for b in chunk if 32 <= b < 127 or b in (9, 10, 13)
                    )
                    return printable_count > len(chunk) * 0.7
                except Exception:
                    return False
    except OSError:
        return False


def _is_readable(path: Path) -> bool:
    """Check if a file is readable by the current user."""
    try:
        return os.access(path, os.R_OK)
    except OSError:
        return False


def _should_skip_file(path: Path) -> bool:
    """Check if a file should be skipped during discovery."""
    # Skip by extension
    if path.suffix.lower() in SKIP_EXTENSIONS:
        return True

    # Skip numbered rotated logs (e.g., syslog.1, syslog.2)
    # but keep the base file
    name = path.name
    if "." in name:
        # Check if it ends with a number (rotated log)
        parts = name.rsplit(".", 1)
        if len(parts) == 2 and parts[1].isdigit():
            return True

    # Skip hidden files
    if name.startswith("."):
        return True

    return False


def _generate_context_name(path: Path, base_dir: Path) -> str:
    """Generate a context name from a file path."""
    try:
        relative = path.relative_to(base_dir)
        # Use path components as name, replacing / with -
        name_parts = list(relative.parts)
        if len(name_parts) > 1:
            return "-".join(name_parts)
        return path.stem or path.name
    except ValueError:
        return path.stem or path.name


def discover_logs(
    search_paths: list[str],
    max_depth: int = 3,
    allowed_directories: list[str] | None = None,
) -> list[DiscoveredLog]:
    """Discover log files in the specified directories.

    Args:
        search_paths: List of directories to search.
        max_depth: Maximum directory depth to traverse.
        allowed_directories: List of allowed directory prefixes for security.

    Returns:
        List of discovered log files.
    """
    allowed_dirs = allowed_directories or ["/var/log", "/opt", "/home"]
    discovered: list[DiscoveredLog] = []
    seen_paths: set[Path] = set()

    for search_path in search_paths:
        # Expand user home directory
        expanded = os.path.expanduser(search_path)
        base_path = Path(expanded).resolve()

        # Security check
        if not _is_path_allowed(base_path, allowed_dirs):
            continue

        if not base_path.exists() or not base_path.is_dir():
            continue

        # Walk the directory tree
        for root, dirs, files in os.walk(base_path):
            root_path = Path(root)

            # Check depth
            try:
                depth = len(root_path.relative_to(base_path).parts)
            except ValueError:
                continue

            if depth > max_depth:
                dirs.clear()  # Don't descend further
                continue

            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith(".")]

            for filename in files:
                file_path = root_path / filename

                # Resolve symlinks to get the real path
                try:
                    resolved = file_path.resolve()
                except OSError:
                    continue

                # Skip if already seen (check only, don't add yet)
                if resolved in seen_paths:
                    continue

                # Security check: validate resolved path is still in allowed directories
                # This prevents symlink escape attacks where a symlink inside an
                # allowed directory points to a file outside the whitelist
                if not _is_path_allowed(resolved, allowed_dirs):
                    continue

                # Apply filters
                if _should_skip_file(file_path):
                    continue

                # Check if readable - skip unreadable files
                if not _is_readable(file_path):
                    continue

                # Check if likely text file
                if not _is_likely_text_file(file_path):
                    continue

                # Only mark as seen after passing all filters
                # This prevents a skipped file from blocking a wanted file with the same target
                seen_paths.add(resolved)

                # Get file size
                try:
                    size = file_path.stat().st_size
                except OSError:
                    size = 0

                # Generate context name
                name = _generate_context_name(file_path, base_path)

                discovered.append(
                    DiscoveredLog(
                        path=resolved,
                        name=name,
                        size_bytes=size,
                        readable=True,  # We already verified readable above
                    )
                )

    # Sort by path for consistent ordering
    discovered.sort(key=lambda d: str(d.path))

    return discovered


def _is_path_allowed(path: Path, allowed_dirs: list[str]) -> bool:
    """Check if a path is within allowed directories."""
    for allowed in allowed_dirs:
        allowed_path = Path(allowed).resolve()
        try:
            path.relative_to(allowed_path)
            return True
        except ValueError:
            continue
    return False


def format_size(size_bytes: int) -> str:
    """Format file size in human-readable form."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
