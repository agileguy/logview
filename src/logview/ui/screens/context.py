"""Context selector modal for switching between log sources."""

from __future__ import annotations

from collections import defaultdict
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

    Displays a tree of available log sources organized by type:
    - GCP Logs grouped by project
    - GKE Logs grouped by cluster
    - Local Logs (syslog, logfile)
    - Discovered Logs
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

        active_node: TreeNode[tuple[str, int]] | None = None

        # Categorize configured sources
        gcp_by_project: dict[str, list[tuple[int, LogSource]]] = defaultdict(list)
        gke_by_cluster: dict[str, list[tuple[int, LogSource]]] = defaultdict(list)
        local_sources: list[tuple[int, LogSource]] = []

        for idx, source in enumerate(self._configured_sources):
            source_type = getattr(source, "source_type", None)
            if source_type == "gcp":
                project = getattr(source, "project_id", "unknown")
                gcp_by_project[project].append((idx, source))
            elif source_type == "gke":
                cluster = getattr(source, "cluster", "unknown")
                gke_by_cluster[cluster].append((idx, source))
            else:
                local_sources.append((idx, source))

        # Add GCP Logs section
        if gcp_by_project:
            gcp_node = tree.root.add(
                f"GCP Logs ({sum(len(v) for v in gcp_by_project.values())})",
                data=None,
            )
            for project, sources in sorted(gcp_by_project.items()):
                project_node = gcp_node.add(f"📁 {project}", data=None)
                for idx, source in sources:
                    is_active = idx == self._active_configured_index
                    label = f"● {source.name}" if is_active else source.name
                    node = project_node.add_leaf(label, data=("configured", idx))
                    if is_active:
                        active_node = node
                        project_node.expand()
                        gcp_node.expand()

        # Add GKE Logs section
        if gke_by_cluster:
            gke_node = tree.root.add(
                f"GKE Logs ({sum(len(v) for v in gke_by_cluster.values())})",
                data=None,
            )
            for cluster, sources in sorted(gke_by_cluster.items()):
                cluster_node = gke_node.add(f"☸ {cluster}", data=None)
                for idx, source in sources:
                    is_active = idx == self._active_configured_index
                    label = f"● {source.name}" if is_active else source.name
                    node = cluster_node.add_leaf(label, data=("configured", idx))
                    if is_active:
                        active_node = node
                        cluster_node.expand()
                        gke_node.expand()

        # Add Local Logs section (syslog, logfile, mock)
        if local_sources:
            local_node = tree.root.add(
                f"Local Logs ({len(local_sources)})",
                data=None,
            )
            for idx, source in local_sources:
                is_active = idx == self._active_configured_index
                label = f"● {source.name}" if is_active else source.name
                node = local_node.add_leaf(label, data=("configured", idx))
                if is_active:
                    active_node = node
                    local_node.expand()

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
