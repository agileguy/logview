"""Integration tests for syslog adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from logview.adapters.syslog import (
    SyslogError,
    SyslogFileNotFoundError,
    SyslogLogSource,
)
from logview.domain.models import Filter, Severity


@pytest.fixture
def fixtures_dir() -> Path:
    """Get the fixtures directory."""
    return Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def sample_syslog(fixtures_dir: Path) -> Path:
    """Get the sample syslog file path."""
    return fixtures_dir / "sample_syslog.txt"


@pytest.fixture
def malformed_syslog(fixtures_dir: Path) -> Path:
    """Get the malformed syslog file path."""
    return fixtures_dir / "malformed_syslog.txt"


@pytest.fixture
def empty_syslog(fixtures_dir: Path) -> Path:
    """Get the empty syslog file path."""
    return fixtures_dir / "empty_syslog.txt"


class TestSyslogLogSource:
    """Integration tests for SyslogLogSource."""

    def test_name_property(self, sample_syslog: Path, fixtures_dir: Path) -> None:
        """Test the name property."""
        source = SyslogLogSource(
            file_path=sample_syslog,
            allowed_directories=[fixtures_dir],
        )
        assert "Syslog" in source.name
        assert "sample_syslog.txt" in source.name

    def test_available_filters(self, sample_syslog: Path, fixtures_dir: Path) -> None:
        """Test available filters are returned."""
        source = SyslogLogSource(
            file_path=sample_syslog,
            allowed_directories=[fixtures_dir],
        )
        filters = source.available_filters()
        assert len(filters) > 0

        filter_names = [f.name for f in filters]
        assert "severity" in filter_names
        assert "hostname" in filter_names
        assert "program" in filter_names

    @pytest.mark.asyncio
    async def test_fetch_returns_entries(
        self, sample_syslog: Path, fixtures_dir: Path
    ) -> None:
        """Test that fetch returns log entries from sample file."""
        source = SyslogLogSource(
            file_path=sample_syslog,
            year=2024,
            allowed_directories=[fixtures_dir],
        )
        log_filter = Filter(limit=100)
        entries = []

        async for entry in source.fetch(log_filter):
            entries.append(entry)

        # Sample file has 15 valid lines
        assert len(entries) == 15

        # Verify entry contents
        for entry in entries:
            assert entry.timestamp is not None
            assert entry.severity is not None
            assert entry.message is not None
            assert entry.source is not None
            assert "hostname" in entry.metadata
            assert "program" in entry.metadata

    @pytest.mark.asyncio
    async def test_fetch_respects_limit(
        self, sample_syslog: Path, fixtures_dir: Path
    ) -> None:
        """Test that fetch respects the limit parameter."""
        source = SyslogLogSource(
            file_path=sample_syslog,
            year=2024,
            allowed_directories=[fixtures_dir],
        )

        log_filter = Filter(limit=5)
        entries = [e async for e in source.fetch(log_filter)]

        assert len(entries) == 5

    @pytest.mark.asyncio
    async def test_fetch_severity_filter(
        self, sample_syslog: Path, fixtures_dir: Path
    ) -> None:
        """Test filtering by severity."""
        source = SyslogLogSource(
            file_path=sample_syslog,
            year=2024,
            allowed_directories=[fixtures_dir],
        )
        log_filter = Filter(severity=Severity.ERROR, limit=100)

        entries = [e async for e in source.fetch(log_filter)]

        # Should only get ERROR and CRITICAL entries
        for entry in entries:
            assert entry.severity >= Severity.ERROR

    @pytest.mark.asyncio
    async def test_fetch_text_search_filter(
        self, sample_syslog: Path, fixtures_dir: Path
    ) -> None:
        """Test filtering by text search."""
        source = SyslogLogSource(
            file_path=sample_syslog,
            year=2024,
            allowed_directories=[fixtures_dir],
        )
        log_filter = Filter(text_search="connection", limit=100)

        entries = [e async for e in source.fetch(log_filter)]

        # All entries should contain "connection" (case-insensitive)
        for entry in entries:
            assert "connection" in entry.message.lower()

    @pytest.mark.asyncio
    async def test_fetch_handles_malformed_lines(
        self, malformed_syslog: Path, fixtures_dir: Path
    ) -> None:
        """Test that malformed lines are skipped gracefully."""
        source = SyslogLogSource(
            file_path=malformed_syslog,
            year=2024,
            allowed_directories=[fixtures_dir],
        )
        log_filter = Filter(limit=100)

        entries = [e async for e in source.fetch(log_filter)]

        # Should have parsed at least some valid entries
        assert len(entries) > 0
        # But not all lines (some are malformed)
        assert len(entries) < 6  # Total lines including blanks is 7

    @pytest.mark.asyncio
    async def test_fetch_empty_file(
        self, empty_syslog: Path, fixtures_dir: Path
    ) -> None:
        """Test that empty file returns no entries."""
        source = SyslogLogSource(
            file_path=empty_syslog,
            year=2024,
            allowed_directories=[fixtures_dir],
        )
        log_filter = Filter(limit=100)

        entries = [e async for e in source.fetch(log_filter)]

        assert len(entries) == 0


class TestSyslogLogSourceSecurity:
    """Security-focused tests for SyslogLogSource."""

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self) -> None:
        """Test that path traversal attempts are blocked."""
        # Attempting to access /etc/passwd via path traversal
        source = SyslogLogSource(
            file_path="/var/log/../etc/passwd",
            allowed_directories=[Path("/var/log")],
        )
        log_filter = Filter(limit=10)

        with pytest.raises(SyslogError) as exc_info:
            async for _ in source.fetch(log_filter):
                pass

        # Should not reveal the actual path in error message
        assert "/etc/passwd" not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_disallowed_directory_blocked(self, fixtures_dir: Path) -> None:
        """Test that files outside allowed directories are blocked."""
        source = SyslogLogSource(
            file_path="/etc/passwd",
            allowed_directories=[fixtures_dir],
        )
        log_filter = Filter(limit=10)

        with pytest.raises(SyslogError, match="not in an allowed directory"):
            async for _ in source.fetch(log_filter):
                pass

    @pytest.mark.asyncio
    async def test_nonexistent_file_error(self, fixtures_dir: Path) -> None:
        """Test that nonexistent files raise appropriate error."""
        source = SyslogLogSource(
            file_path=fixtures_dir / "nonexistent.txt",
            allowed_directories=[fixtures_dir],
        )
        log_filter = Filter(limit=10)

        with pytest.raises(SyslogFileNotFoundError) as exc_info:
            async for _ in source.fetch(log_filter):
                pass

        # Error message should not reveal full path
        assert str(fixtures_dir) not in str(exc_info.value)

    def test_validate_filter_rejects_unsupported_fields(
        self, sample_syslog: Path, fixtures_dir: Path
    ) -> None:
        """Test that unsupported filter fields are rejected."""
        source = SyslogLogSource(
            file_path=sample_syslog,
            allowed_directories=[fixtures_dir],
        )
        log_filter = Filter(fields={"unsupported_field": "value"}, limit=10)

        errors = source.validate_filter(log_filter)

        assert len(errors) > 0
        assert "unsupported_field" in errors[0].lower()


class TestSyslogLogSourceMetadata:
    """Tests for metadata extraction in SyslogLogSource."""

    @pytest.mark.asyncio
    async def test_hostname_extracted(
        self, sample_syslog: Path, fixtures_dir: Path
    ) -> None:
        """Test that hostname is extracted to metadata."""
        source = SyslogLogSource(
            file_path=sample_syslog,
            year=2024,
            allowed_directories=[fixtures_dir],
        )
        log_filter = Filter(limit=1)

        entries = [e async for e in source.fetch(log_filter)]

        assert entries[0].metadata["hostname"] == "myhost"

    @pytest.mark.asyncio
    async def test_program_extracted(
        self, sample_syslog: Path, fixtures_dir: Path
    ) -> None:
        """Test that program name is extracted to source and metadata."""
        source = SyslogLogSource(
            file_path=sample_syslog,
            year=2024,
            allowed_directories=[fixtures_dir],
        )
        log_filter = Filter(limit=1)

        entries = [e async for e in source.fetch(log_filter)]

        assert entries[0].source == "sshd"
        assert entries[0].metadata["program"] == "sshd"

    @pytest.mark.asyncio
    async def test_pid_extracted_when_present(
        self, sample_syslog: Path, fixtures_dir: Path
    ) -> None:
        """Test that PID is extracted when present."""
        source = SyslogLogSource(
            file_path=sample_syslog,
            year=2024,
            allowed_directories=[fixtures_dir],
        )
        log_filter = Filter(limit=1)

        entries = [e async for e in source.fetch(log_filter)]

        assert entries[0].metadata.get("pid") == "1234"

    @pytest.mark.asyncio
    async def test_raw_line_preserved(
        self, sample_syslog: Path, fixtures_dir: Path
    ) -> None:
        """Test that raw log line is preserved."""
        source = SyslogLogSource(
            file_path=sample_syslog,
            year=2024,
            allowed_directories=[fixtures_dir],
        )
        log_filter = Filter(limit=1)

        entries = [e async for e in source.fetch(log_filter)]

        # Raw should contain original syslog line
        assert "Jan 15" in entries[0].raw
        assert "sshd" in entries[0].raw
