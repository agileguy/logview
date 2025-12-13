"""Context selector modal for switching between log sources."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, OptionList
from textual.widgets.option_list import Option

if TYPE_CHECKING:
    from logview.adapters.base import LogSource


class ContextModal(ModalScreen[str | None]):
    """Modal for selecting a log source context.

    Displays a list of available log sources and allows the user
    to select one. Returns the selected source name or None if cancelled.
    """

    DEFAULT_CSS = """
    ContextModal {
        align: center middle;
    }

    ContextModal > Vertical {
        width: 60;
        height: auto;
        max-height: 20;
        background: $surface;
        border: thick $primary;
        padding: 1;
    }

    ContextModal .context-title {
        text-style: bold;
        padding-bottom: 1;
        border-bottom: solid $primary;
        margin-bottom: 1;
    }

    ContextModal OptionList {
        height: auto;
        max-height: 10;
        margin-bottom: 1;
    }

    ContextModal .button-bar {
        height: 3;
        align: center middle;
        padding-top: 1;
        border-top: solid $primary;
    }

    ContextModal Button {
        margin: 0 1;
    }

    ContextModal .option-active {
        text-style: bold;
        color: $success;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "select", "Select"),
    ]

    def __init__(
        self,
        sources: list[LogSource],
        active_source_name: str | None = None,
    ) -> None:
        """Initialize the context selector modal.

        Args:
            sources: List of available log sources.
            active_source_name: Name of the currently active source.
        """
        super().__init__()
        self._sources = sources
        self._active_source_name = active_source_name

    def compose(self) -> ComposeResult:
        """Compose the modal content."""
        with Vertical():
            yield Label("Select Log Source", classes="context-title")

            # Create options for each source
            options: list[Option] = []
            for source in self._sources:
                is_active = source.name == self._active_source_name
                label = f"● {source.name}" if is_active else f"  {source.name}"
                options.append(Option(label, id=source.name))

            option_list = OptionList(*options, id="source-list")
            yield option_list

            # Button bar
            with Vertical(classes="button-bar"):
                yield Button("Select [Enter]", id="btn-select", variant="primary")
                yield Button("Cancel [Esc]", id="btn-cancel")

    def on_mount(self) -> None:
        """Handle mount event - select the active source by default."""
        option_list = self.query_one("#source-list", OptionList)
        if self._active_source_name:
            # Find and highlight the active source
            for idx, source in enumerate(self._sources):
                if source.name == self._active_source_name:
                    option_list.highlighted = idx
                    break

    def action_cancel(self) -> None:
        """Cancel and close the modal."""
        self.dismiss(None)

    def action_select(self) -> None:
        """Select the current context and close."""
        option_list = self.query_one("#source-list", OptionList)
        if option_list.highlighted is not None:
            highlighted = option_list.highlighted
            if highlighted < len(self._sources):
                selected_name = self._sources[highlighted].name
                self.dismiss(selected_name)
                return
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-cancel":
            self.action_cancel()
        elif event.button.id == "btn-select":
            self.action_select()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection (double-click or Enter on option)."""
        if event.option.id:
            self.dismiss(event.option.id)
