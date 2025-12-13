"""Base protocol for log source adapters."""

from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterator, Protocol, runtime_checkable

if TYPE_CHECKING:
    from logview.domain.models import Filter, FilterField, LogEntry


@runtime_checkable
class LogSource(Protocol):
    """Protocol that all log providers must implement."""

    @property
    def name(self) -> str:
        """Human-readable name for this source."""
        ...

    async def fetch(self, log_filter: Filter) -> AsyncIterator[LogEntry]:
        """Fetch logs matching the filter.

        Args:
            log_filter: The filter to apply when fetching logs.

        Yields:
            LogEntry objects matching the filter.
        """
        ...

    def validate_filter(self, log_filter: Filter) -> list[str]:
        """Validate a filter for this source.

        Args:
            log_filter: The filter to validate.

        Returns:
            A list of validation error messages. Empty if valid.
        """
        ...

    def available_filters(self) -> list[FilterField]:
        """Get the list of filter fields this source supports.

        Returns:
            A list of FilterField objects describing available filters.
        """
        ...
