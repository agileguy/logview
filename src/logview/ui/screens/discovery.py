"""Context discovery modal for auto-detecting GCP/GKE resources."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Label, Static

if TYPE_CHECKING:
    from logview.adapters.context_detector import DiscoveredContext


class DiscoveryModal(ModalScreen[list[DiscoveredContext] | None]):
    """Modal for reviewing and selecting discovered contexts.

    Displays discovered GCP projects and GKE clusters with checkboxes.
    User can select which contexts to add to configuration.
    Returns list of selected contexts or None if cancelled.
    """

    DEFAULT_CSS = """
    DiscoveryModal {
        align: center middle;
    }

    DiscoveryModal > Vertical {
        width: 70;
        height: auto;
        max-height: 30;
        background: $surface;
        border: thick $primary;
        padding: 1;
    }

    DiscoveryModal .discovery-title {
        text-style: bold;
        padding-bottom: 1;
        border-bottom: solid $primary;
        margin-bottom: 1;
    }

    DiscoveryModal .discovery-summary {
        padding-bottom: 1;
        color: $text-muted;
    }

    DiscoveryModal .discovery-empty {
        padding: 2 1;
        text-align: center;
        color: $warning;
    }

    DiscoveryModal VerticalScroll {
        height: auto;
        max-height: 15;
        margin-bottom: 1;
        border: solid $primary-background;
        background: $panel;
    }

    DiscoveryModal .context-item {
        padding: 0 1;
    }

    DiscoveryModal .context-item Checkbox {
        width: 100%;
    }

    DiscoveryModal .button-bar {
        height: 3;
        align: center middle;
        padding-top: 1;
        border-top: solid $primary;
    }

    DiscoveryModal Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "select", "Add Selected"),
        ("a", "select_all", "Select All"),
        ("n", "select_none", "Select None"),
    ]

    def __init__(
        self,
        discovered_contexts: list[DiscoveredContext],
        error_message: str | None = None,
    ) -> None:
        """Initialize the discovery modal.

        Args:
            discovered_contexts: List of discovered contexts to display.
            error_message: Optional error message to show if discovery failed.
        """
        super().__init__()
        self._discovered_contexts = discovered_contexts
        self._error_message = error_message
        self._checkboxes: list[Checkbox] = []

    def compose(self) -> ComposeResult:
        """Compose the modal content."""
        with Vertical():
            yield Label("Discovered Contexts", classes="discovery-title")

            # Show error if discovery failed
            if self._error_message:
                yield Static(
                    f"❌ Discovery failed: {self._error_message}",
                    classes="discovery-empty",
                )
            # Show empty message if no contexts found
            elif not self._discovered_contexts:
                yield Static(
                    "No accessible GCP projects or GKE clusters found.\n\n"
                    "Ensure you have:\n"
                    "1. Run: gcloud auth application-default login\n"
                    "2. Access to at least one GCP project\n"
                    "3. Installed detection libraries: pip install logview[detection]",
                    classes="discovery-empty",
                )
            else:
                # Show summary
                gcp_count = sum(
                    1 for ctx in self._discovered_contexts if ctx.context_type == "gcp"
                )
                gke_count = sum(
                    1 for ctx in self._discovered_contexts if ctx.context_type == "gke"
                )
                yield Label(
                    f"Found {gcp_count} GCP projects and {gke_count} GKE clusters",
                    classes="discovery-summary",
                )

                # Show list with checkboxes
                with VerticalScroll():
                    for ctx in self._discovered_contexts:
                        checkbox = Checkbox(
                            self._format_context_label(ctx),
                            value=True,  # Pre-select all by default
                            id=f"ctx-{ctx.context_type}-{ctx.project}-{ctx.cluster or 'none'}",
                        )
                        self._checkboxes.append(checkbox)
                        yield checkbox

            # Button bar
            with Horizontal(classes="button-bar"):
                if not self._error_message and self._discovered_contexts:
                    yield Button("Select All (a)", id="select-all", variant="default")
                    yield Button("Select None (n)", id="select-none", variant="default")
                    yield Button(
                        "Add Selected (↵)", id="add-selected", variant="primary"
                    )
                yield Button("Cancel (Esc)", id="cancel", variant="default")

    def _format_context_label(self, ctx: DiscoveredContext) -> str:
        """Format a context for display.

        Args:
            ctx: The discovered context.

        Returns:
            Formatted label string.
        """
        if ctx.context_type == "gcp":
            return f"[GCP] {ctx.project}"
        elif ctx.context_type == "gke":
            location_info = f" in {ctx.location}" if ctx.location else ""
            return f"[GKE] {ctx.cluster} ({ctx.project}){location_info}"
        else:
            return f"[{ctx.context_type.upper()}] {ctx.name}"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel":
            self.action_cancel()
        elif event.button.id == "add-selected":
            self.action_select()
        elif event.button.id == "select-all":
            self.action_select_all()
        elif event.button.id == "select-none":
            self.action_select_none()

    def action_cancel(self) -> None:
        """Cancel and close modal."""
        self.dismiss(None)

    def action_select(self) -> None:
        """Add selected contexts and close modal."""
        selected = [
            ctx
            for ctx, checkbox in zip(self._discovered_contexts, self._checkboxes)
            if checkbox.value
        ]
        self.dismiss(selected)

    def action_select_all(self) -> None:
        """Select all checkboxes."""
        for checkbox in self._checkboxes:
            checkbox.value = True

    def action_select_none(self) -> None:
        """Deselect all checkboxes."""
        for checkbox in self._checkboxes:
            checkbox.value = False
