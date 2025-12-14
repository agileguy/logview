"""Settings modal for configuring application preferences."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Select

if TYPE_CHECKING:
    from logview.config.schema import UISettings


class SettingsModal(ModalScreen[bool]):
    """Modal for editing application settings.

    Allows configuring theme, timestamp format, and display options.
    Returns True if settings were changed, False if cancelled.
    """

    DEFAULT_CSS = """
    SettingsModal {
        align: center middle;
    }

    SettingsModal > Vertical {
        width: 70;
        height: auto;
        max-height: 25;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    SettingsModal .settings-title {
        text-style: bold;
        text-align: center;
        padding-bottom: 1;
        border-bottom: solid $primary;
        margin-bottom: 1;
        color: $text;
    }

    SettingsModal .settings-label {
        text-style: bold;
        color: $text-muted;
        margin-bottom: 0;
    }

    SettingsModal .settings-row {
        height: 3;
        margin-bottom: 1;
    }

    SettingsModal Select {
        width: 100%;
    }

    SettingsModal Input {
        width: 100%;
    }

    SettingsModal .button-row {
        margin-top: 1;
        padding-top: 1;
        border-top: solid $primary;
        align: center middle;
        height: auto;
    }

    SettingsModal Button {
        margin: 0 1;
    }

    SettingsModal Checkbox {
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    # Theme options (Textual built-in themes available in Textual 6.8.0)
    # Note: Base themes (dark/light/ansi) use "textual-" prefix,
    #       custom themes (catppuccin-mocha, etc.) use names as-is
    THEME_OPTIONS = [
        ("Dark (default)", "dark"),
        ("Light", "light"),
        ("ANSI", "ansi"),
        ("Catppuccin Latte", "catppuccin-latte"),
        ("Catppuccin Mocha", "catppuccin-mocha"),
        ("Dracula", "dracula"),
        ("Flexoki", "flexoki"),
        ("Gruvbox", "gruvbox"),
        ("Monokai", "monokai"),
        ("Nord", "nord"),
        ("Solarized Light", "solarized-light"),
        ("Tokyo Night", "tokyo-night"),
    ]

    # Common timestamp formats
    TIMESTAMP_OPTIONS = [
        ("YYYY-MM-DD HH:MM:SS", "%Y-%m-%d %H:%M:%S"),
        ("ISO 8601", "%Y-%m-%dT%H:%M:%S"),
        ("12-hour", "%Y-%m-%d %I:%M:%S %p"),
        ("Date only", "%Y-%m-%d"),
        ("Time only", "%H:%M:%S"),
    ]

    def __init__(
        self,
        current_settings: UISettings,
        on_save: Callable[[UISettings], None],
    ) -> None:
        """Initialize the settings modal.

        Args:
            current_settings: Current UI settings.
            on_save: Callback when settings are saved.
        """
        super().__init__()
        self._settings = current_settings
        self._on_save = on_save

    def compose(self) -> ComposeResult:
        """Compose the modal content."""
        with Vertical():
            yield Label("Settings", classes="settings-title")

            # Theme section
            yield Label("Theme:", classes="settings-label")
            theme_value = self._settings.theme
            yield Select(
                self.THEME_OPTIONS,
                id="theme-select",
                value=theme_value,
            )

            # Timestamp format section
            yield Label("Timestamp Format:", classes="settings-label")
            current_format = self._settings.timestamp_format
            # Find matching option or use first
            format_value = current_format
            yield Select(
                self.TIMESTAMP_OPTIONS,
                id="format-select",
                value=format_value,
                allow_blank=False,
            )

            # Max message width
            yield Label("Max Message Width:", classes="settings-label")
            yield Input(
                value=str(self._settings.max_message_width),
                id="width-input",
                type="integer",
            )

            # Show metadata checkbox
            yield Checkbox(
                "Show metadata in log list",
                id="metadata-checkbox",
                value=self._settings.show_metadata,
            )

            # Button bar
            with Horizontal(classes="button-row"):
                yield Button("Save", variant="primary", id="btn-save")
                yield Button("Cancel", id="btn-cancel")

    def action_cancel(self) -> None:
        """Cancel and close the modal."""
        self.dismiss(False)

    def _save_settings(self) -> None:
        """Save settings and close."""
        from logview.config.schema import UISettings

        try:
            # Get theme
            theme_select = self.query_one("#theme-select", Select)
            theme = str(theme_select.value) if theme_select.value else "dark"

            # Get timestamp format
            format_select = self.query_one("#format-select", Select)
            timestamp_format = (
                str(format_select.value)
                if format_select.value
                else "%Y-%m-%d %H:%M:%S"
            )

            # Get max width
            width_input = self.query_one("#width-input", Input)
            try:
                max_width = int(width_input.value) if width_input.value else 80
                if max_width < 20:
                    max_width = 20
                if max_width > 500:
                    max_width = 500
            except ValueError:
                max_width = 80

            # Get show metadata
            metadata_checkbox = self.query_one("#metadata-checkbox", Checkbox)
            show_metadata = metadata_checkbox.value

            # Create new settings
            new_settings = UISettings(
                theme=theme,
                timestamp_format=timestamp_format,
                max_message_width=max_width,
                show_metadata=show_metadata,
            )

            self._on_save(new_settings)
            self.dismiss(True)

        except Exception as e:
            self.notify(f"Error saving settings: {e}", severity="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "btn-cancel":
            self.action_cancel()
        elif event.button.id == "btn-save":
            self._save_settings()
