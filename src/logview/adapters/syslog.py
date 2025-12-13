"""Syslog adapter (placeholder for Phase 2)."""

from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterator

if TYPE_CHECKING:
    from logview.domain.models import Filter, FilterField, LogEntry


class SyslogSource:
    """Local syslog source.

    This is a placeholder implementation for Phase 2.
    """

    def __init__(self, path: str = "/var/log/syslog") -> None:
        """Initialize the syslog source.

        Args:
            path: Path to the syslog file.
        """
        self._path = path

    @property
    def name(self) -> str:
        """Human-readable name for this source."""
        return f"Syslog ({self._path})"

    async def fetch(self, log_filter: Filter) -> AsyncIterator[LogEntry]:
        """Fetch logs from syslog.

        Args:
            log_filter: The filter to apply.

        Yields:
            LogEntry objects from syslog.
        """
        raise NotImplementedError("Syslog adapter not yet implemented (Phase 2)")
        # This yield is never reached but needed for type checking
        yield  # type: ignore[misc]

    def validate_filter(self, log_filter: Filter) -> list[str]:
        """Validate a filter for syslog.

        Args:
            log_filter: The filter to validate.

        Returns:
            List of validation errors.
        """
        return []

    def available_filters(self) -> list[FilterField]:
        """Get available filter fields for syslog.

        Returns:
            List of syslog-specific filter fields.
        """
        from logview.domain.models import FilterField, Severity

        return [
            FilterField(name="severity", label="Severity", options=[s.value for s in Severity]),
            FilterField(name="process", label="Process Name"),
        ]
