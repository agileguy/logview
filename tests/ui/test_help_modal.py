"""Tests for the help modal."""

from __future__ import annotations

import pytest

from logview.app import LogViewApp
from logview.ui.screens.help import HelpModal


class TestHelpModal:
    """Tests for HelpModal."""

    @pytest.mark.asyncio
    async def test_modal_opens(self) -> None:
        """Test that the help modal opens correctly."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            # Push the help modal
            app.push_screen(HelpModal())
            await pilot.pause()

            # Modal should be displayed
            assert app.screen.__class__.__name__ == "HelpModal"

    @pytest.mark.asyncio
    async def test_modal_has_title(self) -> None:
        """Test that the modal has a title."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(HelpModal())
            await pilot.pause()

            # Query from the screen (modal)
            title = app.screen.query_one(".help-title")
            assert title is not None

    @pytest.mark.asyncio
    async def test_modal_has_sections(self) -> None:
        """Test that the modal has help sections."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(HelpModal())
            await pilot.pause()

            # Query from the screen (modal)
            sections = app.screen.query(".help-section-title")
            assert len(sections) == 3  # Navigation, Actions, General

    @pytest.mark.asyncio
    async def test_modal_has_close_button(self) -> None:
        """Test that the modal has a close button."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(HelpModal())
            await pilot.pause()

            close_btn = app.screen.query_one("#close-btn")
            assert close_btn is not None

    @pytest.mark.asyncio
    async def test_modal_closes_on_escape(self) -> None:
        """Test that the modal closes on Escape."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(HelpModal())
            await pilot.pause()

            # Press Escape
            await pilot.press("escape")
            await pilot.pause()

            # Should be back to main screen
            assert app.screen.__class__.__name__ != "HelpModal"

    @pytest.mark.asyncio
    async def test_modal_closes_on_button_click(self) -> None:
        """Test that the modal closes on close button click."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(HelpModal())
            await pilot.pause()

            # Click close button
            close_btn = app.screen.query_one("#close-btn")
            await pilot.click(close_btn)
            await pilot.pause()

            # Should be back to main screen
            assert app.screen.__class__.__name__ != "HelpModal"

    @pytest.mark.asyncio
    async def test_modal_opens_via_keybinding(self) -> None:
        """Test that the help modal opens via ? keybinding."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            # Press ? to open help
            await pilot.press("?")
            await pilot.pause()

            # Modal should be displayed
            assert app.screen.__class__.__name__ == "HelpModal"

    @pytest.mark.asyncio
    async def test_modal_shows_keybindings(self) -> None:
        """Test that the modal shows expected keybindings."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(HelpModal())
            await pilot.pause()

            # Check for common keybindings in help rows
            rows = app.screen.query(".help-row")
            assert len(rows) > 0  # Should have help rows
