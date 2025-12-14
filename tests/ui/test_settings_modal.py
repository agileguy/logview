"""Tests for the settings modal."""

from __future__ import annotations

import pytest

from logview.app import LogViewApp
from logview.config.schema import UISettings
from logview.ui.screens.settings import SettingsModal


class TestSettingsModal:
    """Tests for SettingsModal."""

    @pytest.mark.asyncio
    async def test_modal_opens(self) -> None:
        """Test that the settings modal opens correctly."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            settings = UISettings()
            modal = SettingsModal(settings, lambda s: None)
            app.push_screen(modal)
            await pilot.pause()

            # Modal should be displayed
            assert app.screen.__class__.__name__ == "SettingsModal"

    @pytest.mark.asyncio
    async def test_modal_has_theme_select(self) -> None:
        """Test that the modal has a theme selector."""
        from textual.widgets import Select

        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            settings = UISettings()
            modal = SettingsModal(settings, lambda s: None)
            app.push_screen(modal)
            await pilot.pause()

            theme_select = app.screen.query_one("#theme-select", Select)
            assert theme_select is not None

    @pytest.mark.asyncio
    async def test_modal_has_format_select(self) -> None:
        """Test that the modal has a timestamp format selector."""
        from textual.widgets import Select

        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            settings = UISettings()
            modal = SettingsModal(settings, lambda s: None)
            app.push_screen(modal)
            await pilot.pause()

            format_select = app.screen.query_one("#format-select", Select)
            assert format_select is not None

    @pytest.mark.asyncio
    async def test_modal_has_width_input(self) -> None:
        """Test that the modal has a width input."""
        from textual.widgets import Input

        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            settings = UISettings()
            modal = SettingsModal(settings, lambda s: None)
            app.push_screen(modal)
            await pilot.pause()

            width_input = app.screen.query_one("#width-input", Input)
            assert width_input is not None

    @pytest.mark.asyncio
    async def test_modal_closes_on_escape(self) -> None:
        """Test that the modal closes on Escape."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            settings = UISettings()
            modal = SettingsModal(settings, lambda s: None)
            app.push_screen(modal)
            await pilot.pause()

            await pilot.press("escape")
            await pilot.pause()

            assert app.screen.__class__.__name__ != "SettingsModal"

    @pytest.mark.asyncio
    async def test_modal_opens_via_keybinding(self) -> None:
        """Test that the settings modal opens via s keybinding."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            await pilot.press("s")
            await pilot.pause()

            assert app.screen.__class__.__name__ == "SettingsModal"

    @pytest.mark.asyncio
    async def test_modal_populates_current_theme(self) -> None:
        """Test that the modal shows the current theme."""
        from textual.widgets import Select

        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            settings = UISettings(theme="light")
            modal = SettingsModal(settings, lambda s: None)
            app.push_screen(modal)
            await pilot.pause()

            theme_select = app.screen.query_one("#theme-select", Select)
            assert theme_select.value == "light"


class TestUISettings:
    """Tests for UISettings schema."""

    def test_default_theme_is_dark(self) -> None:
        """Test that default theme is dark."""
        settings = UISettings()
        assert settings.theme == "dark"

    def test_default_timestamp_format(self) -> None:
        """Test the default timestamp format."""
        settings = UISettings()
        assert settings.timestamp_format == "%Y-%m-%d %H:%M:%S"

    def test_default_max_message_width(self) -> None:
        """Test the default max message width."""
        settings = UISettings()
        assert settings.max_message_width == 80

    def test_default_show_metadata_is_false(self) -> None:
        """Test that show_metadata defaults to False."""
        settings = UISettings()
        assert settings.show_metadata is False
