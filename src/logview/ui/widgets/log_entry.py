"""Single log entry widget (placeholder for detail view)."""

from __future__ import annotations

from textual.widgets import Static

from logview.domain.models import LogEntry


class LogEntryDetail(Static):
    """A detailed view of a single log entry."""

    def __init__(self, entry: LogEntry, **kwargs) -> None:  # type: ignore[no-untyped-def]
        """Initialize the log entry detail view.

        Args:
            entry: The log entry to display.
        """
        super().__init__(**kwargs)
        self._entry = entry

    def on_mount(self) -> None:
        """Render the entry when mounted."""
        self.update(self._entry.to_json())
