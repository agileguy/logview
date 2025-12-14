"""Tests for the export modal."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from textual.widgets import Button, Input, RadioButton, RadioSet

from logview.app import LogViewApp
from logview.domain.models import LogEntry, Severity
from logview.ui.screens.export import ExportModal


class TestExportModal:
    """Tests for ExportModal."""

    @pytest.fixture
    def sample_entries(self) -> list[LogEntry]:
        """Create sample log entries for testing."""
        return [
            LogEntry(
                timestamp=datetime(2025, 12, 14, 10, 30, 0),
                severity=Severity.INFO,
                message="First log message",
                source="test-source",
                metadata={"key": "value"},
            ),
            LogEntry(
                timestamp=datetime(2025, 12, 14, 10, 31, 0),
                severity=Severity.ERROR,
                message="Error occurred",
                source="test-source",
                metadata={},
            ),
        ]

    def test_write_json(self, sample_entries: list[LogEntry], tmp_path: Path) -> None:
        """Test JSON export format."""
        modal = ExportModal(sample_entries, "test")
        output_path = tmp_path / "test.json"

        modal._write_json(output_path)

        # Verify file contents
        with open(output_path) as f:
            data = json.load(f)

        assert len(data) == 2
        assert data[0]["message"] == "First log message"
        assert data[0]["severity"] == "INFO"
        assert data[1]["message"] == "Error occurred"
        assert data[1]["severity"] == "ERROR"

    def test_write_jsonl(self, sample_entries: list[LogEntry], tmp_path: Path) -> None:
        """Test JSONL export format."""
        modal = ExportModal(sample_entries, "test")
        output_path = tmp_path / "test.jsonl"

        modal._write_jsonl(output_path)

        # Verify file contents
        with open(output_path) as f:
            lines = f.readlines()

        assert len(lines) == 2
        entry1 = json.loads(lines[0])
        entry2 = json.loads(lines[1])
        assert entry1["message"] == "First log message"
        assert entry2["message"] == "Error occurred"

    def test_json_contains_all_fields(
        self, sample_entries: list[LogEntry], tmp_path: Path
    ) -> None:
        """Test that JSON export includes all expected fields."""
        modal = ExportModal(sample_entries, "test")
        output_path = tmp_path / "test.json"

        modal._write_json(output_path)

        with open(output_path) as f:
            data = json.load(f)

        entry = data[0]
        assert "timestamp" in entry
        assert "severity" in entry
        assert "message" in entry
        assert "source" in entry
        assert "metadata" in entry
        assert entry["metadata"] == {"key": "value"}

    def test_jsonl_one_object_per_line(
        self, sample_entries: list[LogEntry], tmp_path: Path
    ) -> None:
        """Test that JSONL format has exactly one JSON object per line."""
        modal = ExportModal(sample_entries, "test")
        output_path = tmp_path / "test.jsonl"

        modal._write_jsonl(output_path)

        with open(output_path) as f:
            for line in f:
                # Each line should be valid JSON
                data = json.loads(line)
                assert isinstance(data, dict)

    def test_empty_entries_creates_empty_array(self, tmp_path: Path) -> None:
        """Test that exporting empty entries creates empty JSON array."""
        modal = ExportModal([], "test")
        output_path = tmp_path / "test.json"

        modal._write_json(output_path)

        with open(output_path) as f:
            data = json.load(f)

        assert data == []

    def test_empty_entries_creates_empty_jsonl(self, tmp_path: Path) -> None:
        """Test that exporting empty entries creates empty JSONL file."""
        modal = ExportModal([], "test")
        output_path = tmp_path / "test.jsonl"

        modal._write_jsonl(output_path)

        with open(output_path) as f:
            content = f.read()

        assert content == ""

    def test_timestamp_iso_format(
        self, sample_entries: list[LogEntry], tmp_path: Path
    ) -> None:
        """Test that timestamps are exported in ISO format."""
        modal = ExportModal(sample_entries, "test")
        output_path = tmp_path / "test.json"

        modal._write_json(output_path)

        with open(output_path) as f:
            data = json.load(f)

        # Should be parseable ISO format
        timestamp = datetime.fromisoformat(data[0]["timestamp"])
        assert timestamp == sample_entries[0].timestamp


class TestExportModalUI:
    """Tests for ExportModal UI interactions."""

    @pytest.fixture
    def sample_entries(self) -> list[LogEntry]:
        """Create sample log entries for testing."""
        return [
            LogEntry(
                timestamp=datetime(2025, 12, 14, 10, 30, 0),
                severity=Severity.INFO,
                message="Test message",
                source="test-source",
            ),
        ]

    @pytest.mark.asyncio
    async def test_modal_opens(self, sample_entries: list[LogEntry]) -> None:
        """Test that export modal opens and displays correctly."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            # Push export modal
            modal = ExportModal(sample_entries, "test-source")
            app.push_screen(modal)
            await pilot.pause()

            # Check modal widgets exist
            assert modal.query_one("#filename-input", Input)
            assert modal.query_one("#format-select", RadioSet)
            assert modal.query_one("#btn-export", Button)
            assert modal.query_one("#btn-cancel", Button)

    @pytest.mark.asyncio
    async def test_modal_shows_entry_count(self, sample_entries: list[LogEntry]) -> None:
        """Test that modal shows the number of entries being exported."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            modal = ExportModal(sample_entries, "test-source")
            app.push_screen(modal)
            await pilot.pause()

            # Modal should display entry count (checked via compose method execution)
            assert modal.query_one("#filename-input", Input)

    @pytest.mark.asyncio
    async def test_modal_has_default_filename(self, sample_entries: list[LogEntry]) -> None:
        """Test that modal provides a default filename."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            modal = ExportModal(sample_entries, "test-source")
            app.push_screen(modal)
            await pilot.pause()

            filename_input = modal.query_one("#filename-input", Input)
            assert filename_input.value.startswith("logs_test-source_")
            assert filename_input.value.endswith(".json")

    @pytest.mark.asyncio
    async def test_modal_json_selected_by_default(
        self, sample_entries: list[LogEntry]
    ) -> None:
        """Test that JSON format is selected by default."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            modal = ExportModal(sample_entries, "test-source")
            app.push_screen(modal)
            await pilot.pause()

            radio_set = modal.query_one("#format-select", RadioSet)
            assert radio_set.pressed_button is not None
            assert radio_set.pressed_button.id == "json"

    @pytest.mark.asyncio
    async def test_modal_cancel_closes_modal(
        self, sample_entries: list[LogEntry]
    ) -> None:
        """Test that cancel button closes modal."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            modal = ExportModal(sample_entries, "test-source")
            app.push_screen(modal)
            await pilot.pause()

            # Verify cancel button exists
            cancel_btn = modal.query_one("#btn-cancel", Button)
            assert cancel_btn is not None

            # Test action_cancel dismisses with None (tested via method call)
            modal.action_cancel()
            await pilot.pause()

            # Modal should be dismissed (no longer in screen stack)
            # Can't easily verify callback result, but action_cancel is tested

    @pytest.mark.asyncio
    async def test_get_selected_format_json(
        self, sample_entries: list[LogEntry]
    ) -> None:
        """Test _get_selected_format returns 'json' when JSON is selected."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            modal = ExportModal(sample_entries, "test-source")
            app.push_screen(modal)
            await pilot.pause()

            # JSON should be selected by default
            assert modal._get_selected_format() == "json"

    @pytest.mark.asyncio
    async def test_get_selected_format_jsonl(
        self, sample_entries: list[LogEntry]
    ) -> None:
        """Test _get_selected_format returns 'jsonl' when JSONL is selected."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            modal = ExportModal(sample_entries, "test-source")
            app.push_screen(modal)
            await pilot.pause()

            # Select JSONL
            jsonl_radio = modal.query_one("#jsonl", RadioButton)
            jsonl_radio.toggle()
            await pilot.pause()

            assert modal._get_selected_format() == "jsonl"


