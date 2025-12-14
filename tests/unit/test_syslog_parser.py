"""Tests for the syslog line parser."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from logview.adapters.syslog_parser import (
    SyslogParseError,
    parse_syslog_line,
)


class TestParseSyslogLine:
    """Tests for parse_syslog_line function."""

    def test_parses_standard_line_with_pid(self) -> None:
        """Test parsing a standard syslog line with PID."""
        line = "Jan 15 10:23:45 myhost sshd[1234]: Accepted publickey for user"
        result = parse_syslog_line(line, year=2024)

        assert result.timestamp == datetime(2024, 1, 15, 10, 23, 45)
        assert result.hostname == "myhost"
        assert result.program == "sshd"
        assert result.pid == 1234
        assert result.message == "Accepted publickey for user"
        assert result.raw == line

    def test_parses_line_without_pid(self) -> None:
        """Test parsing a syslog line without PID brackets."""
        line = "Jan 15 10:23:45 myhost kernel: [UFW BLOCK] something"
        result = parse_syslog_line(line, year=2024)

        assert result.hostname == "myhost"
        assert result.program == "kernel"
        assert result.pid is None
        assert result.message == "[UFW BLOCK] something"

    def test_parses_single_digit_day(self) -> None:
        """Test parsing with single digit day."""
        line = "Jan  5 10:23:45 myhost sshd[1234]: test"
        result = parse_syslog_line(line, year=2024)

        assert result.timestamp.day == 5

    def test_detects_severity_error(self) -> None:
        """Test severity detection for ERROR."""
        line = "Jan 15 10:27:00 myhost app[1]: ERROR: Database connection failed"
        result = parse_syslog_line(line, year=2024)

        assert result.severity == "ERROR"

    def test_detects_severity_warning(self) -> None:
        """Test severity detection for WARNING."""
        line = "Jan 15 10:26:30 myhost app[1]: WARNING: High memory usage"
        result = parse_syslog_line(line, year=2024)

        assert result.severity == "WARN"

    def test_detects_severity_critical(self) -> None:
        """Test severity detection for CRITICAL."""
        line = "Jan 15 10:28:00 myhost app[1]: CRITICAL: Service unavailable"
        result = parse_syslog_line(line, year=2024)

        assert result.severity == "CRITICAL"

    def test_detects_severity_debug(self) -> None:
        """Test severity detection for DEBUG."""
        line = "Jan 15 10:27:30 myhost app[1]: DEBUG: Retrying connection"
        result = parse_syslog_line(line, year=2024)

        assert result.severity == "DEBUG"

    def test_defaults_to_info_severity(self) -> None:
        """Test default INFO severity when no keyword found."""
        line = "Jan 15 10:23:45 myhost sshd[1234]: User logged in"
        result = parse_syslog_line(line, year=2024)

        assert result.severity == "INFO"

    def test_uses_current_year_when_not_provided(self) -> None:
        """Test that current year is used when not specified."""
        line = "Jan 15 10:23:45 myhost sshd[1234]: test"
        result = parse_syslog_line(line)

        assert result.timestamp.year == datetime.now().year

    def test_raises_on_empty_line(self) -> None:
        """Test that empty lines raise SyslogParseError."""
        with pytest.raises(SyslogParseError) as exc_info:
            parse_syslog_line("")

        assert "empty line" in str(exc_info.value)

    def test_raises_on_whitespace_only(self) -> None:
        """Test that whitespace-only lines raise SyslogParseError."""
        with pytest.raises(SyslogParseError) as exc_info:
            parse_syslog_line("   \t\n  ")

        assert "empty line" in str(exc_info.value)

    def test_raises_on_invalid_format(self) -> None:
        """Test that lines not matching format raise SyslogParseError."""
        with pytest.raises(SyslogParseError) as exc_info:
            parse_syslog_line("This is not a syslog line")

        assert "does not match RFC 3164 or RFC 5424 format" in str(exc_info.value)

    def test_raises_on_invalid_month(self) -> None:
        """Test that invalid month raises SyslogParseError."""
        with pytest.raises(SyslogParseError) as exc_info:
            parse_syslog_line("Xyz 15 10:23:45 myhost prog[1]: msg")

        # With dual format support, invalid month falls through to "does not match"
        assert "does not match RFC 3164 or RFC 5424 format" in str(exc_info.value)

    def test_sanitizes_ansi_escape_sequences(self) -> None:
        """Test that ANSI escape sequences are removed from messages."""
        line = "Jan 15 10:23:45 myhost app[1]: \x1b[31mRed text\x1b[0m"
        result = parse_syslog_line(line, year=2024)

        assert "\x1b" not in result.message
        assert result.message == "Red text"

    def test_sanitizes_control_characters(self) -> None:
        """Test that control characters are removed from messages."""
        line = "Jan 15 10:23:45 myhost app[1]: text\x07with\x08bells"
        result = parse_syslog_line(line, year=2024)

        assert "\x07" not in result.message
        assert "\x08" not in result.message

    def test_preserves_tabs_and_newlines(self) -> None:
        """Test that tabs are preserved in messages."""
        line = "Jan 15 10:23:45 myhost app[1]: text\twith\ttabs"
        result = parse_syslog_line(line, year=2024)

        assert "\t" in result.message

    def test_parses_all_months(self) -> None:
        """Test parsing works for all months."""
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        for i, month in enumerate(months, start=1):
            line = f"{month} 15 10:23:45 myhost app[1]: test"
            result = parse_syslog_line(line, year=2024)
            assert result.timestamp.month == i

    def test_error_contains_original_line(self) -> None:
        """Test that SyslogParseError contains the original line."""
        bad_line = "not a syslog line"
        with pytest.raises(SyslogParseError) as exc_info:
            parse_syslog_line(bad_line)

        assert exc_info.value.line == bad_line


class TestRFC5424Format:
    """Tests for RFC 5424 / ISO 8601 timestamp format parsing."""

    def test_parses_rfc5424_with_pid(self) -> None:
        """Test parsing RFC 5424 format with PID (converts to local time)."""
        line = "2025-12-07T00:00:05.319366-07:00 boss rsyslogd[1045]: rsyslogd was HUPed"
        result = parse_syslog_line(line)

        # Timestamp is converted to local time - compute expected value
        from datetime import timedelta, timezone
        tz_minus7 = timezone(timedelta(hours=-7))
        original = datetime(2025, 12, 7, 0, 0, 5, 319366, tzinfo=tz_minus7)
        expected = original.astimezone().replace(tzinfo=None)
        assert result.timestamp == expected
        assert result.hostname == "boss"
        assert result.program == "rsyslogd"
        assert result.pid == 1045
        assert result.message == "rsyslogd was HUPed"

    def test_parses_rfc5424_without_pid(self) -> None:
        """Test parsing RFC 5424 format without PID."""
        line = "2025-12-07T10:30:00+00:00 myhost systemd: Started service"
        result = parse_syslog_line(line)

        assert result.hostname == "myhost"
        assert result.program == "systemd"
        assert result.pid is None
        assert result.message == "Started service"

    def test_parses_rfc5424_utc_z(self) -> None:
        """Test parsing RFC 5424 format with Z timezone (converts to local time)."""
        line = "2025-01-15T14:30:00Z server nginx[999]: Connection accepted"
        result = parse_syslog_line(line)

        # Z means UTC, convert to local time
        original = datetime(2025, 1, 15, 14, 30, 0, tzinfo=UTC)
        expected = original.astimezone().replace(tzinfo=None)
        assert result.timestamp == expected
        assert result.hostname == "server"
        assert result.program == "nginx"
        assert result.pid == 999

    def test_parses_rfc5424_without_microseconds(self) -> None:
        """Test parsing RFC 5424 format without microseconds (converts to local time)."""
        line = "2025-06-15T08:00:00+05:30 host app[1]: message"
        result = parse_syslog_line(line)

        # +05:30 means 5.5 hours ahead of UTC, convert to local time
        from datetime import timedelta, timezone
        tz_plus530 = timezone(timedelta(hours=5, minutes=30))
        original = datetime(2025, 6, 15, 8, 0, 0, tzinfo=tz_plus530)
        expected = original.astimezone().replace(tzinfo=None)
        assert result.timestamp == expected
        assert result.hostname == "host"

    def test_rfc5424_severity_detection(self) -> None:
        """Test severity detection in RFC 5424 messages."""
        error_line = "2025-01-01T00:00:00Z host app[1]: ERROR failed to connect"
        result = parse_syslog_line(error_line)
        assert result.severity == "ERROR"

        warn_line = "2025-01-01T00:00:00Z host app[1]: WARNING disk space low"
        result = parse_syslog_line(warn_line)
        assert result.severity == "WARN"

    def test_rfc5424_sanitizes_messages(self) -> None:
        """Test that RFC 5424 messages are sanitized."""
        line = "2025-01-01T00:00:00Z host app[1]: \x1b[31mRed\x1b[0m text"
        result = parse_syslog_line(line)

        assert "\x1b" not in result.message
        assert result.message == "Red text"


class TestParseSyslogFixtures:
    """Tests using fixture files."""

    @pytest.fixture
    def fixtures_dir(self) -> Path:
        """Get the fixtures directory."""
        return Path(__file__).parent.parent / "fixtures"

    def test_parses_sample_syslog_file(self, fixtures_dir: Path) -> None:
        """Test parsing all lines from sample syslog file."""
        sample_file = fixtures_dir / "sample_syslog.txt"
        lines = sample_file.read_text().strip().split("\n")

        parsed = []
        for line in lines:
            if line.strip():
                result = parse_syslog_line(line, year=2024)
                parsed.append(result)

        assert len(parsed) == 15  # 15 valid lines in sample

        # Verify some specific entries
        assert parsed[0].program == "sshd"
        assert parsed[0].pid == 1234

        # Check severity detection worked
        severities = {p.severity for p in parsed}
        assert "ERROR" in severities
        assert "WARN" in severities
        assert "CRITICAL" in severities

    def test_handles_malformed_lines_gracefully(self, fixtures_dir: Path) -> None:
        """Test that malformed lines raise appropriate errors."""
        malformed_file = fixtures_dir / "malformed_syslog.txt"
        lines = malformed_file.read_text().split("\n")

        valid_count = 0
        error_count = 0

        for line in lines:
            if not line.strip():
                continue
            try:
                parse_syslog_line(line, year=2024)
                valid_count += 1
            except SyslogParseError:
                error_count += 1

        # Should have some valid and some invalid
        assert valid_count > 0
        assert error_count > 0

    def test_empty_file_produces_no_results(self, fixtures_dir: Path) -> None:
        """Test parsing empty file."""
        empty_file = fixtures_dir / "empty_syslog.txt"
        content = empty_file.read_text()

        parsed = []
        for line in content.split("\n"):
            if line.strip():
                try:
                    parsed.append(parse_syslog_line(line, year=2024))
                except SyslogParseError:
                    pass

        assert len(parsed) == 0
