"""Integration tests for Docker adapter.

These tests require Docker to be running and the docker package to be installed.
They will be skipped if Docker is not available.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta

import pytest

from logview.adapters.docker import (
    DOCKER_AVAILABLE,
    DockerContainerNotFoundError,
    DockerLogSource,
)
from logview.domain.models import Filter, Severity, TimeRange

# Skip all tests in this module if Docker is not available
pytestmark = pytest.mark.skipif(
    not DOCKER_AVAILABLE,
    reason="Docker package not installed",
)


def _docker_daemon_available() -> bool:
    """Check if Docker daemon is accessible."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@pytest.fixture
def docker_test_container():
    """Create a test Docker container with logs.

    Yields the container name, then cleans up the container.
    """
    if not _docker_daemon_available():
        pytest.skip("Docker daemon not available")

    container_name = "logview-test-container"

    # Clean up any existing test container
    subprocess.run(
        ["docker", "rm", "-f", container_name],
        capture_output=True,
    )

    # Create a container that writes some logs then exits
    # Use alpine with a simple script that writes logs
    subprocess.run(
        [
            "docker",
            "run",
            "--name",
            container_name,
            "-d",
            "alpine:latest",
            "sh",
            "-c",
            'echo "INFO: Starting test"; '
            'echo "DEBUG: Detail 1"; '
            'echo "WARN: Warning message"; '
            'echo "ERROR: Error occurred"; '
            'echo "INFO: Finished test"; '
            "sleep 1",
        ],
        check=True,
        capture_output=True,
    )

    # Wait for container to finish
    subprocess.run(
        ["docker", "wait", container_name],
        timeout=10,
        capture_output=True,
    )

    yield container_name

    # Cleanup
    subprocess.run(
        ["docker", "rm", "-f", container_name],
        capture_output=True,
    )


@pytest.mark.asyncio
async def test_fetch_logs_from_real_container(docker_test_container):
    """Test fetching logs from a real Docker container."""
    source = DockerLogSource(container=docker_test_container)

    log_filter = Filter(limit=100)
    entries = []

    async for entry in source.fetch(log_filter):
        entries.append(entry)

    # Should have 5 log entries
    assert len(entries) == 5

    # Check messages
    messages = [e.message for e in entries]
    assert "INFO: Starting test" in messages
    assert "DEBUG: Detail 1" in messages
    assert "WARN: Warning message" in messages
    assert "ERROR: Error occurred" in messages
    assert "INFO: Finished test" in messages

    # Check source
    assert all(e.source == docker_test_container for e in entries)

    # Check metadata
    for entry in entries:
        assert "container_id" in entry.metadata
        assert "container_name" in entry.metadata
        assert entry.metadata["container_name"] == docker_test_container
        assert "image" in entry.metadata
        assert "alpine" in entry.metadata["image"]


@pytest.mark.asyncio
async def test_fetch_logs_with_severity_filter(docker_test_container):
    """Test fetching logs with severity filter."""
    source = DockerLogSource(container=docker_test_container)

    # Filter for WARN and above (excludes DEBUG and INFO)
    log_filter = Filter(limit=100, severity=Severity.WARN)
    entries = []

    async for entry in source.fetch(log_filter):
        entries.append(entry)

    # Should have 2 entries: WARN and ERROR
    assert len(entries) == 2

    # Check that all entries have severity >= WARN
    assert all(e.severity >= Severity.WARN for e in entries)


@pytest.mark.asyncio
async def test_fetch_logs_with_text_search(docker_test_container):
    """Test fetching logs with text search filter."""
    source = DockerLogSource(container=docker_test_container)

    # Search for "Warning"
    log_filter = Filter(limit=100, text_search="Warning")
    entries = []

    async for entry in source.fetch(log_filter):
        entries.append(entry)

    # Should have 1 entry
    assert len(entries) == 1
    assert "Warning" in entries[0].message


@pytest.mark.asyncio
async def test_fetch_logs_with_limit(docker_test_container):
    """Test fetching logs with limit."""
    source = DockerLogSource(container=docker_test_container)

    # Limit to 3 entries
    log_filter = Filter(limit=3)
    entries = []

    async for entry in source.fetch(log_filter):
        entries.append(entry)

    # Should have exactly 3 entries
    assert len(entries) == 3


@pytest.mark.asyncio
async def test_container_not_found():
    """Test error handling for non-existent container."""
    source = DockerLogSource(container="nonexistent-container-12345")

    log_filter = Filter(limit=10)

    with pytest.raises(DockerContainerNotFoundError) as exc_info:
        async for _ in source.fetch(log_filter):
            pass

    assert "nonexistent-container-12345" in str(exc_info.value)


