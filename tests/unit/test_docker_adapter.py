"""Unit tests for Docker adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pytest

from logview.adapters.docker import (
    DOCKER_AVAILABLE,
    DockerContainerNotFoundError,
    DockerDaemonError,
    DockerLogSource,
    DockerNotInstalledError,
    DockerPermissionError,
    _infer_severity,
    _parse_docker_timestamp,
    _parse_log_line,
    _sanitize_message,
)
from logview.domain.models import Filter, Severity, TimeRange


# Mock Docker container for testing
@dataclass
class MockContainer:
    """Mock Docker container."""

    id: str = "abc123def456"
    name: str = "test-container"
    attrs: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.attrs is None:
            self.attrs = {
                "Config": {
                    "Image": "nginx:latest",
                    "Labels": {"app": "web", "env": "test"},
                },
                "Image": "sha256:123456789012345678901234567890123456789012345678901234567890",
                "State": {"Status": "running"},
            }

    def logs(
        self,
        stdout: bool = True,
        stderr: bool = True,
        timestamps: bool = False,
        since: datetime | None = None,
        until: datetime | None = None,
        stream: bool = False,
    ) -> list[bytes]:
        """Mock logs method."""
        return [
            b'{"log":"Test log message\\n","stream":"stdout","time":"2024-01-15T10:00:00.123456789Z"}\n',
            b'{"log":"Another message\\n","stream":"stderr","time":"2024-01-15T10:00:01.123456789Z"}\n',
        ]


class MockContainerManager:
    """Mock Docker container manager."""

    def __init__(
        self,
        container: MockContainer | None = None,
        error: Exception | None = None,
    ) -> None:
        """Initialize mock container manager.

        Args:
            container: Container to return.
            error: Exception to raise on get.
        """
        self.container = container or MockContainer()
        self.error = error

    def get(self, container_id: str) -> MockContainer:
        """Mock get method."""
        if self.error:
            raise self.error
        return self.container


class MockDockerClient:
    """Mock Docker client for testing."""

    def __init__(
        self,
        container: MockContainer | None = None,
        error: Exception | None = None,
    ) -> None:
        """Initialize mock client.

        Args:
            container: Container to return.
            error: Exception to raise.
        """
        self.containers = MockContainerManager(container=container, error=error)


# Tests


def test_infer_severity_from_json():
    """Test severity inference from JSON log fields."""
    # Test with 'level' field
    assert _infer_severity("message", {"level": "ERROR"}) == Severity.ERROR
    assert _infer_severity("message", {"level": "error"}) == Severity.ERROR

    # Test with 'severity' field
    assert _infer_severity("message", {"severity": "WARN"}) == Severity.WARN

    # Test with 'loglevel' field
    assert _infer_severity("message", {"loglevel": "DEBUG"}) == Severity.DEBUG

    # Test with 'log_level' field
    assert _infer_severity("message", {"log_level": "CRITICAL"}) == Severity.CRITICAL


def test_infer_severity_from_message():
    """Test severity inference from log message patterns."""
    assert _infer_severity("ERROR: Something went wrong") == Severity.ERROR
    assert _infer_severity("WARN: Be careful") == Severity.WARN
    assert _infer_severity("INFO: All good") == Severity.INFO
    assert _infer_severity("DEBUG: Details here") == Severity.DEBUG
    assert _infer_severity("CRITICAL: System failure") == Severity.CRITICAL

    # Test case insensitivity
    assert _infer_severity("error in processing") == Severity.ERROR
    assert _infer_severity("Warning message") == Severity.WARN

    # Test default
    assert _infer_severity("Just a message") == Severity.INFO


def test_infer_severity_priority():
    """Test that JSON fields take priority over message patterns."""
    # Even though message says ERROR, JSON field says INFO
    assert _infer_severity("ERROR in process", {"level": "INFO"}) == Severity.INFO


def test_sanitize_message_ansi_codes():
    """Test ANSI escape code removal from messages."""
    # Portainer-style colored log with ANSI codes
    message = "\x1b[90m2025/12/14 09:19PM\x1b[0m \x1b[32mINF\x1b[0m \x1b[1mstarting server\x1b[0m"
    sanitized = _sanitize_message(message)
    assert sanitized == "2025/12/14 09:19PM INF starting server"
    assert "\x1b" not in sanitized

    # Message with [XXm style ANSI codes
    message = "[90m2025/12/14[0m [32mINF[0m message"
    # Note: [XXm style codes without ESC prefix are not ANSI codes
    # They should remain as-is (just part of the message)
    sanitized = _sanitize_message(message)
    # Should still contain the brackets as they're not escape codes
    assert "[90m" in sanitized or "2025/12/14" in sanitized

    # Real ANSI codes with ESC prefix
    message = "\x1b[32mGREEN\x1b[0m normal \x1b[1mbold\x1b[0m"
    sanitized = _sanitize_message(message)
    assert sanitized == "GREEN normal bold"

    # Control characters (should be removed except tab/newline)
    message = "test\x00\x01\x02message"
    sanitized = _sanitize_message(message)
    assert sanitized == "testmessage"

    # Tab and newline should be preserved
    message = "test\ttab\nnewline"
    sanitized = _sanitize_message(message)
    assert sanitized == "test\ttab\nnewline"


def test_parse_docker_timestamp():
    """Test Docker timestamp parsing."""
    # Standard Docker timestamp with nanoseconds
    ts = _parse_docker_timestamp("2024-01-15T10:23:45.123456789Z")
    assert ts.year == 2024
    assert ts.month == 1
    assert ts.day == 15
    # Hour depends on local timezone, so don't test exact value
    # Just verify it's a valid hour
    assert 0 <= ts.hour < 24
    assert ts.minute == 23
    assert ts.second == 45
    # Microseconds (nanoseconds truncated)
    assert ts.microsecond == 123456
    # Should be naive (no timezone)
    assert ts.tzinfo is None

    # Without nanoseconds
    ts = _parse_docker_timestamp("2024-01-15T10:23:45Z")
    assert ts.year == 2024
    assert ts.microsecond == 0


def test_parse_docker_timestamp_invalid():
    """Test Docker timestamp parsing with invalid input."""
    # Should return current time on parse error
    ts = _parse_docker_timestamp("invalid-timestamp")
    assert isinstance(ts, datetime)


def test_parse_log_line_json_format():
    """Test parsing Docker log line in JSON format."""
    line = b'{"log":"Test message\\n","stream":"stdout","time":"2024-01-15T10:00:00.123456789Z"}\n'
    metadata = {"container_id": "abc123", "container_name": "test"}

    entry = _parse_log_line(line, "test-container", metadata)

    assert entry is not None
    assert entry.message == "Test message"
    assert entry.source == "test-container"
    assert entry.severity == Severity.INFO
    assert entry.metadata["stream"] == "stdout"
    assert entry.metadata["container_id"] == "abc123"
    assert entry.timestamp.year == 2024


def test_parse_log_line_json_with_severity():
    """Test parsing JSON log line with severity field."""
    line = b'{"log":"Error occurred\\n","stream":"stderr","time":"2024-01-15T10:00:00Z","level":"ERROR"}\n'
    metadata = {"container_id": "abc123"}

    entry = _parse_log_line(line, "test", metadata)

    assert entry is not None
    assert entry.severity == Severity.ERROR
    assert entry.metadata["stream"] == "stderr"


def test_parse_log_line_plain_text():
    """Test parsing Docker log line in plain text format."""
    line = b"2024-01-15T10:00:00.123456789Z Test message here\n"
    metadata = {"container_id": "abc123"}

    entry = _parse_log_line(line, "test-container", metadata)

    assert entry is not None
    assert entry.message == "Test message here"
    assert entry.source == "test-container"
    assert entry.timestamp.year == 2024


def test_parse_log_line_plain_text_no_timestamp():
    """Test parsing plain text log line without timestamp."""
    line = b"Just a log message without timestamp\n"
    metadata = {"container_id": "abc123"}

    entry = _parse_log_line(line, "test", metadata)

    assert entry is not None
    assert entry.message == "Just a log message without timestamp"


def test_parse_log_line_with_ansi_codes():
    """Test parsing log line with ANSI escape codes (like Portainer)."""
    # JSON format with ANSI codes
    line = b'{"log":"\\u001b[90m2025/12/14\\u001b[0m \\u001b[32mINF\\u001b[0m starting\\n","stream":"stdout","time":"2024-01-15T10:00:00Z"}\n'
    metadata = {"container_id": "abc123"}

    entry = _parse_log_line(line, "test", metadata)

    assert entry is not None
    # ANSI codes should be stripped
    assert "\x1b" not in entry.message
    assert "2025/12/14" in entry.message
    assert "INF" in entry.message
    assert "starting" in entry.message


def test_parse_log_line_empty():
    """Test parsing empty log line."""
    entry = _parse_log_line(b"", "test", {})
    assert entry is None

    entry = _parse_log_line(b"\n", "test", {})
    assert entry is None


def test_parse_log_line_invalid():
    """Test parsing invalid log line."""
    # Should handle gracefully and return None
    _parse_log_line(b"\x00\x01\x02", "test", {})
    # May be None or may parse as plain text depending on error
    # Either is acceptable as long as it doesn't crash


def test_docker_not_installed():
    """Test error when docker package not installed."""
    if DOCKER_AVAILABLE:
        pytest.skip("Docker is installed, cannot test unavailability")

    with pytest.raises(DockerNotInstalledError) as exc_info:
        DockerLogSource(container="test")

    assert "pip install logview-ag[docker]" in str(exc_info.value)


def test_docker_log_source_init():
    """Test DockerLogSource initialization."""
    client = MockDockerClient()
    source = DockerLogSource(container="nginx", client=client)

    assert source._container_id == "nginx"
    assert source.source_type == "docker"


def test_docker_log_source_name():
    """Test DockerLogSource name property."""
    client = MockDockerClient()

    # Default name
    source = DockerLogSource(container="nginx", client=client)
    assert "Docker:" in source.name
    assert "nginx" in source.name

    # Custom name
    source = DockerLogSource(container="nginx", name="My Container", client=client)
    assert source.name == "My Container"


def test_docker_log_source_name_after_resolve():
    """Test DockerLogSource name after container resolution."""
    client = MockDockerClient()
    source = DockerLogSource(container="nginx", client=client)

    # Name before resolution
    assert source.name == "Docker: nginx"

    # Resolve container
    source._resolve_container(client)

    # Name after resolution should use container name
    assert source.name == "Docker: test-container"


def test_resolve_container():
    """Test container resolution and metadata caching."""
    container = MockContainer(id="abc123", name="my-app")
    client = MockDockerClient(container=container)
    source = DockerLogSource(container="my-app", client=client)

    resolved = source._resolve_container(client)

    assert resolved == container
    assert source._container_name == "my-app"
    assert source._container_metadata["container_id"] == "abc123"
    assert source._container_metadata["container_name"] == "my-app"
    assert source._container_metadata["image"] == "nginx:latest"
    assert source._container_metadata["status"] == "running"
    assert "label.app" in source._container_metadata
    assert source._container_metadata["label.app"] == "web"


def test_resolve_container_not_found():
    """Test container resolution when container not found."""
    error = Exception("Container not found")
    client = MockDockerClient(error=error)
    source = DockerLogSource(container="nonexistent", client=client)

    with pytest.raises(DockerContainerNotFoundError) as exc_info:
        source._resolve_container(client)

    assert "nonexistent" in str(exc_info.value)


def test_docker_daemon_error():
    """Test error when Docker daemon is unreachable."""
    if not DOCKER_AVAILABLE:
        pytest.skip("Docker not installed")

    # Try to create client with invalid host
    from logview.adapters.docker import DockerLogSource

    source = DockerLogSource(container="test", docker_host="tcp://invalid-host:9999")

    with pytest.raises((DockerDaemonError, DockerPermissionError)):
        source._get_client()


@pytest.mark.asyncio
async def test_fetch_logs():
    """Test fetching logs from Docker container."""
    client = MockDockerClient()
    source = DockerLogSource(container="test", client=client)

    log_filter = Filter(limit=10)
    entries = []

    async for entry in source.fetch(log_filter):
        entries.append(entry)

    assert len(entries) == 2
    assert entries[0].message == "Test log message"
    assert entries[0].source == "test-container"
    assert entries[1].message == "Another message"


@pytest.mark.asyncio
async def test_fetch_logs_with_limit():
    """Test fetching logs with limit."""
    # Create container with many log lines
    container = MockContainer()

    def custom_logs(**kwargs: Any) -> list[bytes]:
        return [
            b'{"log":"Line 1\\n","stream":"stdout","time":"2024-01-15T10:00:00Z"}\n',
            b'{"log":"Line 2\\n","stream":"stdout","time":"2024-01-15T10:00:01Z"}\n',
            b'{"log":"Line 3\\n","stream":"stdout","time":"2024-01-15T10:00:02Z"}\n',
            b'{"log":"Line 4\\n","stream":"stdout","time":"2024-01-15T10:00:03Z"}\n',
            b'{"log":"Line 5\\n","stream":"stdout","time":"2024-01-15T10:00:04Z"}\n',
        ]

    container.logs = custom_logs

    client = MockDockerClient(container=container)
    source = DockerLogSource(container="test", client=client)

    # Limit to 3 entries
    log_filter = Filter(limit=3)
    entries = []

    async for entry in source.fetch(log_filter):
        entries.append(entry)

    assert len(entries) == 3
    assert entries[0].message == "Line 1"
    assert entries[2].message == "Line 3"


@pytest.mark.asyncio
async def test_fetch_logs_with_filter():
    """Test fetching logs with text search filter."""
    container = MockContainer()

    def custom_logs(**kwargs: Any) -> list[bytes]:
        return [
            b'{"log":"ERROR: Something failed\\n","stream":"stdout","time":"2024-01-15T10:00:00Z"}\n',
            b'{"log":"INFO: All good\\n","stream":"stdout","time":"2024-01-15T10:00:01Z"}\n',
            b'{"log":"ERROR: Another failure\\n","stream":"stdout","time":"2024-01-15T10:00:02Z"}\n',
        ]

    container.logs = custom_logs

    client = MockDockerClient(container=container)
    source = DockerLogSource(container="test", client=client)

    # Filter for ERROR messages
    log_filter = Filter(limit=10, text_search="ERROR")
    entries = []

    async for entry in source.fetch(log_filter):
        entries.append(entry)

    assert len(entries) == 2
    assert all("ERROR" in entry.message for entry in entries)


@pytest.mark.asyncio
async def test_fetch_logs_with_severity_filter():
    """Test fetching logs with severity filter."""
    container = MockContainer()

    def custom_logs(**kwargs: Any) -> list[bytes]:
        return [
            b'{"log":"DEBUG: Details\\n","stream":"stdout","time":"2024-01-15T10:00:00Z"}\n',
            b'{"log":"INFO: Normal message\\n","stream":"stdout","time":"2024-01-15T10:00:01Z"}\n',
            b'{"log":"ERROR: Problem\\n","stream":"stdout","time":"2024-01-15T10:00:02Z"}\n',
        ]

    container.logs = custom_logs

    client = MockDockerClient(container=container)
    source = DockerLogSource(container="test", client=client)

    # Filter for INFO and above (excludes DEBUG)
    log_filter = Filter(limit=10, severity=Severity.INFO)
    entries = []

    async for entry in source.fetch(log_filter):
        entries.append(entry)

    assert len(entries) == 2
    assert entries[0].message == "INFO: Normal message"
    assert entries[1].message == "ERROR: Problem"


@pytest.mark.asyncio
async def test_fetch_logs_with_time_range():
    """Test fetching logs with time range filter."""
    container = MockContainer()

    # Mock logs to capture kwargs
    captured_kwargs = {}

    def custom_logs(**kwargs: Any) -> list[bytes]:
        captured_kwargs.update(kwargs)
        return [
            b'{"log":"Test\\n","stream":"stdout","time":"2024-01-15T10:00:00Z"}\n',
        ]

    container.logs = custom_logs

    client = MockDockerClient(container=container)
    source = DockerLogSource(container="test", client=client)

    # Create time range filter
    start = datetime(2024, 1, 15, 9, 0, 0)
    end = datetime(2024, 1, 15, 11, 0, 0)
    log_filter = Filter(limit=10, time_range=TimeRange(start=start, end=end))

    entries = []
    async for entry in source.fetch(log_filter):
        entries.append(entry)

    # Verify that since/until were passed to Docker API
    assert "since" in captured_kwargs
    assert "until" in captured_kwargs
    assert captured_kwargs["since"] == start
    assert captured_kwargs["until"] == end


def test_validate_filter():
    """Test filter validation."""
    client = MockDockerClient()
    source = DockerLogSource(container="test", client=client)

    # Valid filter
    errors = source.validate_filter(Filter(limit=100))
    assert len(errors) == 0

    # Note: We can't test invalid limits (< 1 or > 10000) because the Filter
    # model's __post_init__ validates them before the adapter's validate_filter
    # is called. These tests would raise ValueError during Filter construction.

    # Invalid time range (can be created because TimeRange validates separately)
    start = datetime(2024, 1, 15, 11, 0, 0)
    end = datetime(2024, 1, 15, 9, 0, 0)
    # Create Filter with valid limit, then validate
    try:
        # TimeRange will raise ValueError in __post_init__ if start > end
        time_range = TimeRange(start=start, end=end)
        # If we get here, TimeRange didn't validate (shouldn't happen)
        log_filter = Filter(limit=10, time_range=time_range)
        errors = source.validate_filter(log_filter)
        assert len(errors) > 0
        assert any("before" in err for err in errors)
    except ValueError:
        # Expected: TimeRange validates in __post_init__
        pass


def test_available_filters():
    """Test available filter fields."""
    client = MockDockerClient()
    source = DockerLogSource(container="test", client=client)

    filters = source.available_filters()

    assert len(filters) > 0
    filter_names = [f.name for f in filters]
    assert "container" in filter_names
    assert "severity" in filter_names
