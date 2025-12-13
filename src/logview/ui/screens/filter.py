"""Filter editor modal (placeholder for Phase 2)."""

from __future__ import annotations

from textual.screen import ModalScreen
from textual.widgets import Static

from logview.domain.models import Filter


class FilterModal(ModalScreen[Filter | None]):
    """Modal for editing log filters."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "apply", "Apply"),
    ]

    def compose(self):  # type: ignore[no-untyped-def]
        """Compose the modal content."""
        yield Static("Filter editor - not yet implemented (Phase 2)")

    def action_cancel(self) -> None:
        """Cancel and close the modal."""
        self.dismiss(None)

    def action_apply(self) -> None:
        """Apply the filter and close."""
        self.dismiss(None)
