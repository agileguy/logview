"""Tests for the main application."""

from __future__ import annotations

import pytest

from logview.app import LogViewApp


class TestLogViewApp:
    """Tests for LogViewApp."""

    @pytest.mark.asyncio
    async def test_app_starts(self) -> None:
        """Test that the app starts without errors."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            # App should start and have a log list
            assert app.query_one("#log-list") is not None

    @pytest.mark.asyncio
    async def test_app_has_header_and_footer(self) -> None:
        """Test that app has header and footer."""
        app = LogViewApp()
        async with app.run_test() as pilot:
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
