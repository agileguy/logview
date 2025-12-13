"""Pytest configuration and fixtures."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from logview.adapters.mock import MockLogSource
from logview.domain.models import Filter, LogEntry, Severity, TimeRange

# Snapshot directory configuration for CI vs local environments
# CI uses a separate snapshot directory to avoid conflicts
SNAPSHOT_DIR_ENV = os.environ.get("SNAPSHOT_DIR", "__snapshots__")
IS_CI = os.environ.get("CI", "false").lower() == "true"


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest for the test session."""
    # Register CI marker
    config.addinivalue_line("markers", "ci_only: marks tests to run only in CI")
    config.addinivalue_line("markers", "local_only: marks tests to run only locally")


@pytest.fixture(scope="session")
def snapshot_dir() -> Path:
    """Get the snapshot directory based on environment.

    Returns:
        Path to the snapshot directory (different for CI vs local).
    """
    base_dir = Path(__file__).parent
    if IS_CI:
        return base_dir / "__snapshots_ci__"
    return base_dir / "__snapshots__"


@pytest.fixture(scope="session")
def is_ci() -> bool:
    """Check if running in CI environment."""
    return IS_CI


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
