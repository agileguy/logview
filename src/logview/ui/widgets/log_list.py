"""Main log list widget."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from textual.message import Message
from textual.widgets import DataTable

from logview.domain.models import Filter, LogEntry, Severity

logger = logging.getLogger("logview.ui.log_list")

if TYPE_CHECKING:
    from logview.adapters.base import LogSource


class LogList(DataTable[Any]):
    """A scrollable list of log entries."""

    SEVERITY_STYLES = {
        Severity.DEBUG: "dim",
        Severity.INFO: "",
        Severity.WARN: "yellow",
        Severity.ERROR: "red",
        Severity.CRITICAL: "red bold",
    }

    class EntrySelected(Message):
        """Message sent when a log entry is selected."""

        def __init__(self, entry: LogEntry) -> None:
            self.entry = entry
            super().__init__()

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the log list."""
        super().__init__(**kwargs)
        self.cursor_type = "row"
        self.zebra_stripes = True
        self._entries: list[LogEntry] = []
        self._source: LogSource | None = None
        self._filter: Filter = Filter(limit=100)

    def on_mount(self) -> None:
        """Set up the table when mounted."""
        self.add_columns("Timestamp", "Severity", "Source", "Message")

    def set_source(self, source: LogSource) -> None:
        """Set the log source to fetch from.

        Args:
            source: The log source to use.
        """
        self._source = source

    def set_filter(self, log_filter: Filter) -> None:
        """Set the filter to apply when fetching logs.

        Args:
            log_filter: The filter to use.
        """
        self._filter = log_filter

    async def refresh_logs(self) -> None:
        """Refresh the log list from the current source."""
        if self._source is None:
            logger.debug("No source set, skipping refresh")
            return

        logger.info("Refreshing logs from source: %s", self._source.name)

        # Clear existing rows
        self.clear()
        self._entries = []

        try:
            async for entry in self._source.fetch(self._filter):  # type: ignore[attr-defined]
                self._entries.append(entry)
                self._add_entry_row(entry)
            logger.info("Loaded %d log entries", len(self._entries))
        except Exception as e:
            # Let the app handle the error notification
            logger.error("Error loading logs from %s: %s", self._source.name, e)
            self.app.notify(f"Error loading logs: {e}", severity="error")

    def _add_entry_row(self, entry: LogEntry) -> None:
        """Add a log entry as a row in the table.

        Args:
            entry: The log entry to add.
        """
        timestamp_str = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        severity_str = entry.severity.value
        message = entry.message[:60] + "..." if len(entry.message) > 60 else entry.message

        self.add_row(
            timestamp_str,
            severity_str,
            entry.source,
            message,
        )

    def get_selected_entry(self) -> LogEntry | None:
        """Get the currently selected log entry.

        Returns:
            The selected LogEntry or None if nothing is selected.
        """
        if self.cursor_row is not None and self.cursor_row < len(self._entries):
            return self._entries[self.cursor_row]
        return None

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection event."""
        if event.cursor_row < len(self._entries):
            entry = self._entries[event.cursor_row]
            self.post_message(self.EntrySelected(entry))
