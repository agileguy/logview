"""Main Textual application for LogView."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Input, Label

from logview.adapters.base import LogSource
from logview.adapters.discovery import DiscoveredLog, discover_logs
from logview.adapters.gcp import GCP_AVAILABLE, GCPLogSource
from logview.adapters.gke import GKELogSource
from logview.adapters.logfile import LogFileSource
from logview.adapters.mock import MockLogSource
from logview.adapters.syslog import SyslogLogSource
from logview.config.loader import load_config, save_config
from logview.config.logging import get_logger, setup_logging
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
from logview.ui.screens.export import ExportModal
from logview.ui.screens.filter import FilterModal
from logview.ui.screens.help import HelpModal
from logview.ui.screens.settings import SettingsModal
from logview.ui.widgets.log_list import LogList

logger = get_logger("app")

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
        ("slash", "search", "Search"),
        ("n", "next_match", "Next"),
        ("N", "prev_match", "Prev"),
        ("e", "export", "Export"),
        ("s", "show_settings", "Settings"),
    ]

    DEFAULT_CSS = """
    #search-bar {
        dock: bottom;
        height: 3;
        display: none;
        background: $surface;
        border-top: solid $primary;
        padding: 0 1;
        layer: search-layer;
    }

    #search-bar.visible {
        display: block;
    }

    #search-bar Label {
        width: auto;
        padding: 1 1;
        color: $primary;
        text-style: bold;
    }

    #search-bar Input {
        width: 1fr;
    }

    #search-results {
        width: auto;
        padding: 1 1;
        color: $text-muted;
    }
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize the application.

        Args:
            config_path: Optional path to config file. Uses default if not provided.
        """
        super().__init__()
        self._config_path = config_path
        self._config: Config | None = None
        self._sources: list[LogSource] = []
        self._configured_sources: list[LogSource] = []  # Sources from config file
        self._discovered_sources: list[LogSource] = []  # Sources from discovery
        self._active_source: LogSource | None = None
        self._current_filter: Filter = Filter(limit=100)
        self._registered_paths: set[Path] = set()  # Track registered file paths to avoid duplicates

    def compose(self) -> ComposeResult:
        """Compose the application layout."""
        yield Header()
        yield LogList(id="log-list")
        with Horizontal(id="search-bar"):
            yield Label("Search:")
            yield Input(placeholder="Type to search...", id="search-input")
            yield Label("", id="search-results")
        yield Footer()

    def on_mount(self) -> None:
        """Handle mount event - load config and set up sources."""
        # Load configuration
        try:
            self._config = load_config(self._config_path)
            # Set up logging from config
            setup_logging(self._config.logging)
            logger.info("LogView starting up")
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
            logger.debug("No config loaded, skipping source registration")
            return

        logger.info("Registering %d sources from config", len(self._config.contexts))

        for context in self._config.contexts:
            try:
                logger.debug("Creating source from context: %s (type=%s)", context.name, context.type)
                source = self._create_source_from_context(context)
                if source:
                    # Track path for file-based sources to prevent duplicates
                    # Expand tilde before resolving to ensure consistent path comparison
                    source_path = None
                    if isinstance(context, (SyslogContext, LogFileContext)):
                        source_path = Path(os.path.expanduser(context.path))
                    if not self.register_source(source, path=source_path):
                        # Warn user about duplicate file path in config
                        self.notify(
                            f"Skipping duplicate source '{context.name}' (same file path)",
                            severity="warning",
                        )
            except Exception as e:
                logger.error("Error creating source '%s': %s", context.name, e)
                self.notify(f"Error creating source '{context.name}': {e}", severity="warning")

        # Auto-discover log files in background to avoid blocking UI
        # Use call_after_refresh to ensure event loop is running
        self.call_after_refresh(self._schedule_discovery)

    def _schedule_discovery(self) -> None:
        """Schedule log discovery as an async task."""
        import asyncio

        try:
            asyncio.create_task(self._discover_and_register_logs_async())
        except RuntimeError:
            # No running event loop - skip discovery
            pass

    async def _discover_and_register_logs_async(self) -> None:
        """Discover log files from configured paths and register them (runs in worker)."""
        if not self._config or not self._config.discovery:
            return

        discovery = self._config.discovery
        if not discovery.paths:
            return

        try:
            # Run discovery in thread to avoid blocking
            discovered = await self._run_discovery_in_thread(
                discovery.paths,
                discovery.max_depth,
                discovery.allowed_directories,
            )

            registered_count = 0
            for log in discovered:
                try:
                    source = LogFileSource(
                        name=log.name,
                        path=str(log.path),
                        format="auto",
                        allowed_directories=discovery.allowed_directories,
                    )
                    # Pass path to avoid duplicates with configured sources
                    # Mark as discovered=True for tree grouping in UI
                    if self.register_source(source, path=log.path, discovered=True):  # type: ignore[arg-type]
                        registered_count += 1
                except Exception:
                    # Skip individual files that fail to load (silently)
                    pass

            if registered_count > 0:
                self.notify(f"Discovered {registered_count} log file(s)")

        except Exception as e:
            self.notify(f"Log discovery error: {e}", severity="warning")

    async def _run_discovery_in_thread(
        self,
        paths: list[str],
        max_depth: int,
        allowed_dirs: list[str],
    ) -> list[DiscoveredLog]:
        """Run log discovery in a thread to avoid blocking the event loop."""
        import asyncio

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            discover_logs,
            paths,
            max_depth,
            allowed_dirs,
        )

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
            # Pass configured allowed_directories for security whitelist
            allowed_paths: list[Path] | None = None
            if self._config and self._config.discovery:
                allowed_paths = [Path(os.path.expanduser(d)) for d in self._config.discovery.allowed_directories]
            return SyslogLogSource(  # type: ignore[return-value]
                file_path=context.path,
                name=context.name,
                allowed_directories=allowed_paths,
            )
        elif isinstance(context, LogFileContext):
            # Pass configured allowed_directories for security whitelist
            allowed_dirs = None
            if self._config and self._config.discovery:
                allowed_dirs = self._config.discovery.allowed_directories
            return LogFileSource(  # type: ignore[return-value]
                name=context.name,
                path=context.path,
                format=context.format,
                allowed_directories=allowed_dirs,
            )
        elif isinstance(context, GCPContext):
            if not GCP_AVAILABLE:
                self.notify(
                    "GCP support requires: pip install logview[gcp]",
                    severity="warning",
                )
                return None
            return GCPLogSource(  # type: ignore[return-value]
                project_id=context.project,
                log_name=context.log_name,
                resource_type=context.resource_type,
                name=context.name,
            )
        elif isinstance(context, GKEContext):
            if not GCP_AVAILABLE:
                self.notify(
                    "GKE support requires: pip install logview[gcp]",
                    severity="warning",
                )
                return None
            return GKELogSource(  # type: ignore[return-value]
                project_id=context.project,
                cluster=context.cluster,
                location=context.location,
                default_namespace=context.default_namespace,
                name=context.name,
            )
        else:
            self.notify(f"Source type '{context.type}' not yet implemented", severity="warning")
            return None

    def register_source(
        self,
        source: LogSource,
        path: Path | None = None,
        discovered: bool = False,
    ) -> bool:
        """Register a log source.

        Args:
            source: The log source to register.
            path: Optional file path to track (prevents duplicate registrations).
            discovered: True if this source was auto-discovered (not from config).

        Returns:
            True if registered, False if path was already registered.
        """
        if path is not None:
            # Expand tilde and resolve to get canonical path for comparison
            resolved = Path(os.path.expanduser(str(path))).resolve()
            if resolved in self._registered_paths:
                return False
            self._registered_paths.add(resolved)

        self._sources.append(source)
        if discovered:
            self._discovered_sources.append(source)
        else:
            self._configured_sources.append(source)
        return True

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
        self._update_status_bar()

    def set_filter(self, log_filter: Filter) -> None:
        """Set the current filter and refresh.

        Args:
            log_filter: The filter to apply.
        """
        self._current_filter = log_filter
        log_list = self.query_one("#log-list", LogList)
        log_list.set_filter(log_filter)
        self.call_later(log_list.refresh_logs)
        self._update_status_bar()

    def _update_status_bar(self) -> None:
        """Update the status bar with adapter info and filter details."""
        if not self._active_source:
            self.sub_title = ""
            return

        # Build adapter info
        adapter_info = self._get_adapter_info(self._active_source)

        # Build filter info
        filter_info = self._get_filter_info(self._current_filter)

        # Combine into status bar text
        if filter_info:
            self.sub_title = f"{adapter_info} | {filter_info}"
        else:
            self.sub_title = adapter_info

    def _get_adapter_info(self, source: LogSource) -> str:
        """Get adapter type and metadata for status bar.

        Args:
            source: The log source to get info from.

        Returns:
            Formatted string with adapter type and relevant metadata.
        """
        # Check for source_type property (GCP, GKE)
        if hasattr(source, "source_type"):
            source_type = source.source_type.upper()

            if source_type == "GCP":
                # GCP: show project
                if hasattr(source, "project_id"):
                    return f"GCP: {source.project_id}"
                return "GCP"

            elif source_type == "GKE":
                # GKE: show cluster and project
                if hasattr(source, "cluster") and hasattr(source, "project_id"):
                    cluster = source.cluster
                    project = source.project_id
                    return f"GKE: {cluster} ({project})"
                elif hasattr(source, "cluster"):
                    return f"GKE: {source.cluster}"
                return "GKE"

        # Check for other adapter types using isinstance
        if isinstance(source, SyslogLogSource):
            return f"Syslog: {source._path.name}"
        elif isinstance(source, LogFileSource):
            return f"LogFile: {source._name}"
        elif isinstance(source, MockLogSource):
            return "Mock (testing)"

        # Fallback to name
        return source.name

    def _get_filter_info(self, log_filter: Filter) -> str:
        """Get filter information for status bar.

        Args:
            log_filter: The filter to format.

        Returns:
            Formatted string with filter details, or empty if no filters.
        """
        parts = []

        # Severity filter
        if log_filter.severity:
            parts.append(f"severity>={log_filter.severity.value}")

        # Text search
        if log_filter.text_search:
            # Truncate long search terms
            search = log_filter.text_search
            if len(search) > 20:
                search = search[:17] + "..."
            parts.append(f'text="{search}"')

        # Field filters
        for key, value in log_filter.fields.items():
            # Truncate long values
            display_value = value
            if len(display_value) > 15:
                display_value = display_value[:12] + "..."
            parts.append(f"{key}={display_value}")

        # Time range
        if log_filter.time_range:
            parts.append("time_range")

        # Limit (only show if not default)
        if log_filter.limit != 100:
            parts.append(f"limit={log_filter.limit}")

        if not parts:
            return ""

        return "Filters: " + ", ".join(parts)

    def action_show_context(self) -> None:
        """Show the context selector modal."""
        if not self._sources:
            self.notify("No log sources available")
            return

        # Find active source in configured or discovered lists
        active_configured_index: int | None = None
        active_discovered_index: int | None = None
        if self._active_source:
            try:
                active_configured_index = self._configured_sources.index(self._active_source)
            except ValueError:
                try:
                    active_discovered_index = self._discovered_sources.index(self._active_source)
                except ValueError:
                    pass

        def handle_selection(result: tuple[str, int] | None) -> None:
            if result is not None:
                category, index = result
                if category == "configured" and 0 <= index < len(self._configured_sources):
                    source = self._configured_sources[index]
                    self.set_active_source(source)
                    self.notify(f"Switched to {source.name}")
                elif category == "discovered" and 0 <= index < len(self._discovered_sources):
                    source = self._discovered_sources[index]
                    self.set_active_source(source)
                    self.notify(f"Switched to {source.name}")

        self.push_screen(
            ContextModal(
                configured_sources=self._configured_sources,
                discovered_sources=self._discovered_sources,
                active_configured_index=active_configured_index,
                active_discovered_index=active_discovered_index,
            ),
            handle_selection,
        )

    def action_show_filter(self) -> None:
        """Show the filter editor modal."""

        def handle_filter(new_filter: Filter | None) -> None:
            if new_filter:
                self.set_filter(new_filter)
                self.notify("Filter applied")

        # Get presets from config
        presets = self._config.presets if self._config else []

        self.push_screen(
            FilterModal(
                self._current_filter,
                presets=presets,
                on_save_preset=self._save_preset,
                on_delete_preset=self._delete_preset,
            ),
            handle_filter,
        )

    def _save_preset(self, preset: Any) -> None:
        """Save a filter preset to config.

        Args:
            preset: The FilterPreset to save.
        """
        if self._config is None:
            self._config = Config()

        # Check if preset with same name exists
        existing_idx = next(
            (i for i, p in enumerate(self._config.presets) if p.name == preset.name),
            None,
        )
        if existing_idx is not None:
            self._config.presets[existing_idx] = preset
        else:
            self._config.presets.append(preset)

        try:
            save_config(self._config, self._config_path)
            logger.info("Saved preset: %s", preset.name)
        except Exception as e:
            self.notify(f"Failed to save preset: {e}", severity="error")

    def _delete_preset(self, name: str) -> None:
        """Delete a filter preset from config.

        Args:
            name: Name of the preset to delete.
        """
        if self._config is None:
            return

        self._config.presets = [p for p in self._config.presets if p.name != name]

        try:
            save_config(self._config, self._config_path)
            logger.info("Deleted preset: %s", name)
        except Exception as e:
            self.notify(f"Failed to delete preset: {e}", severity="error")

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
        self.push_screen(HelpModal())

    def action_show_settings(self) -> None:
        """Show the settings modal."""
        if self._config is None:
            self._config = Config()

        def handle_save(new_settings: Any) -> None:
            if self._config:
                self._config.ui = new_settings
                try:
                    save_config(self._config, self._config_path)
                    # Apply theme change immediately
                    self.theme = (
                        "textual-dark"
                        if new_settings.theme == "dark"
                        else "textual-light"
                    )
                    self.notify("Settings saved")
                except Exception as e:
                    self.notify(f"Failed to save settings: {e}", severity="error")

        self.push_screen(
            SettingsModal(self._config.ui, handle_save),
            lambda result: None,  # Ignore dismiss result
        )

    def action_export(self) -> None:
        """Export visible logs to file."""
        log_list = self.query_one("#log-list", LogList)
        entries = log_list.get_visible_entries()

        if not entries:
            self.notify("No entries to export")
            return

        source_name = self._active_source.name if self._active_source else "logs"

        def handle_export(result: Any) -> None:
            if result:
                self.notify(f"Exported to {result}")

        self.push_screen(ExportModal(entries, source_name), handle_export)

    def action_search(self) -> None:
        """Show the search input."""
        search_bar = self.query_one("#search-bar")
        search_input = self.query_one("#search-input", Input)

        # Toggle search bar visibility
        if "visible" in search_bar.classes:
            self._hide_search_bar()
        else:
            search_bar.add_class("visible")
            search_input.focus()

    def _hide_search_bar(self) -> None:
        """Hide the search bar and clear search."""
        search_bar = self.query_one("#search-bar")
        search_input = self.query_one("#search-input", Input)
        search_results = self.query_one("#search-results", Label)

        search_bar.remove_class("visible")
        search_input.value = ""
        search_results.update("")

        # Clear search in log list
        log_list = self.query_one("#log-list", LogList)
        log_list.clear_search()
        log_list.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if event.input.id == "search-input":
            log_list = self.query_one("#log-list", LogList)
            log_list.search(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle search input submission (Enter key)."""
        if event.input.id == "search-input":
            # Move focus to log list to allow navigation
            log_list = self.query_one("#log-list", LogList)
            log_list.focus()

    def on_log_list_search_results_changed(
        self, event: LogList.SearchResultsChanged
    ) -> None:
        """Handle search results update."""
        search_results = self.query_one("#search-results", Label)
        if event.match_count > 0:
            search_results.update(f"{event.current_match}/{event.match_count} matches")
        elif self.query_one("#search-input", Input).value:
            search_results.update("No matches")
        else:
            search_results.update("")

    def action_next_match(self) -> None:
        """Move to next search match."""
        log_list = self.query_one("#log-list", LogList)
        if log_list.is_searching():
            log_list.next_match()
        else:
            self.notify("No active search (press / to search)")

    def action_prev_match(self) -> None:
        """Move to previous search match."""
        log_list = self.query_one("#log-list", LogList)
        if log_list.is_searching():
            log_list.prev_match()
        else:
            self.notify("No active search (press / to search)")

    def on_key(self, event: Any) -> None:
        """Handle key events for search bar escape."""
        # Check if search bar is visible and Escape is pressed
        search_bar = self.query_one("#search-bar")
        if "visible" in search_bar.classes and event.key == "escape":
            self._hide_search_bar()
            event.prevent_default()
            event.stop()

    def on_log_list_entry_selected(self, event: LogList.EntrySelected) -> None:
        """Handle log entry selection from the list."""
        self.push_screen(DetailModal(event.entry))
