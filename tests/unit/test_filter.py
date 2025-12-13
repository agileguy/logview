"""Tests for filter parsing and validation."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from logview.domain.models import Filter, Severity, TimeRange


class TestFilterValidation:
    """Tests for filter validation."""

    def test_valid_filter(self) -> None:
        """Test creating a valid filter."""
        f = Filter(severity=Severity.INFO, limit=100)
        assert f.severity == Severity.INFO
        assert f.limit == 100

    def test_limit_bounds(self) -> None:
        """Test filter limit boundaries."""
        # Minimum valid
        f = Filter(limit=1)
        assert f.limit == 1

        # Maximum valid
        f = Filter(limit=10000)
        assert f.limit == 10000

        # Below minimum
        with pytest.raises(ValueError):
            Filter(limit=0)

        # Above maximum
        with pytest.raises(ValueError):
            Filter(limit=10001)

    def test_filter_immutability(self) -> None:
        """Test that Filter is frozen/immutable."""
        f = Filter(limit=100)
        with pytest.raises(AttributeError):
            f.limit = 200  # type: ignore[misc]


class TestTimeRangeValidation:
    """Tests for time range validation."""

    def test_same_start_end(self) -> None:
        """Test that same start and end is valid (instant)."""
        now = datetime.now()
        tr = TimeRange(start=now, end=now)
        assert tr.start == tr.end

    def test_microsecond_precision(self) -> None:
        """Test time ranges with microsecond precision."""
        start = datetime(2024, 1, 1, 0, 0, 0, 0)
        end = datetime(2024, 1, 1, 0, 0, 0, 1)  # 1 microsecond later
        tr = TimeRange(start=start, end=end)
        assert tr.contains(start)
        assert tr.contains(end)


class TestFilterCombinations:
    """Tests for combined filter criteria."""

    def test_multiple_criteria(self) -> None:
        """Test filter with multiple criteria."""
        now = datetime.now()
        f = Filter(
            time_range=TimeRange(start=now - timedelta(hours=1), end=now),
            severity=Severity.WARN,
            text_search="error",
            fields={"namespace": "default"},
            limit=50,
        )
        assert f.time_range is not None
        assert f.severity == Severity.WARN
        assert f.text_search == "error"
        assert f.fields == {"namespace": "default"}
        assert f.limit == 50

    @pytest.mark.parametrize(
        "severity,expected_value",
        [
            (Severity.DEBUG, "DEBUG"),
            (Severity.INFO, "INFO"),
            (Severity.WARN, "WARN"),
            (Severity.ERROR, "ERROR"),
            (Severity.CRITICAL, "CRITICAL"),
        ],
    )
    def test_severity_values(self, severity: Severity, expected_value: str) -> None:
        """Test all severity enum values."""
        f = Filter(severity=severity)
        assert f.severity is not None
        assert f.severity.value == expected_value
