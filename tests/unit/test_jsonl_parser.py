"""Tests for the JSON Lines parser."""

from __future__ import annotations

from datetime import datetime

import pytest

from logview.adapters.jsonl_parser import (
    JsonlParseError,
    is_jsonl_format,
    parse_jsonl_line,
)


class TestParseJsonlLine:
    """Tests for parse_jsonl_line function."""

    def test_parses_basic_json_object(self) -> None:
        """Test parsing a basic JSON object."""
        line = '{"message": "Hello world"}'
        result = parse_jsonl_line(line)

        assert result.message == "Hello world"
        assert result.severity == "INFO"
        assert result.raw == line

    def test_extracts_timestamp_field(self) -> None:
        """Test extraction of timestamp field."""
        line = '{"timestamp": "2025-01-15T10:30:00", "message": "test"}'
        result = parse_jsonl_line(line)

        assert result.timestamp == datetime(2025, 1, 15, 10, 30, 0)

    def test_extracts_time_field(self) -> None:
        """Test extraction of 'time' field as timestamp."""
        line = '{"time": "2025-01-15T10:30:00", "message": "test"}'
        result = parse_jsonl_line(line)

        assert result.timestamp == datetime(2025, 1, 15, 10, 30, 0)

    def test_extracts_ts_field(self) -> None:
        """Test extraction of 'ts' field as timestamp."""
        line = '{"ts": "2025-01-15T10:30:00", "message": "test"}'
        result = parse_jsonl_line(line)

        assert result.timestamp == datetime(2025, 1, 15, 10, 30, 0)

    def test_parses_unix_timestamp_seconds(self) -> None:
        """Test parsing Unix timestamp in seconds."""
        # 2025-01-15 10:30:00 UTC
        line = '{"timestamp": 1736937000, "message": "test"}'
        result = parse_jsonl_line(line)

        # Should parse without error
        assert result.timestamp is not None

    def test_parses_unix_timestamp_milliseconds(self) -> None:
        """Test parsing Unix timestamp in milliseconds."""
        line = '{"timestamp": 1736937000000, "message": "test"}'
        result = parse_jsonl_line(line)

        assert result.timestamp is not None

    def test_extracts_severity_from_level(self) -> None:
        """Test extraction of severity from 'level' field."""
        line = '{"level": "error", "message": "test"}'
        result = parse_jsonl_line(line)

        assert result.severity == "ERROR"

    def test_extracts_severity_from_severity_field(self) -> None:
        """Test extraction of severity from 'severity' field."""
        line = '{"severity": "warn", "message": "test"}'
        result = parse_jsonl_line(line)

        assert result.severity == "WARN"

    def test_normalizes_severity_values(self) -> None:
        """Test that severity values are normalized correctly."""
        test_cases = [
            ("debug", "DEBUG"),
            ("trace", "DEBUG"),
            ("info", "INFO"),
            ("information", "INFO"),
            ("warn", "WARN"),
            ("warning", "WARN"),
            ("error", "ERROR"),
            ("err", "ERROR"),
            ("critical", "CRITICAL"),
            ("fatal", "CRITICAL"),
        ]
        for input_level, expected in test_cases:
            line = f'{{"level": "{input_level}", "message": "test"}}'
            result = parse_jsonl_line(line)
            assert result.severity == expected, f"Failed for {input_level}"

    def test_extracts_message_from_msg_field(self) -> None:
        """Test extraction of message from 'msg' field."""
        line = '{"msg": "Hello from msg"}'
        result = parse_jsonl_line(line)

        assert result.message == "Hello from msg"

    def test_extracts_message_from_text_field(self) -> None:
        """Test extraction of message from 'text' field."""
        line = '{"text": "Hello from text"}'
        result = parse_jsonl_line(line)

        assert result.message == "Hello from text"

    def test_uses_raw_json_when_no_message_field(self) -> None:
        """Test that raw JSON is used when no message field exists."""
        line = '{"foo": "bar", "baz": 123}'
        result = parse_jsonl_line(line)

        assert result.message == line

    def test_extracts_metadata_from_extra_fields(self) -> None:
        """Test that extra fields go into metadata."""
        line = '{"message": "test", "request_id": "abc123", "user_id": 42}'
        result = parse_jsonl_line(line)

        assert result.metadata["request_id"] == "abc123"
        assert result.metadata["user_id"] == 42

    def test_excludes_standard_fields_from_metadata(self) -> None:
        """Test that standard fields are not duplicated in metadata."""
        line = '{"message": "test", "level": "info", "timestamp": "2025-01-15T10:30:00"}'
        result = parse_jsonl_line(line)

        assert "message" not in result.metadata
        assert "level" not in result.metadata
        assert "timestamp" not in result.metadata

    def test_raises_on_empty_line(self) -> None:
        """Test that empty lines raise an error."""
        with pytest.raises(JsonlParseError, match="empty line"):
            parse_jsonl_line("")

    def test_raises_on_invalid_json(self) -> None:
        """Test that invalid JSON raises an error."""
        with pytest.raises(JsonlParseError, match="invalid JSON"):
            parse_jsonl_line("not json at all")

    def test_raises_on_json_array(self) -> None:
        """Test that JSON arrays raise an error."""
        with pytest.raises(JsonlParseError, match="must be an object"):
            parse_jsonl_line("[1, 2, 3]")

    def test_raises_on_json_string(self) -> None:
        """Test that JSON strings raise an error."""
        with pytest.raises(JsonlParseError, match="must be an object"):
            parse_jsonl_line('"just a string"')

    def test_handles_iso_timestamp_with_z_suffix(self) -> None:
        """Test handling of ISO timestamp with Z suffix."""
        line = '{"timestamp": "2025-01-15T10:30:00Z", "message": "test"}'
        result = parse_jsonl_line(line)

        # Should parse and convert to local time
        assert result.timestamp is not None

    def test_handles_iso_timestamp_with_timezone(self) -> None:
        """Test handling of ISO timestamp with timezone offset."""
        line = '{"timestamp": "2025-01-15T10:30:00+05:00", "message": "test"}'
        result = parse_jsonl_line(line)

        # Should parse and convert to local time
        assert result.timestamp is not None

    def test_preserves_raw_line(self) -> None:
        """Test that raw line is preserved."""
        line = '{"message": "test", "extra": true}'
        result = parse_jsonl_line(line)

        assert result.raw == line

    def test_handles_datetime_object(self) -> None:
        """Test that datetime objects are passed through."""
        from datetime import datetime

        from logview.adapters.jsonl_parser import _parse_timestamp

        dt = datetime(2025, 1, 15, 10, 30, 0)
        result = _parse_timestamp(dt)

        assert result == dt

    def test_parses_unix_timestamp_nanoseconds(self) -> None:
        """Test parsing of Unix timestamps in nanoseconds."""
        # 1737800000000000000 nanoseconds = 2025-01-25 09:06:40
        line = '{"timestamp": 1737800000000000000, "message": "test"}'
        result = parse_jsonl_line(line)

        assert result.timestamp is not None
        assert result.timestamp.year == 2025
        assert result.timestamp.month == 1

    def test_parses_unix_timestamp_microseconds(self) -> None:
        """Test parsing of Unix timestamps in microseconds."""
        # 1737800000000000 microseconds = 2025-01-25 09:06:40
        line = '{"timestamp": 1737800000000000, "message": "test"}'
        result = parse_jsonl_line(line)

        assert result.timestamp is not None
        assert result.timestamp.year == 2025
        assert result.timestamp.month == 1

    def test_handles_invalid_unix_timestamp(self) -> None:
        """Test handling of invalid Unix timestamps."""
        from datetime import datetime

        from logview.adapters.jsonl_parser import _parse_timestamp

        # Extremely large value that will cause overflow
        result = _parse_timestamp(1e20)

        # Should return current time as fallback
        assert isinstance(result, datetime)
        assert result.year >= 2025

    def test_parses_alternative_date_formats(self) -> None:
        """Test parsing of alternative date format strings."""
        test_cases = [
            ('{"timestamp": "2025-01-15 10:30:00", "message": "test"}', 2025, 1, 15),
            ('{"timestamp": "2025-01-15 10:30:00.123456", "message": "test"}', 2025, 1, 15),
            ('{"timestamp": "2025/01/15 10:30:00", "message": "test"}', 2025, 1, 15),
            ('{"timestamp": "15/Jan/2025:10:30:00", "message": "test"}', 2025, 1, 15),
        ]

        for line, year, month, day in test_cases:
            result = parse_jsonl_line(line)
            assert result.timestamp is not None
            assert result.timestamp.year == year
            assert result.timestamp.month == month
            assert result.timestamp.day == day

    def test_raises_on_unparseable_timestamp(self) -> None:
        """Test that unparseable timestamps raise ValueError."""
        import pytest

        from logview.adapters.jsonl_parser import _parse_timestamp

        # Invalid timestamp value
        with pytest.raises(ValueError, match="Cannot parse timestamp"):
            _parse_timestamp({"invalid": "object"})

    def test_case_insensitive_field_lookup(self) -> None:
        """Test that field lookup is case-insensitive."""
        # Test with uppercase MESSAGE field
        line = '{"MESSAGE": "test message", "LEVEL": "info"}'
        result = parse_jsonl_line(line)

        assert result.message == "test message"
        # Severity is normalized to uppercase
        assert result.severity == "INFO"


class TestIsJsonlFormat:
    """Tests for is_jsonl_format function."""

    def test_returns_true_for_valid_json_object(self) -> None:
        """Test that valid JSON objects return True."""
        assert is_jsonl_format('{"key": "value"}') is True
        assert is_jsonl_format('{"a": 1, "b": 2}') is True

    def test_returns_false_for_json_array(self) -> None:
        """Test that JSON arrays return False."""
        assert is_jsonl_format("[1, 2, 3]") is False

    def test_returns_false_for_json_string(self) -> None:
        """Test that JSON strings return False."""
        assert is_jsonl_format('"hello"') is False

    def test_returns_false_for_invalid_json(self) -> None:
        """Test that invalid JSON returns False."""
        assert is_jsonl_format("not json") is False

    def test_returns_false_for_empty_string(self) -> None:
        """Test that empty strings return False."""
        assert is_jsonl_format("") is False

    def test_handles_whitespace(self) -> None:
        """Test that whitespace is handled correctly."""
        assert is_jsonl_format('  {"key": "value"}  ') is True
