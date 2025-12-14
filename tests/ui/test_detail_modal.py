"""Tests for the log detail modal."""

from __future__ import annotations

from datetime import datetime

import pytest

from logview.app import LogViewApp
from logview.domain.models import LogEntry, Severity
from logview.ui.screens.detail import DetailModal


@pytest.fixture
def sample_entry() -> LogEntry:
    """Create a sample log entry for testing."""
    return LogEntry(
        timestamp=datetime(2024, 1, 15, 10, 23, 45),
        severity=Severity.ERROR,
        message="Database connection failed: timeout after 30s",
        source="db-proxy",
        metadata={
            "hostname": "server01",
            "pid": "1234",
            "cluster": "production",
        },
        raw="Jan 15 10:23:45 server01 db-proxy[1234]: ERROR: Database connection failed",
    )


class TestDetailModal:
    """Tests for DetailModal."""

    @pytest.mark.asyncio
    async def test_modal_opens(self, sample_entry: LogEntry) -> None:
        """Test that the detail modal opens correctly."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            # Push the detail modal
            app.push_screen(DetailModal(sample_entry))
            await pilot.pause()

            # Modal should be displayed
            assert app.screen.__class__.__name__ == "DetailModal"

    @pytest.mark.asyncio
    async def test_modal_has_labels(self, sample_entry: LogEntry) -> None:
        """Test that the modal has expected labels."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(DetailModal(sample_entry))
            await pilot.pause()

            # Check that labels are present
            labels = app.screen.query("Label")
            assert len(list(labels)) > 0

    @pytest.mark.asyncio
    async def test_modal_has_static_widgets(self, sample_entry: LogEntry) -> None:
        """Test that the modal has Static widgets for content."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(DetailModal(sample_entry))
            await pilot.pause()

            # Check that Static widgets are present for displaying content
            statics = app.screen.query("Static")
            assert len(list(statics)) > 0

    @pytest.mark.asyncio
    async def test_modal_has_scrollable_container(self, sample_entry: LogEntry) -> None:
        """Test that the modal has a scrollable container."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(DetailModal(sample_entry))
            await pilot.pause()

            # Check for scrollable container
            containers = app.screen.query("ScrollableContainer")
            assert len(list(containers)) > 0

    @pytest.mark.asyncio
    async def test_modal_stores_entry(self, sample_entry: LogEntry) -> None:
        """Test that the modal stores the log entry correctly."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            modal = DetailModal(sample_entry)
            app.push_screen(modal)
            await pilot.pause()

            # Check that the entry is stored
            assert modal._entry == sample_entry
            assert modal._entry.message == "Database connection failed: timeout after 30s"
            assert modal._entry.severity == Severity.ERROR

    @pytest.mark.asyncio
    async def test_modal_closes_on_escape(self, sample_entry: LogEntry) -> None:
        """Test that pressing Escape closes the modal."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(DetailModal(sample_entry))
            await pilot.pause()

            # Verify modal is open
            assert app.screen.__class__.__name__ == "DetailModal"

            # Press escape
            await pilot.press("escape")
            await pilot.pause()

            # Modal should be closed, back to main screen
            assert app.screen.__class__.__name__ != "DetailModal"

    @pytest.mark.asyncio
    async def test_modal_has_copy_button(self, sample_entry: LogEntry) -> None:
        """Test that the modal has a copy button."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(DetailModal(sample_entry))
            await pilot.pause()

            # Check for copy button
            buttons = app.screen.query("Button")
            copy_button = any("Copy" in str(b.label) for b in buttons)
            assert copy_button

    @pytest.mark.asyncio
    async def test_modal_has_close_button(self, sample_entry: LogEntry) -> None:
        """Test that the modal has a close button."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(DetailModal(sample_entry))
            await pilot.pause()

            # Check for close button
            buttons = app.screen.query("Button")
            close_button = any("Close" in str(b.label) for b in buttons)
            assert close_button


class TestDetailModalWithoutOptionalFields:
    """Tests for DetailModal with minimal log entry."""

    @pytest.fixture
    def minimal_entry(self) -> LogEntry:
        """Create a minimal log entry without optional fields."""
        return LogEntry(
            timestamp=datetime(2024, 1, 15, 10, 23, 45),
            severity=Severity.INFO,
            message="Simple log message",
            source="app",
            metadata={},
            raw="",
        )

    @pytest.mark.asyncio
    async def test_modal_handles_empty_metadata(self, minimal_entry: LogEntry) -> None:
        """Test that the modal handles empty metadata gracefully."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(DetailModal(minimal_entry))
            await pilot.pause()

            # Should not crash, modal should be displayed
            assert app.screen.__class__.__name__ == "DetailModal"

    @pytest.mark.asyncio
    async def test_modal_handles_empty_raw(self, minimal_entry: LogEntry) -> None:
        """Test that the modal handles empty raw field gracefully."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(DetailModal(minimal_entry))
            await pilot.pause()

            # Should not crash, modal should be displayed
            assert app.screen.__class__.__name__ == "DetailModal"
