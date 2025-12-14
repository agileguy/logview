"""Tests for the plain text parser."""

from __future__ import annotations

from datetime import datetime

from logview.adapters.plaintext_parser import parse_plain_line


class TestParsePlainLine:
    """Tests for parse_plain_line function."""

    def test_parses_simple_line(self) -> None:
        """Test parsing a simple text line."""
        line = "This is a log message"
        result = parse_plain_line(line)

        assert result.message == "This is a log message"
        assert result.severity == "INFO"
        assert result.raw == line

    def test_uses_provided_timestamp(self) -> None:
        """Test that provided timestamp is used."""
        timestamp = datetime(2025, 1, 15, 10, 30, 0)
        result = parse_plain_line("test message", default_timestamp=timestamp)

        assert result.timestamp == timestamp

    def test_uses_current_time_when_no_timestamp(self) -> None:
        """Test that current time is used when no timestamp provided."""
        before = datetime.now()
        result = parse_plain_line("test message")
        after = datetime.now()

        assert before <= result.timestamp <= after

    def test_detects_error_severity(self) -> None:
        """Test detection of ERROR severity."""
        test_cases = [
            "ERROR: Something went wrong",
            "An error occurred",
            "ERR connection failed",
            "FAILURE in processing",
            "Request failed with error",
        ]
        for line in test_cases:
            result = parse_plain_line(line)
            assert result.severity == "ERROR", f"Failed for: {line}"

    def test_detects_warning_severity(self) -> None:
        """Test detection of WARN severity."""
        test_cases = [
            "WARNING: Disk space low",
            "WARN: Connection timeout",
            "A warning was issued",
        ]
        for line in test_cases:
            result = parse_plain_line(line)
            assert result.severity == "WARN", f"Failed for: {line}"

    def test_detects_critical_severity(self) -> None:
        """Test detection of CRITICAL severity."""
        test_cases = [
            "CRITICAL: System failure",
            "CRIT: Out of memory",
            "FATAL: Cannot continue",
            "PANIC: Kernel panic",
        ]
        for line in test_cases:
            result = parse_plain_line(line)
            assert result.severity == "CRITICAL", f"Failed for: {line}"

    def test_detects_debug_severity(self) -> None:
        """Test detection of DEBUG severity."""
        test_cases = [
            "DEBUG: Variable value is 42",
            "TRACE: Entering function",
        ]
        for line in test_cases:
            result = parse_plain_line(line)
            assert result.severity == "DEBUG", f"Failed for: {line}"

    def test_defaults_to_info_severity(self) -> None:
        """Test that INFO is the default severity."""
        result = parse_plain_line("Just a normal log message")
        assert result.severity == "INFO"

    def test_severity_detection_is_case_insensitive(self) -> None:
        """Test that severity detection is case insensitive."""
        assert parse_plain_line("error happened").severity == "ERROR"
        assert parse_plain_line("Error happened").severity == "ERROR"
        assert parse_plain_line("ERROR happened").severity == "ERROR"

    def test_removes_ansi_escape_sequences(self) -> None:
        """Test that ANSI escape sequences are removed."""
        line = "\x1b[31mRed text\x1b[0m"
        result = parse_plain_line(line)

        assert result.message == "Red text"

    def test_removes_control_characters(self) -> None:
        """Test that control characters are removed."""
        line = "Hello\x00World\x07Test"
        result = parse_plain_line(line)

        assert result.message == "HelloWorldTest"

    def test_preserves_tabs_and_newlines(self) -> None:
        """Test that tabs are preserved."""
        line = "Column1\tColumn2"
        result = parse_plain_line(line)

        assert result.message == "Column1\tColumn2"

    def test_strips_trailing_newline(self) -> None:
        """Test that trailing newlines are stripped."""
        line = "Log message\n"
        result = parse_plain_line(line)

        assert result.message == "Log message"

    def test_strips_trailing_carriage_return(self) -> None:
        """Test that trailing carriage returns are stripped."""
        line = "Log message\r\n"
        result = parse_plain_line(line)

        assert result.message == "Log message"

    def test_preserves_raw_line(self) -> None:
        """Test that raw line is preserved (trailing whitespace stripped)."""
        line = "Original message\n"
        result = parse_plain_line(line)

        assert result.raw == "Original message"
