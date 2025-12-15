"""Core domain models for LogView."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class Severity(Enum):
    """Log severity levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    @classmethod
    def from_string(cls, value: str) -> Severity:
        """Parse a severity from a string, case-insensitive."""
        normalized = value.upper().strip()
        # Handle common aliases
        aliases = {
            "WARNING": "WARN",
            "FATAL": "CRITICAL",
            "CRIT": "CRITICAL",
            "ERR": "ERROR",
            "DBG": "DEBUG",
            "INF": "INFO",
        }
        normalized = aliases.get(normalized, normalized)
        return cls(normalized)

    def __ge__(self, other: Severity) -> bool:
        """Compare severity levels."""
        order = [Severity.DEBUG, Severity.INFO, Severity.WARN, Severity.ERROR, Severity.CRITICAL]
        return order.index(self) >= order.index(other)

    def __gt__(self, other: Severity) -> bool:
        """Compare severity levels."""
        order = [Severity.DEBUG, Severity.INFO, Severity.WARN, Severity.ERROR, Severity.CRITICAL]
        return order.index(self) > order.index(other)

    def __le__(self, other: Severity) -> bool:
        """Compare severity levels."""
        return not self.__gt__(other)

    def __lt__(self, other: Severity) -> bool:
        """Compare severity levels."""
        return not self.__ge__(other)


@dataclass(frozen=True)
class TimeRange:
    """A time range for filtering logs."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        """Validate the time range."""
        if self.start > self.end:
            raise ValueError("start must be before or equal to end")

    def contains(self, dt: datetime) -> bool:
        """Check if a datetime falls within this range."""
        return self.start <= dt <= self.end


@dataclass(frozen=True)
class Filter:
    """A filter for querying logs."""

    time_range: TimeRange | None = None
    fields: dict[str, str] = field(default_factory=dict)
    text_search: str | None = None
    source_filter: str | None = None
    severity: Severity | None = None
    limit: int = 1000

    def __post_init__(self) -> None:
        """Validate the filter."""
        if self.limit < 1:
            raise ValueError("limit must be at least 1")
        if self.limit > 10000:
            raise ValueError("limit must not exceed 10000")


@dataclass
class LogEntry:
    """A single log entry."""

    timestamp: datetime
    severity: Severity
    message: str
    source: str
    metadata: dict[str, str] = field(default_factory=dict)
    raw: str = ""

    def to_json(self) -> str:
        """Serialize the log entry to JSON."""
        return json.dumps(
            {
                "timestamp": self.timestamp.isoformat(),
                "severity": self.severity.value,
                "message": self.message,
                "source": self.source,
                "metadata": self.metadata,
            },
            indent=2,
        )

    def matches_filter(self, log_filter: Filter) -> bool:
        """Check if this entry matches a filter."""
        # Check time range
        if log_filter.time_range and not log_filter.time_range.contains(self.timestamp):
            return False

        # Check severity (minimum level)
        if log_filter.severity and self.severity < log_filter.severity:
            return False

        # Check text search (case-insensitive substring match)
        if log_filter.text_search:
            search_lower = log_filter.text_search.lower()
            if search_lower not in self.message.lower():
                return False

        # Check source filter (case-insensitive substring match)
        if log_filter.source_filter:
            filter_lower = log_filter.source_filter.lower()
            if filter_lower not in self.source.lower():
                return False

        # Check field filters
        for key, value in log_filter.fields.items():
            if key not in self.metadata or self.metadata[key] != value:
                return False

        return True


@dataclass
class FilterField:
    """Describes a filterable field for a log source."""

    name: str
    label: str
    required: bool = False
    options: list[str] | None = None
