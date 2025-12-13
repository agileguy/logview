"""GCP Cloud Logging adapter (placeholder for Phase 3)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from logview.domain.models import Filter, FilterField, LogEntry


class GCPLogSource:
    """GCP Cloud Logging source.

    This is a placeholder implementation for Phase 3.
    """

    def __init__(self, project_id: str) -> None:
        """Initialize the GCP log source.

        Args:
            project_id: The GCP project ID to fetch logs from.
        """
        self._project_id = project_id

    @property
    def name(self) -> str:
        """Human-readable name for this source."""
        return f"GCP: {self._project_id}"

    async def fetch(self, log_filter: Filter) -> AsyncIterator[LogEntry]:
        """Fetch logs from GCP Cloud Logging.

        Args:
            log_filter: The filter to apply.

        Yields:
            LogEntry objects from GCP.
        """
        raise NotImplementedError("GCP adapter not yet implemented (Phase 3)")
        yield  # Makes this an async generator

    def validate_filter(self, log_filter: Filter) -> list[str]:
        """Validate a filter for GCP.

        Args:
            log_filter: The filter to validate.

        Returns:
            List of validation errors.
        """
        return []

    def available_filters(self) -> list[FilterField]:
        """Get available filter fields for GCP.

        Returns:
            List of GCP-specific filter fields.
        """
        from logview.domain.models import FilterField, Severity

        return [
            FilterField(name="project", label="Project ID", required=True),
            FilterField(name="log_name", label="Log Name"),
            FilterField(name="resource_type", label="Resource Type"),
            FilterField(name="severity", label="Severity", options=[s.value for s in Severity]),
        ]
