"""Help modal displaying keyboard shortcuts and application info."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class HelpModal(ModalScreen[None]):
    """Modal displaying keyboard shortcuts and help information.

    Styled modal with sections for navigation, actions, and general shortcuts.
    Dismiss with Escape or the Close button.
    """

    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
    }

    HelpModal > Vertical {
        width: 70;
        max-width: 80%;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    HelpModal .help-title {
        text-style: bold;
        text-align: center;
        padding-bottom: 1;
        border-bottom: solid $primary;
        margin-bottom: 1;
        color: $text;
    }

    HelpModal .help-section {
        margin-bottom: 1;
    }

    HelpModal .help-section-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 0;
    }

    HelpModal .help-row {
        padding-left: 2;
    }

    HelpModal .help-key {
        text-style: bold;
        color: $secondary;
        width: 14;
    }

    HelpModal .help-desc {
        color: $text;
    }

    HelpModal .button-row {
        margin-top: 1;
        padding-top: 1;
        border-top: solid $primary;
        align: center middle;
        height: auto;
    }

    HelpModal Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
        ("question_mark", "close", "Close"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the modal content."""
        with Vertical():
            yield Static("LogView Help", classes="help-title")

            with VerticalScroll():
                # Navigation section
                yield Static("Navigation", classes="help-section-title")
                yield Static("[b]↑/↓[/b]         Move selection up/down", classes="help-row")
                yield Static("[b]Page Up[/b]     Scroll up one page", classes="help-row")
                yield Static("[b]Page Down[/b]   Scroll down one page", classes="help-row")
                yield Static("[b]Home[/b]        Go to first entry", classes="help-row")
                yield Static("[b]End[/b]         Go to last entry", classes="help-row")
                yield Static("", classes="help-section")

                # Actions section
                yield Static("Actions", classes="help-section-title")
                yield Static("[b]Enter[/b]       View log entry details", classes="help-row")
                yield Static("[b]c[/b]           Change log source context", classes="help-row")
                yield Static("[b]f[/b]           Open filter (source, time, severity, text)", classes="help-row")
                yield Static("[b]r[/b]           Refresh logs", classes="help-row")
                yield Static("[b]/[/b]           Search within results", classes="help-row")
                yield Static("[b]n[/b]           Next search match", classes="help-row")
                yield Static("[b]N[/b]           Previous search match", classes="help-row")
                yield Static("[b]e[/b]           Export visible logs", classes="help-row")
                yield Static("", classes="help-section")

                # General section
                yield Static("General", classes="help-section-title")
                yield Static("[b]?[/b]           Show this help", classes="help-row")
                yield Static("[b]s[/b]           Open settings", classes="help-row")
                yield Static("[b]Ctrl+Q[/b]      Toggle dark/light theme", classes="help-row")
                yield Static("[b]q[/b]           Quit application", classes="help-row")
                yield Static("[b]Esc[/b]         Close modal / cancel", classes="help-row")

            with Vertical(classes="button-row"):
                yield Button("Close", variant="primary", id="close-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "close-btn":
            self.dismiss(None)

    def action_close(self) -> None:
        """Close the help modal."""
        self.dismiss(None)
