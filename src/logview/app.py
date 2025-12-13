"""Main Textual application for LogView."""

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from logview.ui.widgets.log_list import LogList


class LogViewApp(App[None]):
    """A TUI application for viewing logs from multiple sources."""

    TITLE = "LogView"
    CSS_PATH = "ui/styles/theme.tcss"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("c", "show_context", "Context"),
        ("f", "show_filter", "Filter"),
        ("?", "show_help", "Help"),
        ("/", "search", "Search"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the application layout."""
        yield Header()
        yield LogList(id="log-list")
        yield Footer()

    def action_show_context(self) -> None:
        """Show the context selector modal."""
        # TODO: Implement in Phase 2
        self.notify("Context selector not yet implemented")

    def action_show_filter(self) -> None:
        """Show the filter editor modal."""
        # TODO: Implement in Phase 2
        self.notify("Filter editor not yet implemented")

    def action_show_help(self) -> None:
        """Show the help modal."""
        # TODO: Implement in Phase 2
        self.notify("Help not yet implemented")

    def action_search(self) -> None:
        """Show the search input."""
        # TODO: Implement in Phase 5
        self.notify("Search not yet implemented")
