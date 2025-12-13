"""Help modal (placeholder for Phase 2)."""

from __future__ import annotations

from textual.screen import ModalScreen
from textual.widgets import Static

HELP_TEXT = """
LogView - Keyboard Shortcuts

Navigation:
  ↑/↓       Move selection up/down
  Page Up   Scroll up one page
  Page Down Scroll down one page
  Home      Go to first entry
  End       Go to last entry

Actions:
  Enter     View log entry details
  c         Change log source context
  f         Open filter editor
  /         Search within results
  ?         Show this help

General:
  q         Quit application
  Esc       Close modal/cancel
"""


class HelpModal(ModalScreen[None]):
    """Modal displaying keyboard shortcuts and help."""

    BINDINGS = [
        ("escape", "close", "Close"),
        ("question_mark", "close", "Close"),
    ]

    def compose(self):  # type: ignore[no-untyped-def]
        """Compose the modal content."""
        yield Static(HELP_TEXT)

    def action_close(self) -> None:
        """Close the help modal."""
        self.dismiss(None)
