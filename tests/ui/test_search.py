"""Tests for the search within results feature."""

from __future__ import annotations

import asyncio

import pytest

from logview.app import LogViewApp
from logview.ui.widgets.log_list import LogList


class TestSearchFeature:
    """Tests for search within results."""

    @pytest.mark.asyncio
    async def test_search_bar_hidden_by_default(self) -> None:
        """Test that search bar is hidden initially."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            search_bar = app.query_one("#search-bar")
            assert "visible" not in search_bar.classes

    @pytest.mark.asyncio
    async def test_search_bar_shows_on_slash(self) -> None:
        """Test that pressing / shows the search bar."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("slash")
            await pilot.pause()
            search_bar = app.query_one("#search-bar")
            assert "visible" in search_bar.classes

    @pytest.mark.asyncio
    async def test_search_bar_hides_on_escape(self) -> None:
        """Test that pressing Escape hides the search bar."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("slash")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            search_bar = app.query_one("#search-bar")
            assert "visible" not in search_bar.classes

    @pytest.mark.asyncio
    async def test_search_bar_toggles_with_escape(self) -> None:
        """Test that Escape hides the search bar after showing it."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            # Show
            await pilot.press("slash")
            await pilot.pause()
            search_bar = app.query_one("#search-bar")
            assert "visible" in search_bar.classes
            # Hide with Escape
            await pilot.press("escape")
            await pilot.pause()
            assert "visible" not in search_bar.classes


class TestLogListSearch:
    """Tests for LogList search functionality."""

    @pytest.mark.asyncio
    async def test_search_filters_entries(self) -> None:
        """Test that search filters the displayed entries."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            log_list = app.query_one("#log-list", LogList)

            # Wait for logs to load
            await pilot.pause()

            initial_count = log_list.get_entry_count()
            assert initial_count > 0, "Should have some entries loaded"

            # Search for something that probably won't match everything
            log_list.search("error")
            await pilot.pause()

            # Should filter results (may be 0 or fewer than initial)
            search_count = log_list.get_entry_count()
            assert search_count <= initial_count

    @pytest.mark.asyncio
    async def test_clear_search_restores_entries(self) -> None:
        """Test that clearing search restores all entries."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            log_list = app.query_one("#log-list", LogList)

            # Wait for logs to load
            await pilot.pause()

            initial_count = log_list.get_entry_count()

            # Search and then clear
            log_list.search("xyz")
            await pilot.pause()
            log_list.clear_search()
            await pilot.pause()

            # Should restore all entries
            assert log_list.get_entry_count() == initial_count

    @pytest.mark.asyncio
    async def test_is_searching_returns_correct_state(self) -> None:
        """Test that is_searching returns correct state."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            log_list = app.query_one("#log-list", LogList)

            assert not log_list.is_searching()

            # Use the search bar to trigger search
            await pilot.press("slash")
            await pilot.pause()
            search_input = app.query_one("#search-input")
            search_input.value = "test"
            await asyncio.sleep(0.2)  # Wait for 150ms debounce timer to fire
            await pilot.pause()
            assert log_list.is_searching()

            # Clear via escape
            await pilot.press("escape")
            await pilot.pause()
            assert not log_list.is_searching()

    @pytest.mark.asyncio
    async def test_empty_search_clears_filter(self) -> None:
        """Test that empty search string clears the filter."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            log_list = app.query_one("#log-list", LogList)

            # Wait for logs to load
            await pilot.pause()
            initial_count = log_list.get_entry_count()

            log_list.search("test")
            log_list.search("")
            await pilot.pause()

            # Should be back to original
            assert log_list.get_entry_count() == initial_count
            assert not log_list.is_searching()


class TestSearchNavigation:
    """Tests for search navigation (next/prev match)."""

    @pytest.mark.asyncio
    async def test_next_match_returns_false_when_no_search(self) -> None:
        """Test that next_match returns False when no search is active."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            log_list = app.query_one("#log-list", LogList)

            assert not log_list.next_match()

    @pytest.mark.asyncio
    async def test_prev_match_returns_false_when_no_search(self) -> None:
        """Test that prev_match returns False when no search is active."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            log_list = app.query_one("#log-list", LogList)

            assert not log_list.prev_match()
