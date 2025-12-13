"""Tests for the filter editor modal."""

from __future__ import annotations

import pytest

from logview.app import LogViewApp
from logview.domain.models import Filter, Severity
from logview.ui.screens.filter import FilterModal


class TestFilterModal:
    """Tests for FilterModal."""

    @pytest.mark.asyncio
    async def test_modal_opens(self) -> None:
        """Test that the filter modal opens correctly."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(FilterModal())
            await pilot.pause()

            assert app.screen.__class__.__name__ == "FilterModal"

    @pytest.mark.asyncio
    async def test_modal_has_time_select(self) -> None:
        """Test that the modal has a time range select."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(FilterModal())
            await pilot.pause()

            selects = app.screen.query("Select")
            assert len(list(selects)) >= 1

    @pytest.mark.asyncio
    async def test_modal_has_severity_select(self) -> None:
        """Test that the modal has a severity select."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(FilterModal())
            await pilot.pause()

            selects = list(app.screen.query("Select"))
            assert len(selects) >= 2

    @pytest.mark.asyncio
    async def test_modal_has_text_search_input(self) -> None:
        """Test that the modal has a text search input."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(FilterModal())
            await pilot.pause()

            inputs = app.screen.query("Input")
            assert len(list(inputs)) >= 1

    @pytest.mark.asyncio
    async def test_modal_has_limit_input(self) -> None:
        """Test that the modal has a limit input."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(FilterModal())
            await pilot.pause()

            limit_input = app.screen.query_one("#limit-input")
            assert limit_input is not None

    @pytest.mark.asyncio
    async def test_modal_closes_on_escape(self) -> None:
        """Test that pressing Escape closes the modal."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(FilterModal())
            await pilot.pause()

            assert app.screen.__class__.__name__ == "FilterModal"

            await pilot.press("escape")
            await pilot.pause()

            assert app.screen.__class__.__name__ != "FilterModal"

    @pytest.mark.asyncio
    async def test_modal_has_apply_button(self) -> None:
        """Test that the modal has an apply button."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(FilterModal())
            await pilot.pause()

            buttons = app.screen.query("Button")
            apply_button = any("Apply" in str(b.label) for b in buttons)
            assert apply_button

    @pytest.mark.asyncio
    async def test_modal_has_cancel_button(self) -> None:
        """Test that the modal has a cancel button."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(FilterModal())
            await pilot.pause()

            buttons = app.screen.query("Button")
            cancel_button = any("Cancel" in str(b.label) for b in buttons)
            assert cancel_button

    @pytest.mark.asyncio
    async def test_modal_has_clear_button(self) -> None:
        """Test that the modal has a clear button."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(FilterModal())
            await pilot.pause()

            buttons = app.screen.query("Button")
            clear_button = any("Clear" in str(b.label) for b in buttons)
            assert clear_button


class TestFilterModalWithCurrentFilter:
    """Tests for FilterModal with pre-existing filter."""

    @pytest.fixture
    def current_filter(self) -> Filter:
        """Create a sample filter for testing."""
        return Filter(
            severity=Severity.ERROR,
            text_search="database",
            limit=500,
        )

    @pytest.mark.asyncio
    async def test_modal_stores_current_filter(self, current_filter: Filter) -> None:
        """Test that the modal stores the current filter."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            modal = FilterModal(current_filter)
            app.push_screen(modal)
            await pilot.pause()

            assert modal._current_filter == current_filter

    @pytest.mark.asyncio
    async def test_modal_populates_text_search(self, current_filter: Filter) -> None:
        """Test that text search is pre-populated."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            modal = FilterModal(current_filter)
            app.push_screen(modal)
            await pilot.pause()

            from textual.widgets import Input

            text_input = app.screen.query_one("#text-search", Input)
            assert text_input.value == "database"

    @pytest.mark.asyncio
    async def test_modal_populates_limit(self, current_filter: Filter) -> None:
        """Test that limit is pre-populated."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            modal = FilterModal(current_filter)
            app.push_screen(modal)
            await pilot.pause()

            from textual.widgets import Input

            limit_input = app.screen.query_one("#limit-input", Input)
            assert limit_input.value == "500"


class TestFilterModalReturnsValue:
    """Tests for filter modal return values."""

    @pytest.mark.asyncio
    async def test_modal_returns_none_on_cancel(self) -> None:
        """Test that cancelling returns None."""
        app = LogViewApp()
        result = "not_set"

        def capture_result(value: Filter | None) -> None:
            nonlocal result
            result = value

        async with app.run_test() as pilot:
            app.push_screen(FilterModal(), capture_result)
            await pilot.pause()

            await pilot.press("escape")
            await pilot.pause()

        assert result is None


class TestFilterModalDefaults:
    """Tests for filter modal default values."""

    @pytest.mark.asyncio
    async def test_modal_defaults_no_filter(self) -> None:
        """Test that modal works with no current filter."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            modal = FilterModal()  # No current filter
            app.push_screen(modal)
            await pilot.pause()

            # Should not crash
            assert app.screen.__class__.__name__ == "FilterModal"

    @pytest.mark.asyncio
    async def test_modal_default_limit_is_1000(self) -> None:
        """Test that default limit is 1000."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            modal = FilterModal()
            app.push_screen(modal)
            await pilot.pause()

            from textual.widgets import Input

            limit_input = app.screen.query_one("#limit-input", Input)
            assert limit_input.value == "1000"
