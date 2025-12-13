"""Main log list widget."""

from __future__ import annotations

from textual.widgets import DataTable

from logview.adapters.mock import MockLogSource
from logview.domain.models import Filter, Severity


class LogList(DataTable):
    """A scrollable list of log entries."""

    SEVERITY_STYLES = {
        Severity.DEBUG: "dim",
        Severity.INFO: "",
        Severity.WARN: "yellow",
        Severity.ERROR: "red",
        Severity.CRITICAL: "red bold",
    }

    def __init__(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        """Initialize the log list."""
        super().__init__(**kwargs)
        self.cursor_type = "row"
        self.zebra_stripes = True

    def on_mount(self) -> None:
        """Set up the table when mounted."""
        self.add_columns("Timestamp", "Severity", "Source", "Message")
        self.call_later(self._load_initial_logs)

    async def _load_initial_logs(self) -> None:
        """Load initial logs from the mock source."""
        source = MockLogSource(seed=42)
        log_filter = Filter(limit=100)

        async for entry in source.fetch(log_filter):
            timestamp_str = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            severity_str = entry.severity.value

            self.add_row(
                timestamp_str,
                severity_str,
                entry.source,
                entry.message[:60] + "..." if len(entry.message) > 60 else entry.message,
            )
