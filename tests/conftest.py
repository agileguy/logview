"""Pytest configuration and fixtures."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from logview.adapters.mock import MockLogSource
from logview.domain.models import Filter, LogEntry, Severity, TimeRange


@pytest.fixture
def mock_source() -> MockLogSource:
    """Create a seeded mock log source for reproducible tests."""
    return MockLogSource(seed=42)


@pytest.fixture
def sample_log_entry() -> LogEntry:
    """Create a sample log entry for testing."""
    return LogEntry(
        timestamp=datetime(2024, 1, 15, 10, 23, 45),
        severity=Severity.INFO,
        message="Test log message",
        source="test-service",
        metadata={"cluster": "test", "namespace": "default"},
        raw='{"message": "Test log message"}',
    )


@pytest.fixture
def sample_filter() -> Filter:
    """Create a sample filter for testing."""
    now = datetime.now()
    return Filter(
        time_range=TimeRange(start=now - timedelta(hours=1), end=now),
        severity=Severity.INFO,
        limit=100,
    )


@pytest.fixture
def sample_time_range() -> TimeRange:
    """Create a sample time range for testing."""
    now = datetime.now()
    return TimeRange(start=now - timedelta(hours=1), end=now)
