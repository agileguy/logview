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

    class SearchResultsChanged(Message):
        """Message sent when search results change."""

        def __init__(self, match_count: int, current_match: int) -> None:
            self.match_count = match_count
            self.current_match = current_match
            super().__init__()

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the log list."""
        super().__init__(**kwargs)
        self.cursor_type = "row"
        self.zebra_stripes = True
        self._entries: list[LogEntry] = []
        self._filtered_entries: list[LogEntry] = []  # Entries after search filter
        self._match_indices: list[int] = []  # Row indices that match search
        self._current_match_idx: int = -1  # Index in _match_indices
        self._search_text: str = ""
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
        # Use filtered entries when search is active
        entries = self._filtered_entries if self._search_text else self._entries
        if self.cursor_row is not None and self.cursor_row < len(entries):
            return entries[self.cursor_row]
        return None

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection event."""
        # Use filtered entries when search is active
        entries = self._filtered_entries if self._search_text else self._entries
        if event.cursor_row < len(entries):
            entry = entries[event.cursor_row]
            self.post_message(self.EntrySelected(entry))

    def get_entry_count(self) -> int:
        """Get the number of entries currently displayed.

        Returns:
            The count of visible entries.
        """
        if self._search_text:
            return len(self._filtered_entries)
        return len(self._entries)

    def search(self, text: str) -> None:
        """Search within loaded entries and update display.

        Args:
            text: The search text (case-insensitive).
        """
        self._search_text = text.strip().lower()

        if not self._search_text:
            self.clear_search()
            return

        # Filter entries that match
        self._filtered_entries = []
        self._match_indices = []

        for entry in self._entries:
            if self._search_text in entry.message.lower():
                self._match_indices.append(len(self._filtered_entries))
                self._filtered_entries.append(entry)

        # Rebuild table with filtered entries
        self.clear()
        for entry in self._filtered_entries:
            self._add_entry_row(entry)

        # Set current match
        self._current_match_idx = 0 if self._match_indices else -1
        if self._current_match_idx >= 0 and self._filtered_entries:
            self.move_cursor(row=0)

        # Notify about results
        self.post_message(
            self.SearchResultsChanged(
                len(self._filtered_entries),
                self._current_match_idx + 1 if self._current_match_idx >= 0 else 0,
            )
        )
        logger.debug(
            "Search '%s' found %d matches",
            self._search_text,
            len(self._filtered_entries),
        )

    def clear_search(self) -> None:
        """Clear search and restore all entries."""
        self._search_text = ""
        self._filtered_entries = []
        self._match_indices = []
        self._current_match_idx = -1

        # Rebuild table with all entries
        self.clear()
        for entry in self._entries:
            self._add_entry_row(entry)

        # Notify search cleared
        self.post_message(self.SearchResultsChanged(0, 0))
        logger.debug("Search cleared, showing all %d entries", len(self._entries))

    def next_match(self) -> bool:
        """Move cursor to next search match.

        Returns:
            True if moved to a match, False if no matches.
        """
        if not self._filtered_entries:
            return False

        # Move to next entry (wrap around)
        if self.cursor_row is not None:
            next_row = (self.cursor_row + 1) % len(self._filtered_entries)
            self.move_cursor(row=next_row)
            self._current_match_idx = next_row
        else:
            self.move_cursor(row=0)
            self._current_match_idx = 0

        self.post_message(
            self.SearchResultsChanged(
                len(self._filtered_entries),
                self._current_match_idx + 1,
            )
        )
        return True

    def prev_match(self) -> bool:
        """Move cursor to previous search match.

        Returns:
            True if moved to a match, False if no matches.
        """
        if not self._filtered_entries:
            return False

        # Move to previous entry (wrap around)
        if self.cursor_row is not None:
            prev_row = (self.cursor_row - 1) % len(self._filtered_entries)
            self.move_cursor(row=prev_row)
            self._current_match_idx = prev_row
        else:
            self.move_cursor(row=len(self._filtered_entries) - 1)
            self._current_match_idx = len(self._filtered_entries) - 1

        self.post_message(
            self.SearchResultsChanged(
                len(self._filtered_entries),
                self._current_match_idx + 1,
            )
        )
        return True

    def is_searching(self) -> bool:
        """Check if a search is currently active.

        Returns:
            True if search is active, False otherwise.
        """
        return bool(self._search_text)