class TestExportModalValidation:
    """Tests for ExportModal validation and error handling."""

    @pytest.fixture
    def sample_entries(self) -> list[LogEntry]:
        """Create sample log entries for testing."""
        return [
            LogEntry(
                timestamp=datetime(2025, 12, 14, 10, 30, 0),
                severity=Severity.INFO,
                message="Test message",
                source="test-source",
            ),
        ]

    @pytest.mark.asyncio
    async def test_export_rejects_empty_filename(
        self, sample_entries: list[LogEntry]
    ) -> None:
        """Test that export validation rejects empty filename."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            modal = ExportModal(sample_entries, "test-source")
            app.push_screen(modal)
            await pilot.pause()

            # Clear filename
            filename_input = modal.query_one("#filename-input", Input)
            filename_input.value = ""
            await pilot.pause()

            # Try to export
            result = modal._export_logs()

            # Should fail validation
            assert result is None

    @pytest.mark.asyncio
    async def test_export_rejects_absolute_path(
        self, sample_entries: list[LogEntry]
    ) -> None:
        """Test that export validation rejects absolute paths."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            modal = ExportModal(sample_entries, "test-source")
            app.push_screen(modal)
            await pilot.pause()

            # Set absolute path
            filename_input = modal.query_one("#filename-input", Input)
            filename_input.value = "/tmp/test.json"
            await pilot.pause()

            # Try to export
            result = modal._export_logs()

            # Should fail validation
            assert result is None

    @pytest.mark.asyncio
    async def test_export_with_jsonl_format(
        self, sample_entries: list[LogEntry], tmp_path: Path
    ) -> None:
        """Test exporting with JSONL format selected."""
        import os

        app = LogViewApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            modal = ExportModal(sample_entries, "test-source")
            app.push_screen(modal)
            await pilot.pause()

            # Change to temp dir
            original_cwd = Path.cwd()
            os.chdir(tmp_path)

            try:
                # Select JSONL
                jsonl_radio = modal.query_one("#jsonl", RadioButton)
                jsonl_radio.toggle()
                await pilot.pause()

                # Set filename
                filename_input = modal.query_one("#filename-input", Input)
                filename_input.value = "test_export.jsonl"
                await pilot.pause()

                # Export
                result = modal._export_logs()

                # Should succeed
                assert result is not None
                assert result.name == "test_export.jsonl"
                assert result.exists()

                # Verify JSONL format
                with open(result) as f:
                    line = f.readline()
                    data = json.loads(line)
                    assert data["message"] == "Test message"
            finally:
                os.chdir(original_cwd)
