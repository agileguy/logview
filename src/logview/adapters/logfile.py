"""Generic log file adapter with format auto-detection."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from logview.adapters.jsonl_parser import JsonlParseError, is_jsonl_format, parse_jsonl_line
from logview.adapters.plaintext_parser import parse_plain_line
from logview.domain.models import Filter, FilterField, LogEntry, Severity

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

# Try to import syslog parser (available after Phase 2)
SYSLOG_AVAILABLE = False
SyslogParseError: type[Exception] = Exception
_parse_syslog_line: Callable[[str], Any] | None = None

try:
    from logview.adapters import syslog_parser  # type: ignore[attr-defined]
    SYSLOG_AVAILABLE = True
    SyslogParseError = syslog_parser.SyslogParseError
    _parse_syslog_line = syslog_parser.parse_syslog_line
except (ImportError, AttributeError):
    pass

LogFormat = Literal["auto", "plain", "syslog", "jsonl"]


class LogFileError(Exception):
    """Base exception for log file adapter errors."""

    pass


class LogFileSecurityError(LogFileError):
    """Raised when a security violation is detected."""

    pass


class LogFileNotFoundError(LogFileError):
    """Raised when log file doesn't exist."""

    pass


def detect_format(file_path: Path, sample_lines: int = 10) -> LogFormat:
    """Detect the format of a log file by sampling its content.

    Args:
        file_path: Path to the log file.
        sample_lines: Number of lines to sample for detection.

    Returns:
        Detected format: 'jsonl', 'syslog', or 'plain'.
    """
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            lines = []
            for _ in range(sample_lines):
                line = f.readline()
                if not line:
                    break
                line = line.strip()
                if line:  # Skip empty lines
                    lines.append(line)
    except OSError:
        return "plain"

    if not lines:
        return "plain"

    # Try JSON Lines first (check if majority of lines are valid JSON objects)
    jsonl_count = sum(1 for line in lines if is_jsonl_format(line))
    if jsonl_count >= len(lines) * 0.8:  # 80% threshold
        return "jsonl"

    # Try syslog format (only if parser is available)
    if SYSLOG_AVAILABLE and _parse_syslog_line is not None:
        syslog_count = 0
        for line in lines:
            try:
                _parse_syslog_line(line)
                syslog_count += 1
            except SyslogParseError:
                pass

        if syslog_count >= len(lines) * 0.8:  # 80% threshold
            return "syslog"

    # Default to plain text
    return "plain"


