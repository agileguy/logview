"""JSON Lines log parser."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


class JsonlParseError(Exception):
    """Raised when a JSON Lines entry cannot be parsed."""

    def __init__(self, line: str, reason: str) -> None:
        self.line = line
        self.reason = reason
        super().__init__(f"Failed to parse JSON line: {reason}")


@dataclass(frozen=True)
class ParsedJsonlLine:
    """A parsed JSON Lines log entry."""

    timestamp: datetime
    message: str
    severity: str
    metadata: dict[str, Any]
    raw: str


# Common timestamp field names in JSON logs
TIMESTAMP_FIELDS = ("timestamp", "time", "ts", "@timestamp", "date", "datetime")

# Common severity/level field names
SEVERITY_FIELDS = ("level", "severity", "log_level", "loglevel", "lvl")

# Common message field names
MESSAGE_FIELDS = ("message", "msg", "text", "log", "body")

# Severity normalization mapping
SEVERITY_MAP = {
    "trace": "DEBUG",
    "debug": "DEBUG",
    "info": "INFO",
    "information": "INFO",
    "warn": "WARN",
    "warning": "WARN",
    "error": "ERROR",
    "err": "ERROR",
    "critical": "CRITICAL",
    "crit": "CRITICAL",
    "fatal": "CRITICAL",
    "panic": "CRITICAL",
}


def _find_field(data: dict[str, Any], field_names: tuple[str, ...]) -> Any | None:
    """Find a field in the data by checking multiple possible names."""
    for name in field_names:
        if name in data:
            return data[name]
        # Also check case-insensitive
        for key in data:
            if key.lower() == name.lower():
                return data[key]
    return None


def _parse_timestamp(value: Any) -> datetime:
    """Parse a timestamp from various formats."""
    if isinstance(value, datetime):
        return value

    if isinstance(value, (int, float)):
        # Unix timestamp - interpret as UTC, then convert to local time
        # Handle different precisions: seconds, milliseconds, microseconds, nanoseconds
        if value > 1e18:  # Nanoseconds
            value = value / 1e9
        elif value > 1e15:  # Microseconds
            value = value / 1e6
        elif value > 1e12:  # Milliseconds
            value = value / 1e3
        # Interpret as UTC and convert to local time (naive datetime)
        utc_dt = datetime.fromtimestamp(value, tz=UTC)
        return utc_dt.astimezone().replace(tzinfo=None)

    if isinstance(value, str):
        # Try ISO format first
        try:
            # Handle Z suffix
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            dt = datetime.fromisoformat(value)
            # Convert to local time if timezone-aware
            if dt.tzinfo is not None:
                dt = dt.astimezone().replace(tzinfo=None)
            return dt
        except ValueError:
            pass

        # Try common formats
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y/%m/%d %H:%M:%S",
            "%d/%b/%Y:%H:%M:%S",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue

    raise ValueError(f"Cannot parse timestamp: {value}")


def _normalize_severity(value: Any) -> str:
    """Normalize severity level to standard values."""
    if value is None:
        return "INFO"

    str_value = str(value).lower().strip()
    return SEVERITY_MAP.get(str_value, "INFO")


def parse_jsonl_line(line: str) -> ParsedJsonlLine:
    """Parse a single JSON Lines log entry.

    Args:
        line: A single line containing a JSON object.

    Returns:
        ParsedJsonlLine with extracted fields.

    Raises:
        JsonlParseError: If the line cannot be parsed.
    """
    line = line.strip()
    if not line:
        raise JsonlParseError(line, "empty line")

    try:
        data = json.loads(line)
    except json.JSONDecodeError as e:
        raise JsonlParseError(line, f"invalid JSON: {e}") from e

    if not isinstance(data, dict):
        raise JsonlParseError(line, "JSON must be an object")

    # Extract timestamp
    ts_value = _find_field(data, TIMESTAMP_FIELDS)
    if ts_value is not None:
        try:
            timestamp = _parse_timestamp(ts_value)
        except ValueError:
            timestamp = datetime.now()
    else:
        timestamp = datetime.now()

    # Extract severity
    sev_value = _find_field(data, SEVERITY_FIELDS)
    severity = _normalize_severity(sev_value)

    # Extract message
    msg_value = _find_field(data, MESSAGE_FIELDS)
    if msg_value is not None:
        message = str(msg_value)
    else:
        # Use the entire JSON as message if no message field
        message = line

    # Build metadata from remaining fields
    metadata: dict[str, Any] = {}
    used_fields = set()
    for field_tuple in (TIMESTAMP_FIELDS, SEVERITY_FIELDS, MESSAGE_FIELDS):
        for field in field_tuple:
            used_fields.add(field.lower())

    for key, value in data.items():
        if key.lower() not in used_fields:
            metadata[key] = value

    return ParsedJsonlLine(
        timestamp=timestamp,
        message=message,
        severity=severity,
        metadata=metadata,
        raw=line,
    )


def is_jsonl_format(line: str) -> bool:
    """Check if a line appears to be valid JSON Lines format.

    Args:
        line: A line to check.

    Returns:
        True if the line is valid JSON that is an object.
    """
    line = line.strip()
    if not line:
        return False

    try:
        data = json.loads(line)
        return isinstance(data, dict)
    except json.JSONDecodeError:
        return False
