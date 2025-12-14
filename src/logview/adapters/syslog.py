"""Syslog file adapter for reading local syslog files."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING

from logview.adapters.syslog_parser import ParsedSyslogLine, SyslogParseError, parse_syslog_line
from logview.domain.models import FilterField, LogEntry, Severity

if TYPE_CHECKING:
    from logview.domain.models import Filter


class SyslogError(Exception):
    """Base exception for syslog adapter errors."""

    pass


class SyslogFileNotFoundError(SyslogError):
    """Raised when the syslog file cannot be found."""

    def __init__(self, path: Path) -> None:
        self.path = path
        # Security: Don't expose full path in message
        super().__init__("Syslog file not found")


class SyslogPermissionError(SyslogError):
    """Raised when the syslog file cannot be read due to permissions."""

    def __init__(self, path: Path) -> None:
        self.path = path
        # Security: Don't expose full path in message
        super().__init__("Permission denied reading syslog file")


class SyslogLogSource:
    """Log source adapter for reading syslog-format files.

    Supports RFC 3164 (BSD syslog) format commonly used on Linux systems.
    Default location is /var/log/syslog on Debian/Ubuntu systems.
    """

    # Allowed base directories for syslog files (security: prevent path traversal)
    ALLOWED_DIRECTORIES = [
        Path("/var/log"),
        Path("/tmp"),  # For testing
    ]

    def __init__(
        self,
        file_path: Path | str | None = None,
        year: int | None = None,
        allowed_directories: list[Path] | None = None,
        name: str | None = None,
    ) -> None:
        """Initialize the syslog source.

        Args:
            file_path: Path to the syslog file. Defaults to /var/log/syslog.
            year: Year to use for timestamps (syslog doesn't include year).
                  Defaults to current year.
            allowed_directories: Override allowed directories (for testing).
            name: Custom display name. If not provided, generates from file path.
        """
        if file_path is None:
            self._path = Path("/var/log/syslog")
        else:
            self._path = Path(file_path)

        self._year = year
        self._validated = False
        self._custom_name = name
        self._resolved_path: Path | None = None  # Set after validation to prevent TOCTOU
        self._allowed_directories = (
            allowed_directories if allowed_directories is not None else self.ALLOWED_DIRECTORIES
        )

    @property
    def name(self) -> str:
        """Human-readable name for this source."""
        if self._custom_name:
            return self._custom_name
        return f"Syslog ({self._path.name})"

    def _validate_path(self) -> None:
        """Validate that the file path is safe and accessible.

        Raises:
            SyslogFileNotFoundError: If file doesn't exist.
            SyslogPermissionError: If file cannot be read.
            SyslogError: If path is outside allowed directories.
        """
        # Resolve any symlinks and relative paths
        try:
            resolved = self._path.resolve()
        except (OSError, ValueError) as e:
            raise SyslogError(f"Invalid path: {e}") from e

        # Security: Check path is within allowed directories
        # Resolve allowed directories too to handle symlinks (e.g., /tmp -> /private/tmp on macOS)
        is_allowed = any(
            self._is_path_under(resolved, allowed_dir.resolve())
            for allowed_dir in self._allowed_directories
        )

        if not is_allowed:
            # Don't reveal the actual path in the error
            raise SyslogError("Path is not in an allowed directory")

        # Check file exists
        if not resolved.exists():
            raise SyslogFileNotFoundError(resolved)

        # Check file is readable
        if not os.access(resolved, os.R_OK):
            raise SyslogPermissionError(resolved)

        # Check it's actually a file
        if not resolved.is_file():
            raise SyslogError("Path is not a regular file")

        # Store resolved path to prevent TOCTOU attacks
        self._resolved_path = resolved
        self._validated = True

    @staticmethod
    def _is_path_under(path: Path, parent: Path) -> bool:
        """Check if a path is under a parent directory.

        Args:
            path: The path to check.
            parent: The parent directory.

        Returns:
            True if path is under parent, False otherwise.
        """
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False

    async def fetch(self, log_filter: Filter) -> AsyncIterator[LogEntry]:
        """Fetch logs from the syslog file matching the filter.

        Args:
            log_filter: The filter to apply when fetching logs.

        Yields:
            LogEntry objects matching the filter.

        Raises:
            SyslogError: If file cannot be read.
        """
        if not self._validated:
            self._validate_path()

        # Use resolved path to prevent TOCTOU attacks
        assert self._resolved_path is not None, "Path not validated"

        count = 0
        parse_errors = 0
        max_parse_errors = 100  # Don't spam errors for badly formatted files

        try:
            # Read file in blocking way, but yield to event loop periodically
            with open(self._resolved_path, encoding="utf-8", errors="replace") as f:
                for line_num, line in enumerate(f, start=1):
                    # Yield to event loop every 100 lines
                    if line_num % 100 == 0:
                        await asyncio.sleep(0)

                    if not line.strip():
                        continue

                    try:
                        parsed = parse_syslog_line(line, year=self._year)
                    except SyslogParseError:
                        parse_errors += 1
                        if parse_errors <= max_parse_errors:
                            # Skip malformed lines silently
                            pass
                        continue

                    entry = self._parsed_to_entry(parsed)

                    if entry.matches_filter(log_filter):
                        yield entry
                        count += 1
                        if count >= log_filter.limit:
                            break

        except FileNotFoundError as e:
            raise SyslogFileNotFoundError(self._path) from e
        except PermissionError as e:
            raise SyslogPermissionError(self._path) from e
        except OSError as e:
            raise SyslogError(f"Error reading syslog: {e}") from e

    def _parsed_to_entry(self, parsed: ParsedSyslogLine) -> LogEntry:
        """Convert a parsed syslog line to a LogEntry.

        Args:
            parsed: The parsed syslog line.

        Returns:
            A LogEntry object.
        """
        return LogEntry(
            timestamp=parsed.timestamp,
            severity=Severity.from_string(parsed.severity),
            message=parsed.message,
            source=parsed.program,
            metadata={
                "hostname": parsed.hostname,
                "program": parsed.program,
                **({"pid": str(parsed.pid)} if parsed.pid else {}),
            },
            raw=parsed.raw,
        )

    def validate_filter(self, log_filter: Filter) -> list[str]:
        """Validate a filter for syslog source.

        Args:
            log_filter: The filter to validate.

        Returns:
            List of validation error messages.
        """
        errors: list[str] = []

        # Check for unsupported fields
        supported_fields = {"hostname", "program", "pid"}
        for field in log_filter.fields:
            if field not in supported_fields:
                errors.append(f"Unsupported filter field: {field}")

        return errors

    def available_filters(self) -> list[FilterField]:
        """Get available filter fields for syslog.

        Returns:
            List of FilterField objects describing available filters.
        """
        return [
            FilterField(
                name="severity",
                label="Minimum Severity",
                options=[s.value for s in Severity],
            ),
            FilterField(
                name="hostname",
                label="Hostname",
            ),
            FilterField(
                name="program",
                label="Program/Service",
            ),
        ]
