"""Integration tests for the LogFile adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from logview.adapters.logfile import (
    SYSLOG_AVAILABLE,
    LogFileNotFoundError,
    LogFileSecurityError,
    LogFileSource,
    detect_format,
)
from logview.domain.models import Filter

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


class TestDetectFormat:
    """Tests for format auto-detection."""

    def test_detects_jsonl_format(self) -> None:
        """Test detection of JSON Lines format."""
        path = FIXTURES_DIR / "sample_jsonl.log"
        assert detect_format(path) == "jsonl"

    @pytest.mark.skipif(not SYSLOG_AVAILABLE, reason="syslog parser not available")
    def test_detects_syslog_format(self) -> None:
        """Test detection of syslog format."""
        path = FIXTURES_DIR / "sample_syslog.txt"
        assert detect_format(path) == "syslog"

    def test_detects_plain_format(self) -> None:
        """Test detection of plain text format."""
        path = FIXTURES_DIR / "sample_plain.log"
        assert detect_format(path) == "plain"

    def test_returns_plain_for_nonexistent_file(self) -> None:
        """Test that nonexistent files default to plain."""
        path = FIXTURES_DIR / "nonexistent.log"
        assert detect_format(path) == "plain"


class TestLogFileSource:
    """Tests for LogFileSource class."""

    def test_creates_source_with_valid_path(self, tmp_path: Path) -> None:
        """Test creating a source with a valid path."""
        log_file = tmp_path / "test.log"
        log_file.write_text("test log line\n")

        source = LogFileSource(
            name="test",
            path=str(log_file),
            allowed_directories=[str(tmp_path)],
        )

        assert source.name == "test"
        assert source.path == log_file

    def test_auto_detects_format(self, tmp_path: Path) -> None:
        """Test that format is auto-detected."""
        log_file = tmp_path / "test.log"
        log_file.write_text('{"message": "test"}\n')

        source = LogFileSource(
            name="test",
            path=str(log_file),
            format="auto",
            allowed_directories=[str(tmp_path)],
        )

        assert source.format == "jsonl"

    def test_respects_explicit_format(self, tmp_path: Path) -> None:
        """Test that explicit format is respected."""
        log_file = tmp_path / "test.log"
        log_file.write_text('{"message": "test"}\n')

        source = LogFileSource(
            name="test",
            path=str(log_file),
            format="plain",
            allowed_directories=[str(tmp_path)],
        )

        assert source.format == "plain"

    def test_raises_on_nonexistent_file(self, tmp_path: Path) -> None:
        """Test that nonexistent files raise an error."""
        with pytest.raises(LogFileNotFoundError):
            LogFileSource(
                name="test",
                path=str(tmp_path / "nonexistent.log"),
                allowed_directories=[str(tmp_path)],
            )

    def test_raises_on_directory_path(self, tmp_path: Path) -> None:
        """Test that directory paths raise an error."""
        with pytest.raises(LogFileNotFoundError):
            LogFileSource(
                name="test",
                path=str(tmp_path),
                allowed_directories=[str(tmp_path)],
            )

    def test_raises_on_disallowed_path(self, tmp_path: Path) -> None:
        """Test that paths outside allowed directories raise an error."""
        log_file = tmp_path / "test.log"
        log_file.write_text("test\n")

        with pytest.raises(LogFileSecurityError):
            LogFileSource(
                name="test",
                path=str(log_file),
                allowed_directories=["/some/other/path"],
            )

    def test_expands_home_directory(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that ~ is expanded to home directory."""
        # Create a log file in a simulated home directory
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        log_file = fake_home / "test.log"
        log_file.write_text("test\n")

        monkeypatch.setenv("HOME", str(fake_home))

        source = LogFileSource(
            name="test",
            path="~/test.log",
            allowed_directories=[str(fake_home)],
        )

        assert source.path == log_file


