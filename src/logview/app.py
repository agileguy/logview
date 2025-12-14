"""Main Textual application for LogView."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from logview.adapters.base import LogSource
from logview.adapters.logfile import LogFileSource
from logview.adapters.mock import MockLogSource
from logview.adapters.syslog import SyslogLogSource
from logview.config.loader import load_config, save_config
from logview.config.schema import (
    Config,
    GCPContext,
    GKEContext,
    LogFileContext,
    MockContext,
    SyslogContext,
)
from logview.domain.models import Filter
from logview.ui.screens.context import ContextModal
from logview.ui.screens.detail import DetailModal
from logview.ui.screens.filter import FilterModal
from logview.ui.widgets.log_list import LogList

if TYPE_CHECKING:
    pass


class LogViewApp(App[None]):
    """A TUI application for viewing logs from multiple sources."""

    TITLE = "LogView"
    CSS_PATH = "ui/styles/theme.tcss"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("c", "show_context", "Context"),
        ("f", "show_filter", "Filter"),
        ("r", "refresh", "Refresh"),
        ("?", "show_help", "Help"),
        ("/", "search", "Search"),
    ]

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize the application.

        Args:
            config_path: Optional path to config file. Uses default if not provided.
        """
        super().__init__()
        self._config_path = config_path
        self._config: Config | None = None
        self._sources: list[LogSource] = []
        self._active_source: LogSource | None = None
        self._current_filter: Filter = Filter(limit=100)

    def compose(self) -> ComposeResult:
        """Compose the application layout."""
        yield Header()
        yield LogList(id="log-list")
        yield Footer()

    def on_mount(self) -> None:
        """Handle mount event - load config and set up sources."""
        # Load configuration
        try:
            self._config = load_config(self._config_path)
            self._register_sources_from_config()
        except Exception as e:
            self.notify(f"Error loading config: {e}", severity="error")

        # Always apply UI settings (sets up theme watcher)
        self._apply_ui_settings()

        # If no sources from config, register default mock
        if not self._sources:
            mock_source = MockLogSource(seed=42)
            self.register_source(mock_source)  # type: ignore[arg-type]

        # Set first source as active
        if self._sources:
            self.set_active_source(self._sources[0])

    def _apply_ui_settings(self) -> None:
        """Apply UI settings from configuration."""
        if self._config:
            # Apply theme from config (dark mode is default in Textual)
            self.theme = "textual-dark" if self._config.ui.theme == "dark" else "textual-light"

    def action_toggle_dark(self) -> None:
        """Toggle dark mode and save the preference to config."""
        # Call parent implementation to actually toggle
        super().action_toggle_dark()

        # Save the new preference (theme is now "textual-dark" or "textual-light")
        self._save_theme_preference()

    def _save_theme_preference(self) -> None:
        """Save current theme preference to config file."""
        # Ensure we have a config to save
        if self._config is None:
            self._config = Config()

        # Map Textual theme name to our config value
        is_dark = self.theme == "textual-dark"
        self._config.ui.theme = "dark" if is_dark else "light"
        try:
            save_config(self._config, self._config_path)
        except Exception as e:
            self.notify(f"Failed to save theme preference: {e}", severity="warning")

    def _register_sources_from_config(self) -> None:
        """Register log sources from configuration."""
        if not self._config:
            return

        for context in self._config.contexts:
            try:
                source = self._create_source_from_context(context)
                if source:
                    self.register_source(source)
            except Exception as e:
                self.notify(f"Error creating source '{context.name}': {e}", severity="warning")

    def _create_source_from_context(
        self,
        context: MockContext | SyslogContext | GCPContext | GKEContext | LogFileContext,
    ) -> LogSource | None:
        """Create a log source from a config context.

        Args:
            context: The context configuration.

        Returns:
            A LogSource instance or None if the type is not supported yet.
        """
        if isinstance(context, MockContext):
            return MockLogSource(seed=context.seed)  # type: ignore[return-value]
        elif isinstance(context, SyslogContext):
            return SyslogLogSource(file_path=context.path)  # type: ignore[return-value]
        elif isinstance(context, LogFileContext):
            return LogFileSource(  # type: ignore[return-value]
                name=context.name,
                path=context.path,
                format=context.format,
            )
        else:
            # GCP and GKE not implemented yet
            self.notify(f"Source type '{context.type}' not yet implemented", severity="warning")
            return None

    def register_source(self, source: LogSource) -> None:
        """Register a log source.

        Args:
            source: The log source to register.
        """
        self._sources.append(source)

    def set_active_source(self, source: LogSource) -> None:
        """Set the active log source and refresh.

        Args:
            source: The source to make active.
        """
        self._active_source = source
        log_list = self.query_one("#log-list", LogList)
        log_list.set_source(source)
        log_list.set_filter(self._current_filter)
        self.call_later(log_list.refresh_logs)
        self.sub_title = source.name

    def set_filter(self, log_filter: Filter) -> None:
        """Set the current filter and refresh.

        Args:
            log_filter: The filter to apply.
        """
        self._current_filter = log_filter
        log_list = self.query_one("#log-list", LogList)
        log_list.set_filter(log_filter)
        self.call_later(log_list.refresh_logs)

    def action_show_context(self) -> None:
        """Show the context selector modal."""
        if not self._sources:
            self.notify("No log sources available")
            return

        # Find active source index
        active_index: int | None = None
        if self._active_source:
            try:
                active_index = self._sources.index(self._active_source)
            except ValueError:
                pass

        def handle_selection(selected_index: int | None) -> None:
            if selected_index is not None and 0 <= selected_index < len(self._sources):
                source = self._sources[selected_index]
                self.set_active_source(source)
                self.notify(f"Switched to {source.name}")

        self.push_screen(
            ContextModal(self._sources, active_source_index=active_index),
            handle_selection,
        )

    def action_show_filter(self) -> None:
        """Show the filter editor modal."""

        def handle_filter(new_filter: Filter | None) -> None:
            if new_filter:
                self.set_filter(new_filter)
                self.notify("Filter applied")

        self.push_screen(
            FilterModal(self._current_filter),
            handle_filter,
        )

    def action_refresh(self) -> None:
        """Refresh the log list."""
        log_list = self.query_one("#log-list", LogList)
        self.call_later(log_list.refresh_logs)
        self.notify("Refreshing logs...")

    def action_show_detail(self) -> None:
        """Show detail view for the selected entry."""
        log_list = self.query_one("#log-list", LogList)
        entry = log_list.get_selected_entry()
        if entry:
            self.push_screen(DetailModal(entry))
        else:
            self.notify("No entry selected")

    def action_show_help(self) -> None:
        """Show the help modal."""
        # TODO: Implement in later phase
        self.notify("Help not yet implemented")

    def action_search(self) -> None:
        """Show the search input."""
        # TODO: Implement in Phase 5
        self.notify("Search not yet implemented")

    def on_log_list_entry_selected(self, event: LogList.EntrySelected) -> None:
        """Handle log entry selection from the list."""
        self.push_screen(DetailModal(event.entry))
