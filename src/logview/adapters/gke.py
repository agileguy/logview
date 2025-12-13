"""GKE Kubernetes log adapter (placeholder for Phase 4)."""

from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterator

if TYPE_CHECKING:
    from logview.domain.models import Filter, FilterField, LogEntry


class GKELogSource:
    """GKE Kubernetes log source.

    This is a placeholder implementation for Phase 4.
    """

    def __init__(self, project_id: str, cluster: str, namespace: str | None = None) -> None:
        """Initialize the GKE log source.

        Args:
            project_id: The GCP project ID.
            cluster: The GKE cluster name.
            namespace: Optional default namespace.
        """
        self._project_id = project_id
        self._cluster = cluster
        self._namespace = namespace

    @property
    def name(self) -> str:
        """Human-readable name for this source."""
        if self._namespace:
            return f"GKE: {self._cluster}/{self._namespace}"
        return f"GKE: {self._cluster}"

    async def fetch(self, log_filter: Filter) -> AsyncIterator[LogEntry]:
        """Fetch logs from GKE.

        Args:
            log_filter: The filter to apply.

        Yields:
            LogEntry objects from GKE.
        """
        raise NotImplementedError("GKE adapter not yet implemented (Phase 4)")
        # This yield is never reached but needed for type checking
        yield  # type: ignore[misc]

    def validate_filter(self, log_filter: Filter) -> list[str]:
        """Validate a filter for GKE.

        Args:
            log_filter: The filter to validate.

        Returns:
            List of validation errors.
        """
        return []

    def available_filters(self) -> list[FilterField]:
        """Get available filter fields for GKE.

        Returns:
            List of GKE-specific filter fields.
        """
        from logview.domain.models import FilterField, Severity

        return [
            FilterField(name="cluster", label="Cluster", required=True),
            FilterField(name="namespace", label="Namespace"),
            FilterField(name="pod", label="Pod Name"),
            FilterField(name="container", label="Container"),
            FilterField(name="labels", label="Labels (key=value)"),
            FilterField(name="severity", label="Severity", options=[s.value for s in Severity]),
        ]