class TestLogFileSourceFetch:
    """Tests for LogFileSource.fetch method."""

    @pytest.mark.asyncio
    async def test_fetches_jsonl_entries(self) -> None:
        """Test fetching entries from a JSON Lines file."""
        source = LogFileSource(
            name="test",
            path=str(FIXTURES_DIR / "sample_jsonl.log"),
            format="jsonl",
            allowed_directories=[str(FIXTURES_DIR)],
        )

        entries = [entry async for entry in source.fetch(Filter())]

        assert len(entries) == 5
        # Check entries are sorted by timestamp (newest first)
        assert entries[0].message == "Failed to send email"
        assert entries[0].severity.value == "ERROR"

    @pytest.mark.asyncio
    async def test_fetches_plain_entries(self) -> None:
        """Test fetching entries from a plain text file."""
        source = LogFileSource(
            name="test",
            path=str(FIXTURES_DIR / "sample_plain.log"),
            format="plain",
            allowed_directories=[str(FIXTURES_DIR)],
        )

        entries = [entry async for entry in source.fetch(Filter())]

        assert len(entries) == 10
        # Check severity detection
        severities = {e.message: e.severity.value for e in entries}
        assert severities["ERROR: Database connection lost"] == "ERROR"
        assert severities["WARNING: Request took longer than expected (2.5s)"] == "WARN"
        assert severities["CRITICAL: Out of disk space"] == "CRITICAL"

    @pytest.mark.asyncio
    @pytest.mark.skipif(not SYSLOG_AVAILABLE, reason="syslog parser not available")
    async def test_fetches_syslog_entries(self) -> None:
        """Test fetching entries from a syslog file."""
        source = LogFileSource(
            name="test",
            path=str(FIXTURES_DIR / "sample_syslog.txt"),
            format="syslog",
            allowed_directories=[str(FIXTURES_DIR)],
        )

        entries = [entry async for entry in source.fetch(Filter())]

        assert len(entries) > 0
        # Check that metadata contains syslog fields
        assert "hostname" in entries[0].metadata or "program" in entries[0].metadata

    @pytest.mark.asyncio
    async def test_respects_limit(self) -> None:
        """Test that fetch respects the limit filter."""
        source = LogFileSource(
            name="test",
            path=str(FIXTURES_DIR / "sample_jsonl.log"),
            format="jsonl",
            allowed_directories=[str(FIXTURES_DIR)],
        )

        entries = [entry async for entry in source.fetch(Filter(limit=2))]

        assert len(entries) == 2

    @pytest.mark.asyncio
    async def test_applies_text_search_filter(self) -> None:
        """Test that text search filter is applied."""
        source = LogFileSource(
            name="test",
            path=str(FIXTURES_DIR / "sample_jsonl.log"),
            format="jsonl",
            allowed_directories=[str(FIXTURES_DIR)],
        )

        filter = Filter(text_search="email")
        entries = [entry async for entry in source.fetch(filter)]

        assert len(entries) == 1
        assert "email" in entries[0].message.lower()

    @pytest.mark.asyncio
    async def test_skips_empty_lines(self, tmp_path: Path) -> None:
        """Test that empty lines are skipped."""
        log_file = tmp_path / "test.log"
        log_file.write_text("line 1\n\n\nline 2\n")

        source = LogFileSource(
            name="test",
            path=str(log_file),
            format="plain",
            allowed_directories=[str(tmp_path)],
        )

        entries = [entry async for entry in source.fetch(Filter())]

        assert len(entries) == 2


class TestLogFileSourceValidation:
    """Tests for LogFileSource.validate_filter method."""

    def test_validates_valid_filter(self, tmp_path: Path) -> None:
        """Test that valid filters pass validation."""
        log_file = tmp_path / "test.log"
        log_file.write_text("test\n")

        source = LogFileSource(
            name="test",
            path=str(log_file),
            allowed_directories=[str(tmp_path)],
        )

        errors = source.validate_filter(Filter())
        assert errors == []

    def test_filter_rejects_limit_below_one(self) -> None:
        """Test that Filter rejects limit below 1 at construction."""
        with pytest.raises(ValueError, match="limit must be at least 1"):
            Filter(limit=0)

    def test_filter_rejects_excessive_limit(self) -> None:
        """Test that Filter rejects excessive limit at construction."""
        with pytest.raises(ValueError, match="limit must not exceed"):
            Filter(limit=200000)


class TestLogFileSourceFilters:
    """Tests for LogFileSource.available_filters method."""

    def test_returns_expected_filters(self, tmp_path: Path) -> None:
        """Test that expected filter fields are returned."""
        log_file = tmp_path / "test.log"
        log_file.write_text("test\n")

        source = LogFileSource(
            name="test",
            path=str(log_file),
            allowed_directories=[str(tmp_path)],
        )

        filters = source.available_filters()
        filter_names = [f.name for f in filters]

        assert "time_range" in filter_names
        assert "severity" in filter_names
        assert "text_search" in filter_names
