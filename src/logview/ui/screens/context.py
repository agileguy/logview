"""Context selector modal for switching between log sources."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Tree
from textual.widgets.tree import TreeNode

if TYPE_CHECKING:
    from logview.adapters.base import LogSource


class ContextModal(ModalScreen[tuple[str, int] | None]):
    """Modal for selecting a log source context.

    Displays a tree of available log sources with configured sources at
    root level and discovered sources in a collapsible "Discovered Logs" node.
    Returns a tuple of (category, index) or None if cancelled.
    """

    DEFAULT_CSS = """
    ContextModal {
        align: center middle;
    }

    ContextModal > Vertical {
        width: 60;
        height: auto;
        max-height: 25;
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

    ContextModal Tree {
        height: auto;
        max-height: 15;
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
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "select", "Select"),
    ]

    def __init__(
        self,
        configured_sources: list[LogSource],
        discovered_sources: list[LogSource],
        active_configured_index: int | None = None,
        active_discovered_index: int | None = None,
    ) -> None:
        """Initialize the context selector modal.

        Args:
            configured_sources: List of sources from config file.
            discovered_sources: List of auto-discovered sources.
            active_configured_index: Index of active source in configured list.
            active_discovered_index: Index of active source in discovered list.
        """
        super().__init__()
        self._configured_sources = configured_sources
        self._discovered_sources = discovered_sources
        self._active_configured_index = active_configured_index
        self._active_discovered_index = active_discovered_index

    def compose(self) -> ComposeResult:
        """Compose the modal content."""
        with Vertical():
            yield Label("Select Log Source", classes="context-title")

            # Create tree widget
            tree: Tree[tuple[str, int]] = Tree("Log Sources", id="source-tree")
            tree.show_root = False
            tree.guide_depth = 2

            yield tree

            # Button bar
            with Vertical(classes="button-bar"):
                yield Button("Select [Enter]", id="btn-select", variant="primary")
                yield Button("Cancel [Esc]", id="btn-cancel")

    def on_mount(self) -> None:
        """Handle mount event - populate tree and select active source."""
        tree = self.query_one("#source-tree", Tree)

        # Add configured sources at root level
        active_node: TreeNode[tuple[str, int]] | None = None

        for idx, source in enumerate(self._configured_sources):
            is_active = idx == self._active_configured_index
            label = f"● {source.name}" if is_active else source.name
            node = tree.root.add_leaf(label, data=("configured", idx))
            if is_active:
                active_node = node

        # Add discovered sources under a collapsible node
        if self._discovered_sources:
            discovered_node = tree.root.add(
                f"Discovered Logs ({len(self._discovered_sources)})",
                data=None,
            )
            # Start collapsed
            discovered_node.collapse()

            for idx, source in enumerate(self._discovered_sources):
                is_active = idx == self._active_discovered_index
                label = f"● {source.name}" if is_active else source.name
                node = discovered_node.add_leaf(label, data=("discovered", idx))
                if is_active:
                    active_node = node
                    # Expand the discovered node if active source is in it
                    discovered_node.expand()

        # Expand root and move cursor to active node
        tree.root.expand()
        if active_node:
            tree.move_cursor(active_node)

    def action_cancel(self) -> None:
        """Cancel and close the modal."""
        self.dismiss(None)

    def action_select(self) -> None:
        """Select the current context and close."""
        tree = self.query_one("#source-tree", Tree)
        node = tree.cursor_node
        if node and node.data is not None:
            self.dismiss(node.data)
        else:
            # If on a branch node (like "Discovered Logs"), toggle it
            if node and node.allow_expand:
                node.toggle()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-cancel":
            self.action_cancel()
        elif event.button.id == "btn-select":
            self.action_select()

    def on_tree_node_selected(self, event: Tree.NodeSelected[tuple[str, int]]) -> None:
        """Handle tree node selection (double-click or Enter on leaf)."""
        if event.node.data is not None:
            self.dismiss(event.node.data)
