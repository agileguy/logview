"""Context selector modal (placeholder for Phase 2)."""

from __future__ import annotations

from textual.screen import ModalScreen
from textual.widgets import Static


class ContextModal(ModalScreen[str | None]):
    """Modal for selecting a log source context."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "select", "Select"),
    ]

    def compose(self):  # type: ignore[no-untyped-def]
        """Compose the modal content."""
        yield Static("Context selector - not yet implemented (Phase 2)")

    def action_cancel(self) -> None:
        """Cancel and close the modal."""
        self.dismiss(None)

    def action_select(self) -> None:
        """Select the current context and close."""
        self.dismiss(None)
