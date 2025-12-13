"""Syslog line parser for RFC 3164 (BSD syslog) format."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# RFC 3164 BSD syslog format:
# <Mon DD HH:MM:SS> <hostname> <program>[<pid>]: <message>
# Example: Jan 15 10:23:45 myhost sshd[1234]: Accepted publickey for user
RFC3164_PATTERN = re.compile(
    r"^(?P<month>[A-Z][a-z]{2})\s+"
    r"(?P<day>\d{1,2})\s+"
    r"(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<hostname>\S+)\s+"
    r"(?P<program>[^\[:]+)"
    r"(?:\[(?P<pid>\d+)\])?:\s*"
    r"(?P<message>.*)$",
    re.IGNORECASE,
)

# Map month abbreviations to numbers
MONTH_MAP = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

# Patterns for detecting severity in message content
SEVERITY_PATTERNS = [
    (re.compile(r"\bCRITICAL\b", re.IGNORECASE), "CRITICAL"),
    (re.compile(r"\bFATAL\b", re.IGNORECASE), "CRITICAL"),
    (re.compile(r"\bERROR\b", re.IGNORECASE), "ERROR"),
    (re.compile(r"\bERR\b", re.IGNORECASE), "ERROR"),
    (re.compile(r"\bWARNING\b", re.IGNORECASE), "WARN"),
    (re.compile(r"\bWARN\b", re.IGNORECASE), "WARN"),
    (re.compile(r"\bINFO\b", re.IGNORECASE), "INFO"),
    (re.compile(r"\bDEBUG\b", re.IGNORECASE), "DEBUG"),
]


@dataclass
class ParsedSyslogLine:
    """Result of parsing a syslog line."""

    timestamp: datetime
    hostname: str
    program: str
    pid: int | None
    message: str
    severity: str
    raw: str


class SyslogParseError(Exception):
    """Raised when a syslog line cannot be parsed."""

    def __init__(self, line: str, reason: str) -> None:
        self.line = line
        self.reason = reason
        super().__init__(f"Failed to parse syslog line: {reason}")


def _detect_severity(message: str) -> str:
    """Detect severity level from message content.

    Syslog messages often contain severity keywords like ERROR, WARNING, etc.
    This function scans the message for these keywords.

    Args:
        message: The log message to scan.

    Returns:
        The detected severity level, defaults to "INFO" if none found.
    """
    for pattern, severity in SEVERITY_PATTERNS:
        if pattern.search(message):
            return severity
    return "INFO"


def _sanitize_message(message: str) -> str:
    """Sanitize message by removing potentially dangerous terminal escape sequences.

    Security: Prevent terminal escape sequence injection attacks.

    Args:
        message: The raw message to sanitize.

    Returns:
        Sanitized message with escape sequences removed.
    """
    # Remove ANSI escape sequences
    ansi_escape = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
    message = ansi_escape.sub("", message)

    # Remove other control characters except newline and tab
    message = "".join(char for char in message if char == "\n" or char == "\t" or (ord(char) >= 32))

    return message


def parse_syslog_line(line: str, year: int | None = None) -> ParsedSyslogLine:
    """Parse a single syslog line in RFC 3164 format.

    Args:
        line: The syslog line to parse.
        year: The year to use for the timestamp (syslog doesn't include year).
              Defaults to current year.

    Returns:
        ParsedSyslogLine containing the parsed fields.

    Raises:
        SyslogParseError: If the line cannot be parsed.
    """
    if not line or not line.strip():
        raise SyslogParseError(line, "empty line")

    line = line.strip()
    match = RFC3164_PATTERN.match(line)

    if not match:
        raise SyslogParseError(line, "does not match RFC 3164 format")

    groups = match.groupdict()

    # Parse timestamp
    month_str = groups["month"].lower()
    if month_str not in MONTH_MAP:
        raise SyslogParseError(line, f"invalid month: {groups['month']}")

    month = MONTH_MAP[month_str]
    day = int(groups["day"])

    # Parse time
    time_parts = groups["time"].split(":")
    if len(time_parts) != 3:
        raise SyslogParseError(line, f"invalid time format: {groups['time']}")

    try:
        hour = int(time_parts[0])
        minute = int(time_parts[1])
        second = int(time_parts[2])
    except ValueError as e:
        raise SyslogParseError(line, f"invalid time components: {e}") from e

    # Use provided year or current year
    if year is None:
        year = datetime.now().year

    try:
        timestamp = datetime(year, month, day, hour, minute, second)
    except ValueError as e:
        raise SyslogParseError(line, f"invalid date/time: {e}") from e

    # Parse PID (may be None)
    pid = int(groups["pid"]) if groups["pid"] else None

    # Sanitize message and detect severity
    message = _sanitize_message(groups["message"])
    severity = _detect_severity(message)

    return ParsedSyslogLine(
        timestamp=timestamp,
        hostname=groups["hostname"],
        program=groups["program"].strip(),
        pid=pid,
        message=message,
        severity=severity,
        raw=line,
    )