class LogFileSource:
    """Log source for generic text log files.

    Supports multiple formats with auto-detection:
    - plain: Each line is a log entry
    - jsonl: JSON Lines format
    - syslog: RFC 3164/5424 syslog format
    """

    def __init__(
        self,
        name: str,
        path: str,
        format: LogFormat = "auto",
        allowed_directories: list[str] | None = None,
    ) -> None:
        """Initialize the log file source.

        Args:
            name: Display name for this log source.
            path: Path to the log file.
            format: Log format ('auto', 'plain', 'syslog', 'jsonl').
            allowed_directories: List of allowed directory prefixes for security.

        Raises:
            LogFileSecurityError: If path is outside allowed directories.
            LogFileNotFoundError: If the file doesn't exist.
        """
        self._name = name
        self._original_path = path
        self._format: LogFormat = format
        self._allowed_directories = allowed_directories or ["/var/log", "/opt", "/home"]

        # Resolve and validate path
        self._resolved_path = self._validate_path(path)

        # Auto-detect format if needed
        if self._format == "auto":
            self._format = detect_format(self._resolved_path)

    def _validate_path(self, path: str) -> Path:
        """Validate and resolve the file path.

        Args:
            path: The path to validate.

        Returns:
            Resolved Path object.

        Raises:
            LogFileSecurityError: If path is outside allowed directories.
            LogFileNotFoundError: If the file doesn't exist.
        """
        # Expand user home directory
        expanded = os.path.expanduser(path)
        resolved = Path(expanded).resolve()

        # Check if file exists
        if not resolved.exists():
            raise LogFileNotFoundError(f"Log file not found: {path}")

        if not resolved.is_file():
            raise LogFileNotFoundError(f"Path is not a file: {path}")

        # Security check: ensure path is within allowed directories
        allowed = False
        for allowed_dir in self._allowed_directories:
            allowed_path = Path(allowed_dir).resolve()
            try:
                resolved.relative_to(allowed_path)
                allowed = True
                break
            except ValueError:
                continue

        if not allowed:
            raise LogFileSecurityError(
                f"Access denied: {path} is outside allowed directories"
            )

        return resolved

    @property
    def name(self) -> str:
        """Human-readable name for this source."""
        return self._name

    @property
    def format(self) -> LogFormat:
        """The detected or configured format."""
        return self._format

    @property
    def path(self) -> Path:
        """The resolved file path."""
        return self._resolved_path

    async def fetch(self, filter: Filter) -> AsyncIterator[LogEntry]:
        """Fetch log entries from the file.

        Args:
            filter: Filter to apply to log entries.

        Yields:
            LogEntry objects matching the filter.
        """
        entries: list[LogEntry] = []

        # Get file modification time for plain text timestamps
        try:
            file_mtime = datetime.fromtimestamp(self._resolved_path.stat().st_mtime)
        except OSError:
            file_mtime = datetime.now()

        try:
            with open(self._resolved_path, encoding="utf-8", errors="replace") as f:
                for line_num, line in enumerate(f, 1):
                    if not line.strip():
                        continue

                    try:
                        entry = self._parse_line(line, file_mtime, line_num)
                        if entry and entry.matches_filter(filter):
                            entries.append(entry)

                            # Respect limit
                            if len(entries) >= filter.limit:
                                break
                    except (SyslogParseError, JsonlParseError):
                        # Skip unparseable lines
                        continue

        except OSError as e:
            raise LogFileError(f"Error reading log file: {e}") from e

        # Sort by timestamp descending (newest first)
        entries.sort(key=lambda e: e.timestamp, reverse=True)

        # Apply limit after sorting
        for entry in entries[: filter.limit]:
            yield entry

    def _parse_line(
        self,
        line: str,
        file_mtime: datetime,
        line_num: int,
    ) -> LogEntry | None:
        """Parse a line according to the detected format."""
        if self._format == "jsonl":
            jsonl_parsed = parse_jsonl_line(line)
            return LogEntry(
                timestamp=jsonl_parsed.timestamp,
                severity=Severity.from_string(jsonl_parsed.severity),
                message=jsonl_parsed.message,
                source=self._name,
                metadata={"line": str(line_num), **jsonl_parsed.metadata},
                raw=jsonl_parsed.raw,
            )

        elif self._format == "syslog":
            if not SYSLOG_AVAILABLE:
                # Fall back to plain text if syslog parser not available
                parsed_plain = parse_plain_line(line, file_mtime)
                return LogEntry(
                    timestamp=parsed_plain.timestamp,
                    severity=Severity.from_string(parsed_plain.severity),
                    message=parsed_plain.message,
                    source=self._name,
                    metadata={"line": str(line_num)},
                    raw=parsed_plain.raw,
                )

            assert _parse_syslog_line is not None  # Checked above with SYSLOG_AVAILABLE
            syslog_parsed = _parse_syslog_line(line)
            metadata: dict[str, str] = {"line": str(line_num)}
            if syslog_parsed.hostname:
                metadata["hostname"] = syslog_parsed.hostname
            if syslog_parsed.program:
                metadata["program"] = syslog_parsed.program
            if syslog_parsed.pid:
                metadata["pid"] = str(syslog_parsed.pid)

            return LogEntry(
                timestamp=syslog_parsed.timestamp,
                severity=Severity.from_string(syslog_parsed.severity),
                message=syslog_parsed.message,
                source=self._name,
                metadata=metadata,
                raw=syslog_parsed.raw,
            )

        else:  # plain
            plain_parsed = parse_plain_line(line, file_mtime)
            return LogEntry(
                timestamp=plain_parsed.timestamp,
                severity=Severity.from_string(plain_parsed.severity),
                message=plain_parsed.message,
                source=self._name,
                metadata={"line": str(line_num)},
                raw=plain_parsed.raw,
            )

    def validate_filter(self, filter: Filter) -> list[str]:
        """Return list of validation errors, empty if valid."""
        errors: list[str] = []

        if filter.limit < 1:
            errors.append("Limit must be at least 1")

        if filter.limit > 100000:
            errors.append("Limit cannot exceed 100000")

        # LogFile adapter only supports time_range, severity, text_search
        if filter.fields:
            unsupported = set(filter.fields.keys()) - {"line"}
            if unsupported:
                errors.append(f"Unsupported filter fields: {', '.join(unsupported)}")

        return errors

    def available_filters(self) -> list[FilterField]:
        """Return list of filter fields this source supports."""
        return [
            FilterField(name="time_range", label="Time Range"),
            FilterField(name="severity", label="Minimum Severity"),
            FilterField(name="text_search", label="Text Search"),
        ]