@pytest.mark.asyncio
async def test_container_metadata(docker_test_container):
    """Test that container metadata is properly extracted."""
    source = DockerLogSource(container=docker_test_container)

    log_filter = Filter(limit=1)
    entries = []

    async for entry in source.fetch(log_filter):
        entries.append(entry)

    assert len(entries) == 1
    entry = entries[0]

    # Check required metadata fields
    assert "container_id" in entry.metadata
    assert "container_name" in entry.metadata
    assert "image" in entry.metadata
    assert "status" in entry.metadata

    # Validate values
    assert entry.metadata["container_name"] == docker_test_container
    assert len(entry.metadata["container_id"]) == 12  # Short ID
    assert "alpine" in entry.metadata["image"].lower()


@pytest.mark.asyncio
async def test_source_name(docker_test_container):
    """Test source name generation."""
    # Default name
    source = DockerLogSource(container=docker_test_container)
    # Name should include container identifier
    assert "Docker:" in source.name
    assert docker_test_container in source.name

    # Custom name
    source = DockerLogSource(container=docker_test_container, name="My Test Container")
    assert source.name == "My Test Container"


@pytest.mark.asyncio
async def test_severity_inference(docker_test_container):
    """Test that severities are correctly inferred from log messages."""
    source = DockerLogSource(container=docker_test_container)

    log_filter = Filter(limit=100)
    entries = []

    async for entry in source.fetch(log_filter):
        entries.append(entry)

    # Find specific entries and check severity
    for entry in entries:
        if "INFO:" in entry.message:
            assert entry.severity == Severity.INFO
        elif "DEBUG:" in entry.message:
            assert entry.severity == Severity.DEBUG
        elif "WARN:" in entry.message:
            assert entry.severity == Severity.WARN
        elif "ERROR:" in entry.message:
            assert entry.severity == Severity.ERROR


@pytest.fixture
def docker_json_logs_container():
    """Create a test container with JSON-formatted logs."""
    if not _docker_daemon_available():
        pytest.skip("Docker daemon not available")

    container_name = "logview-test-json-container"

    # Clean up any existing test container
    subprocess.run(
        ["docker", "rm", "-f", container_name],
        capture_output=True,
    )

    # Create container that outputs JSON logs
    # Note: Docker automatically wraps logs in JSON format when using json-file driver
    subprocess.run(
        [
            "docker",
            "run",
            "--name",
            container_name,
            "--log-driver",
            "json-file",
            "-d",
            "alpine:latest",
            "sh",
            "-c",
            'echo "Test JSON log"; sleep 1',
        ],
        check=True,
        capture_output=True,
    )

    # Wait for container
    subprocess.run(
        ["docker", "wait", container_name],
        timeout=10,
        capture_output=True,
    )

    yield container_name

    # Cleanup
    subprocess.run(
        ["docker", "rm", "-f", container_name],
        capture_output=True,
    )


@pytest.mark.asyncio
async def test_json_log_format(docker_json_logs_container):
    """Test parsing JSON-formatted Docker logs."""
    source = DockerLogSource(container=docker_json_logs_container)

    log_filter = Filter(limit=10)
    entries = []

    async for entry in source.fetch(log_filter):
        entries.append(entry)

    assert len(entries) >= 1

    # Check that log was parsed
    entry = entries[0]
    assert entry.message == "Test JSON log"
    assert entry.timestamp is not None
    assert isinstance(entry.timestamp, datetime)


@pytest.mark.asyncio
async def test_validate_filter():
    """Test filter validation."""
    if not _docker_daemon_available():
        pytest.skip("Docker daemon not available")

    source = DockerLogSource(container="test")

    # Valid filter
    errors = source.validate_filter(Filter(limit=100))
    assert len(errors) == 0

    # Invalid limit
    errors = source.validate_filter(Filter(limit=0))
    assert len(errors) > 0

    # Invalid time range
    start = datetime.now()
    end = start - timedelta(hours=1)
    errors = source.validate_filter(Filter(limit=10, time_range=TimeRange(start=start, end=end)))
    assert len(errors) > 0


@pytest.mark.asyncio
async def test_available_filters():
    """Test available filter fields."""
    if not _docker_daemon_available():
        pytest.skip("Docker daemon not available")

    source = DockerLogSource(container="test")

    filters = source.available_filters()

    assert len(filters) > 0
    filter_names = [f.name for f in filters]
    assert "container" in filter_names
    assert "severity" in filter_names
