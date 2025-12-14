"""Tests for the export modal."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

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
