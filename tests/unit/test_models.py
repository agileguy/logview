"""Tests for domain models."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from logview.domain.models import Filter, FilterField, LogEntry, Severity, TimeRange


class TestSeverity:
    """Tests for Severity enum."""

    def test_from_string_valid(self) -> None:
        """Test parsing valid severity strings."""
        assert Severity.from_string("DEBUG") == Severity.DEBUG
        assert Severity.from_string("INFO") == Severity.INFO
        assert Severity.from_string("WARN") == Severity.WARN
        assert Severity.from_string("ERROR") == Severity.ERROR
        assert Severity.from_string("CRITICAL") == Severity.CRITICAL

    def test_from_string_case_insensitive(self) -> None:
        """Test case-insensitive parsing."""
        assert Severity.from_string("debug") == Severity.DEBUG
        assert Severity.from_string("Info") == Severity.INFO
        assert Severity.from_string("ERROR") == Severity.ERROR

    def test_from_string_aliases(self) -> None:
        """Test common aliases are recognized."""
        assert Severity.from_string("WARNING") == Severity.WARN
        assert Severity.from_string("FATAL") == Severity.CRITICAL
        assert Severity.from_string("ERR") == Severity.ERROR

    def test_from_string_invalid(self) -> None:
        """Test invalid severity strings raise ValueError."""
        with pytest.raises(ValueError):
            Severity.from_string("INVALID")

    def test_comparison_operators(self) -> None:
        """Test severity comparison operators."""
        assert Severity.ERROR > Severity.WARN
        assert Severity.WARN >= Severity.WARN
        assert Severity.INFO < Severity.WARN
        assert Severity.DEBUG <= Severity.DEBUG
        assert Severity.CRITICAL >= Severity.DEBUG


class TestTimeRange:
    """Tests for TimeRange."""

    def test_valid_time_range(self) -> None:
        """Test creating a valid time range."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        end = datetime(2024, 1, 1, 12, 0, 0)
        tr = TimeRange(start=start, end=end)
        assert tr.start == start
        assert tr.end == end

    def test_invalid_time_range(self) -> None:
        """Test that start after end raises ValueError."""
        start = datetime(2024, 1, 2, 0, 0, 0)
        end = datetime(2024, 1, 1, 0, 0, 0)
        with pytest.raises(ValueError, match="start must be before"):
            TimeRange(start=start, end=end)

    def test_contains(self) -> None:
        """Test the contains method."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        end = datetime(2024, 1, 1, 12, 0, 0)
        tr = TimeRange(start=start, end=end)

        assert tr.contains(datetime(2024, 1, 1, 6, 0, 0))
        assert tr.contains(start)  # inclusive
        assert tr.contains(end)  # inclusive
        assert not tr.contains(datetime(2024, 1, 1, 13, 0, 0))
        assert not tr.contains(datetime(2023, 12, 31, 23, 59, 59))


class TestFilter:
    """Tests for Filter."""

    def test_default_filter(self) -> None:
        """Test default filter values."""
        f = Filter()
        assert f.time_range is None
        assert f.fields == {}
        assert f.text_search is None
        assert f.source_filter is None
        assert f.severity is None
        assert f.limit == 1000

    def test_filter_with_values(self) -> None:
        """Test filter with specified values."""
        now = datetime.now()
        tr = TimeRange(start=now - timedelta(hours=1), end=now)
        f = Filter(
            time_range=tr,
            fields={"namespace": "default"},
            text_search="error",
            severity=Severity.WARN,
            limit=500,
        )
        assert f.time_range == tr
        assert f.fields == {"namespace": "default"}
        assert f.text_search == "error"
        assert f.severity == Severity.WARN
        assert f.limit == 500

    def test_filter_limit_validation(self) -> None:
        """Test filter limit validation."""
        with pytest.raises(ValueError, match="limit must be at least 1"):
            Filter(limit=0)

        with pytest.raises(ValueError, match="limit must not exceed 10000"):
            Filter(limit=10001)


class TestLogEntry:
    """Tests for LogEntry."""

    def test_create_log_entry(self) -> None:
        """Test creating a log entry."""
        entry = LogEntry(
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            severity=Severity.INFO,
            message="Test message",
            source="test-source",
            metadata={"key": "value"},
            raw='{"raw": "data"}',
        )
        assert entry.severity == Severity.INFO
        assert entry.message == "Test message"

    def test_to_json(self) -> None:
        """Test JSON serialization."""
        entry = LogEntry(
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            severity=Severity.INFO,
            message="Test message",
            source="test-source",
            metadata={"key": "value"},
        )
        result = json.loads(entry.to_json())
        assert result["severity"] == "INFO"
        assert result["message"] == "Test message"
        assert result["source"] == "test-source"
        assert result["metadata"] == {"key": "value"}

    def test_matches_filter_no_filter(self) -> None:
        """Test that entries match an empty filter."""
        entry = LogEntry(
            timestamp=datetime.now(),
            severity=Severity.INFO,
            message="Test",
            source="test",
        )
        assert entry.matches_filter(Filter())

    def test_matches_filter_time_range(self) -> None:
        """Test time range filtering."""
        now = datetime.now()
        entry = LogEntry(
            timestamp=now,
            severity=Severity.INFO,
            message="Test",
            source="test",
        )

        # Entry within range
        tr_match = TimeRange(start=now - timedelta(hours=1), end=now + timedelta(hours=1))
        assert entry.matches_filter(Filter(time_range=tr_match))

        # Entry outside range
        tr_no_match = TimeRange(
            start=now + timedelta(hours=1), end=now + timedelta(hours=2)
        )
        assert not entry.matches_filter(Filter(time_range=tr_no_match))

    def test_matches_filter_severity(self) -> None:
        """Test severity filtering."""
        entry = LogEntry(
            timestamp=datetime.now(),
            severity=Severity.WARN,
            message="Test",
            source="test",
        )

        # WARN >= INFO, should match
        assert entry.matches_filter(Filter(severity=Severity.INFO))

        # WARN >= WARN, should match
        assert entry.matches_filter(Filter(severity=Severity.WARN))

        # WARN < ERROR, should not match
        assert not entry.matches_filter(Filter(severity=Severity.ERROR))

    def test_matches_filter_text_search(self) -> None:
        """Test text search filtering."""
        entry = LogEntry(
            timestamp=datetime.now(),
            severity=Severity.INFO,
            message="Connection refused to database",
            source="test",
        )

        assert entry.matches_filter(Filter(text_search="connection"))
        assert entry.matches_filter(Filter(text_search="DATABASE"))  # case insensitive
        assert not entry.matches_filter(Filter(text_search="timeout"))

    def test_matches_filter_source_filter(self) -> None:
        """Test source filtering."""
        entry = LogEntry(
            timestamp=datetime.now(),
            severity=Severity.INFO,
            message="Test message",
            source="api-server-abc123",
        )

        # Should match substring
        assert entry.matches_filter(Filter(source_filter="api-server"))
        assert entry.matches_filter(Filter(source_filter="abc"))
        # Should be case insensitive
        assert entry.matches_filter(Filter(source_filter="API-SERVER"))
        # Should not match non-present string
        assert not entry.matches_filter(Filter(source_filter="worker"))

    def test_matches_filter_source_filter_case_insensitive(self) -> None:
        """Test source filtering is case insensitive."""
        entry = LogEntry(
            timestamp=datetime.now(),
            severity=Severity.INFO,
            message="Test",
            source="WorkerPod-123",
        )

        assert entry.matches_filter(Filter(source_filter="worker"))
        assert entry.matches_filter(Filter(source_filter="WORKER"))
        assert entry.matches_filter(Filter(source_filter="pod"))
        assert entry.matches_filter(Filter(source_filter="POD"))

    def test_matches_filter_fields(self) -> None:
        """Test field filtering."""
        entry = LogEntry(
            timestamp=datetime.now(),
            severity=Severity.INFO,
            message="Test",
            source="test",
            metadata={"namespace": "default", "pod": "api-123"},
        )

        assert entry.matches_filter(Filter(fields={"namespace": "default"}))
        assert not entry.matches_filter(Filter(fields={"namespace": "production"}))
        assert not entry.matches_filter(Filter(fields={"cluster": "any"}))


class TestFilterField:
    """Tests for FilterField."""

    def test_create_filter_field(self) -> None:
        """Test creating a filter field."""
        field = FilterField(
            name="severity",
            label="Severity Level",
            required=True,
            options=["DEBUG", "INFO", "WARN", "ERROR"],
        )
        assert field.name == "severity"
        assert field.label == "Severity Level"
        assert field.required is True
        assert field.options == ["DEBUG", "INFO", "WARN", "ERROR"]

    def test_filter_field_defaults(self) -> None:
        """Test filter field default values."""
        field = FilterField(name="text", label="Text Search")
        assert field.required is False
        assert field.options is None
