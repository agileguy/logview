"""Plain text log parser."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ParsedPlainLine:
    """A parsed plain text log entry."""

    timestamp: datetime
    message: str
    severity: str
    raw: str


# Patterns to detect severity in plain text logs
SEVERITY_PATTERNS = {
    "CRITICAL": re.compile(r"\b(CRITICAL|CRIT|FATAL|PANIC)\b", re.IGNORECASE),
    "ERROR": re.compile(r"\b(ERROR|ERR|FAILURE|FAILED)\b", re.IGNORECASE),
    "WARN": re.compile(r"\b(WARN|WARNING)\b", re.IGNORECASE),
    "DEBUG": re.compile(r"\b(DEBUG|TRACE)\b", re.IGNORECASE),
}


def _detect_severity(message: str) -> str:
    """Detect severity level from message content."""
    for severity, pattern in SEVERITY_PATTERNS.items():
        if pattern.search(message):
            return severity
    return "INFO"


def _sanitize_message(message: str) -> str:
    """Remove ANSI escape codes and control characters from message."""
    # Remove ANSI escape sequences
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    message = ansi_escape.sub("", message)

    # Remove other control characters except tab and newline
    message = "".join(
        char if char in ("\t", "\n") or (ord(char) >= 32) else "" for char in message
    )

    return message


def parse_plain_line(
    line: str,
    default_timestamp: datetime | None = None,
) -> ParsedPlainLine:
    """Parse a single plain text log line.

    For plain text logs, each line is treated as a single log entry.
    The timestamp defaults to the provided timestamp or current time.
    Severity is detected from keywords in the message.

    Args:
        line: A single line of log text.
        default_timestamp: Timestamp to use (e.g., file modification time).

    Returns:
        ParsedPlainLine with the message and detected severity.
    """
    line = line.rstrip("\n\r")
    message = _sanitize_message(line)
    severity = _detect_severity(message)

    return ParsedPlainLine(
        timestamp=default_timestamp or datetime.now(),
        message=message,
        severity=severity,
        raw=line,
    )
