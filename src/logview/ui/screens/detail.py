"""Log detail modal for viewing full log entry information."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

if TYPE_CHECKING:
    from logview.domain.models import LogEntry


class DetailModal(ModalScreen[None]):
    """Modal for viewing full log entry details.

    Displays the complete log entry with all metadata in a scrollable view.
    Supports copying the JSON representation to clipboard.
    """

    DEFAULT_CSS = """
    DetailModal {
        align: center middle;
    }

    DetailModal > Vertical {
        width: 80%;
        max-width: 100;
        height: 80%;
        max-height: 40;
        background: $surface;
        border: thick $primary;
        padding: 1;
    }

    DetailModal .detail-title {
        text-style: bold;
        padding-bottom: 1;
        border-bottom: solid $primary;
        margin-bottom: 1;
    }

    DetailModal .detail-section {
        margin-bottom: 1;
    }

    DetailModal .detail-label {
        text-style: bold;
        color: $text-muted;
    }

    DetailModal .detail-value {
        margin-left: 2;
    }

    DetailModal .detail-message {
        margin-top: 1;
        padding: 1;
        background: $surface-darken-1;
        border: solid $primary-lighten-2;
    }

    DetailModal .detail-raw {
        margin-top: 1;
        padding: 1;
        background: $surface-darken-2;
        border: dashed $primary-lighten-2;
        text-style: italic;
    }

    DetailModal ScrollableContainer {
        height: 1fr;
        border: solid $primary-lighten-2;
        padding: 0 1;
    }

    DetailModal .button-bar {
        dock: bottom;
        height: 3;
        align: center middle;
        padding-top: 1;
        border-top: solid $primary;
    }

    DetailModal Button {
        margin: 0 1;
    }
    """

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

    def compose(self) -> ComposeResult:
        """Compose the modal content."""
        with Vertical():
            yield Label("Log Entry Detail", classes="detail-title")

            with ScrollableContainer():
                # Timestamp section
                yield Label("Timestamp:", classes="detail-label")
                yield Static(
                    self._entry.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    classes="detail-value",
                )

                # Severity section
                yield Label("Severity:", classes="detail-label")
                severity_class = f"severity-{self._entry.severity.value.lower()}"
                yield Static(
                    self._entry.severity.value,
                    classes=f"detail-value {severity_class}",
                )

                # Source section
                yield Label("Source:", classes="detail-label")
                yield Static(self._entry.source, classes="detail-value")

                # Message section
                yield Label("Message:", classes="detail-label")
                yield Static(self._entry.message, classes="detail-message")

                # Metadata section (if any)
                if self._entry.metadata:
                    yield Label("Metadata:", classes="detail-label detail-section")
                    metadata_text = self._format_metadata(self._entry.metadata)
                    yield Static(metadata_text, classes="detail-value")

                # Raw log (if present)
                if self._entry.raw:
                    yield Label("Raw Log:", classes="detail-label detail-section")
                    yield Static(self._entry.raw, classes="detail-raw")

            # Button bar
            with Vertical(classes="button-bar"):
                yield Button("Copy JSON [c]", id="btn-copy", variant="primary")
                yield Button("Close [Esc]", id="btn-close")

    def _format_metadata(self, metadata: dict[str, str]) -> str:
        """Format metadata dictionary for display.

        Args:
            metadata: The metadata dictionary.

        Returns:
            Formatted string representation.
        """
        lines = []
        for key, value in sorted(metadata.items()):
            lines.append(f"  {key}: {value}")
        return "\n".join(lines)

    def action_close(self) -> None:
        """Close the modal."""
        self.dismiss(None)

    def action_copy(self) -> None:
        """Copy the log entry JSON to clipboard."""
        json_str = self._entry.to_json()
        try:
            import pyperclip  # type: ignore[import-untyped]

            pyperclip.copy(json_str)
            self.notify("Copied to clipboard")
        except ImportError:
            # pyperclip not installed, try to copy via xclip/xsel
            self._copy_fallback(json_str)
        except Exception as e:
            self.notify(f"Failed to copy: {e}", severity="error")

    def _copy_fallback(self, text: str) -> None:
        """Fallback clipboard copy using shell commands.

        Args:
            text: The text to copy to clipboard.
        """
        import subprocess

        # Try xclip first, then xsel
        for cmd in [["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]:
            try:
                process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                process.communicate(input=text.encode("utf-8"), timeout=5)
                if process.returncode == 0:
                    self.notify("Copied to clipboard")
                    return
            except (subprocess.SubprocessError, FileNotFoundError):
                continue

        self.notify("Clipboard not available (install xclip or xsel)", severity="warning")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-close":
            self.action_close()
        elif event.button.id == "btn-copy":
            self.action_copy()
