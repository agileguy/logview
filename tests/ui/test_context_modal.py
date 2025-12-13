"""Tests for the context selector modal."""

from __future__ import annotations

import pytest

from logview.app import LogViewApp
from logview.ui.screens.context import ContextModal


class MockSourceForTest:
    """Simple mock source for testing."""

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name


@pytest.fixture
def mock_sources() -> list[MockSourceForTest]:
    """Create mock sources for testing."""
    return [
        MockSourceForTest("Mock (testing)"),
        MockSourceForTest("Syslog (/var/log/syslog)"),
        MockSourceForTest("GCP Logging"),
    ]


class TestContextModal:
    """Tests for ContextModal."""

    @pytest.mark.asyncio
    async def test_modal_opens(self, mock_sources: list[MockSourceForTest]) -> None:
        """Test that the context modal opens correctly."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(ContextModal(mock_sources))  # type: ignore[arg-type]
            await pilot.pause()

            assert app.screen.__class__.__name__ == "ContextModal"

    @pytest.mark.asyncio
    async def test_modal_has_option_list(self, mock_sources: list[MockSourceForTest]) -> None:
        """Test that the modal has an option list."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(ContextModal(mock_sources))  # type: ignore[arg-type]
            await pilot.pause()

            option_lists = app.screen.query("OptionList")
            assert len(list(option_lists)) == 1

    @pytest.mark.asyncio
    async def test_modal_shows_all_sources(self, mock_sources: list[MockSourceForTest]) -> None:
        """Test that the modal shows all available sources."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(ContextModal(mock_sources))  # type: ignore[arg-type]
            await pilot.pause()

            from textual.widgets import OptionList

            option_list = app.screen.query_one(OptionList)
            assert option_list.option_count == 3

    @pytest.mark.asyncio
    async def test_modal_closes_on_escape(
        self, mock_sources: list[MockSourceForTest]
    ) -> None:
        """Test that pressing Escape closes the modal."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(ContextModal(mock_sources))  # type: ignore[arg-type]
            await pilot.pause()

            assert app.screen.__class__.__name__ == "ContextModal"

            await pilot.press("escape")
            await pilot.pause()

            assert app.screen.__class__.__name__ != "ContextModal"

    @pytest.mark.asyncio
    async def test_modal_has_select_button(
        self, mock_sources: list[MockSourceForTest]
    ) -> None:
        """Test that the modal has a select button."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(ContextModal(mock_sources))  # type: ignore[arg-type]
            await pilot.pause()

            buttons = app.screen.query("Button")
            select_button = any("Select" in str(b.label) for b in buttons)
            assert select_button

    @pytest.mark.asyncio
    async def test_modal_has_cancel_button(
        self, mock_sources: list[MockSourceForTest]
    ) -> None:
        """Test that the modal has a cancel button."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(ContextModal(mock_sources))  # type: ignore[arg-type]
            await pilot.pause()

            buttons = app.screen.query("Button")
            cancel_button = any("Cancel" in str(b.label) for b in buttons)
            assert cancel_button

    @pytest.mark.asyncio
    async def test_modal_stores_sources(
        self, mock_sources: list[MockSourceForTest]
    ) -> None:
        """Test that the modal stores the sources correctly."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            modal = ContextModal(mock_sources)  # type: ignore[arg-type]
            app.push_screen(modal)
            await pilot.pause()

            assert modal._sources == mock_sources
            assert len(modal._sources) == 3

    @pytest.mark.asyncio
    async def test_modal_highlights_active_source(
        self, mock_sources: list[MockSourceForTest]
    ) -> None:
        """Test that the active source is highlighted."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            modal = ContextModal(
                mock_sources,  # type: ignore[arg-type]
                active_source_name="Syslog (/var/log/syslog)",
            )
            app.push_screen(modal)
            await pilot.pause()

            from textual.widgets import OptionList

            option_list = app.screen.query_one(OptionList)
            # The active source should be highlighted (index 1)
            assert option_list.highlighted == 1


class TestContextModalSelection:
    """Tests for context selection behavior."""

    @pytest.mark.asyncio
    async def test_modal_returns_none_on_cancel(
        self, mock_sources: list[MockSourceForTest]
    ) -> None:
        """Test that cancelling returns None."""
        app = LogViewApp()
        result = None

        def capture_result(value: str | None) -> None:
            nonlocal result
            result = value

        async with app.run_test() as pilot:
            app.push_screen(ContextModal(mock_sources), capture_result)  # type: ignore[arg-type]
            await pilot.pause()

            await pilot.press("escape")
            await pilot.pause()

        assert result is None


class TestContextModalEmpty:
    """Tests for context modal with edge cases."""

    @pytest.mark.asyncio
    async def test_modal_handles_empty_sources(self) -> None:
        """Test that the modal handles empty source list."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(ContextModal([]))
            await pilot.pause()

            # Should not crash
            assert app.screen.__class__.__name__ == "ContextModal"

            from textual.widgets import OptionList

            option_list = app.screen.query_one(OptionList)
            assert option_list.option_count == 0

    @pytest.mark.asyncio
    async def test_modal_handles_no_active_source(
        self, mock_sources: list[MockSourceForTest]
    ) -> None:
        """Test that the modal handles no active source."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            modal = ContextModal(mock_sources, active_source_name=None)  # type: ignore[arg-type]
            app.push_screen(modal)
            await pilot.pause()

            # Should not crash
            assert app.screen.__class__.__name__ == "ContextModal"
