"""Log detail modal (placeholder for Phase 2)."""

from __future__ import annotations

from textual.screen import ModalScreen
from textual.widgets import Static

from logview.domain.models import LogEntry


class DetailModal(ModalScreen[None]):
    """Modal for viewing log entry details."""

    BINDINGS = [
        ("escape", "close", "Close"),
        ("c", "copy", "Copy JSON"),
    ]

    def __init__(self, entry: LogEntry) -> None:
        """Initialize the detail modal.

        Args:
            entry: The log entry to display.
        """
        super().__init__()
        self._entry = entry

    def compose(self):  # type: ignore[no-untyped-def]
        """Compose the modal content."""
        yield Static("Detail view - not yet implemented (Phase 2)")

    def action_close(self) -> None:
        """Close the modal."""
        self.dismiss(None)

    def action_copy(self) -> None:
        """Copy the log entry JSON to clipboard."""
        # TODO: Implement clipboard copy
        pass
