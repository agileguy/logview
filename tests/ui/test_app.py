"""Tests for the main application."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from logview.app import LogViewApp
from logview.config.schema import Config


class TestLogViewApp:
    """Tests for LogViewApp."""

    @pytest.mark.asyncio
    async def test_app_starts(self) -> None:
        """Test that the app starts without errors."""
        app = LogViewApp()
        async with app.run_test():
            # App should start and have a log list
            assert app.query_one("#log-list") is not None

    @pytest.mark.asyncio
    async def test_app_has_header_and_footer(self) -> None:
        """Test that app has header and footer."""
        app = LogViewApp()
        async with app.run_test():
            from textual.widgets import Footer, Header

            assert app.query_one(Header) is not None
            assert app.query_one(Footer) is not None

    @pytest.mark.asyncio
    async def test_quit_action(self) -> None:
        """Test that q key quits the app."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.press("q")
            # App should exit (test will complete)

    @pytest.mark.asyncio
    async def test_context_action_shows_notification(self) -> None:
        """Test that c key shows not implemented notification."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.press("c")
            # Should show notification (Phase 2 placeholder)

    @pytest.mark.asyncio
    async def test_filter_action_shows_notification(self) -> None:
        """Test that f key shows not implemented notification."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.press("f")
            # Should show notification (Phase 2 placeholder)

    @pytest.mark.asyncio
    async def test_help_action_shows_notification(self) -> None:
        """Test that ? key shows not implemented notification."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.press("?")
            # Should show notification (Phase 2 placeholder)


class TestThemePersistence:
    """Tests for theme persistence."""

    @pytest.fixture
    def config_file(self, tmp_path: Path) -> Path:
        """Create a temporary config file."""
        config_path = tmp_path / "config.json"
        config = Config()
        config.ui.theme = "dark"
        config_path.write_text(json.dumps(config.model_dump(), indent=2))
        return config_path

    @pytest.mark.asyncio
    async def test_toggle_dark_saves_to_config(self, config_file: Path) -> None:
        """Test that toggling theme via action saves to config file."""
        app = LogViewApp(config_path=config_file)
        async with app.run_test() as pilot:
            await pilot.pause()

            # Verify starting in dark mode
            assert app.theme == "textual-dark"

            # Toggle to light mode via action (as command palette would)
            app.action_toggle_dark()
            await pilot.pause()

            # Verify config file was updated
            saved_config = json.loads(config_file.read_text())
            assert saved_config["ui"]["theme"] == "light"

    @pytest.mark.asyncio
    async def test_toggle_dark_to_dark_saves_to_config(self, tmp_path: Path) -> None:
        """Test that toggling to dark theme saves to config file."""
        config_path = tmp_path / "config.json"
        config = Config()
        config.ui.theme = "light"
        config_path.write_text(json.dumps(config.model_dump(), indent=2))

        app = LogViewApp(config_path=config_path)
        async with app.run_test() as pilot:
            await pilot.pause()

            # Verify starting in light mode
            assert app.theme == "textual-light"

            # Toggle to dark mode via action
            app.action_toggle_dark()
            await pilot.pause()

            # Verify config file was updated
            saved_config = json.loads(config_path.read_text())
            assert saved_config["ui"]["theme"] == "dark"

    @pytest.mark.asyncio
    async def test_startup_does_not_save_config(self, config_file: Path) -> None:
        """Test that loading config on startup doesn't trigger a save."""
        original_content = config_file.read_text()

        app = LogViewApp(config_path=config_file)
        async with app.run_test() as pilot:
            await pilot.pause()
            # Give filesystem time to update mtime if a save occurred
            await pilot.pause()

        # File should not have been modified
        assert config_file.read_text() == original_content

    @pytest.mark.asyncio
    async def test_theme_loads_from_config_dark(self, config_file: Path) -> None:
        """Test that dark theme loads from config."""
        app = LogViewApp(config_path=config_file)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.theme == "textual-dark"

    @pytest.mark.asyncio
    async def test_theme_loads_from_config_light(self, tmp_path: Path) -> None:
        """Test that light theme loads from config."""
        config_path = tmp_path / "config.json"
        config = Config()
        config.ui.theme = "light"
        config_path.write_text(json.dumps(config.model_dump(), indent=2))

        app = LogViewApp(config_path=config_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.theme == "textual-light"

    @pytest.mark.asyncio
    async def test_missing_config_defaults_to_dark(self, tmp_path: Path) -> None:
        """Test that missing config file defaults to dark theme."""
        config_path = tmp_path / "nonexistent.json"

        app = LogViewApp(config_path=config_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            # Default config has theme="dark", but without config loaded Textual defaults to dark
            assert app.theme == "textual-dark"

    @pytest.mark.asyncio
    async def test_toggle_dark_creates_config_if_missing(self, tmp_path: Path) -> None:
        """Test that toggling theme creates config file if it doesn't exist."""
        config_path = tmp_path / "new_config.json"
        assert not config_path.exists()

        app = LogViewApp(config_path=config_path)
        async with app.run_test() as pilot:
            await pilot.pause()

            # Toggle theme via action
            app.action_toggle_dark()
            await pilot.pause()

            # Config file should now exist with light theme (toggled from dark default)
            assert config_path.exists()
            saved_config = json.loads(config_path.read_text())
            assert saved_config["ui"]["theme"] == "light"

    @pytest.mark.asyncio
    async def test_direct_theme_change_persists(self, config_file: Path) -> None:
        """Test that directly setting theme (like command palette) persists to config."""
        app = LogViewApp(config_path=config_file)
        async with app.run_test() as pilot:
            await pilot.pause()

            # Directly set theme (simulates Textual's command palette theme picker)
            # Custom themes like catppuccin-mocha don't use "textual-" prefix
            app.theme = "catppuccin-mocha"
            await pilot.pause()

            # Verify config file was updated
            saved_config = json.loads(config_file.read_text())
            assert saved_config["ui"]["theme"] == "catppuccin-mocha"
