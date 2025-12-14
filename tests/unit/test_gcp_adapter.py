"""Unit tests for GCP Cloud Logging adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest

from logview.adapters.gcp import (
    GCP_AVAILABLE,
    GCPAuthenticationError,
    GCPInvalidProjectError,
    GCPLogSource,
    GCPNotInstalledError,
    GCPPermissionError,
    GCPProjectNotFoundError,
    GCPQuotaExceededError,
    _build_filter,
    _parse_log_entry,
    _validate_project_id,
)
from logview.domain.models import Filter, Severity, TimeRange


# Mock log entry for testing
@dataclass
class MockResource:
    """Mock GCP resource."""

    type: str = "gce_instance"
    labels: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if self.labels is None:
            self.labels = {"instance_id": "test-instance"}


@dataclass
class MockLogEntry:
    """Mock GCP log entry for testing."""

    timestamp: datetime | None = None
    severity: str = "INFO"
    text_payload: str | None = None
    json_payload: dict[str, Any] | None = None
    proto_payload: Any = None
    resource: MockResource | None = None
    log_name: str = "projects/test-project/logs/test"
    labels: dict[str, str] | None = None
    insert_id: str = "test-insert-id"

    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = datetime.now(UTC)
        if self.resource is None:
            self.resource = MockResource()
        if self.labels is None:
            self.labels = {}


class MockLoggingClient:
    """Mock GCP logging client for testing."""

    def __init__(
        self,
        entries: list[MockLogEntry] | None = None,
        error: Exception | None = None,
    ) -> None:
        """Initialize mock client.

        Args:
            entries: List of entries to return.
            error: Exception to raise on list_entries.
        """
        self.entries = entries or []
        self.error = error
        self.last_filter: str | None = None
        self.last_order_by: str | None = None
        self.last_page_size: int | None = None
        self.last_resource_names: list[str] | None = None

    def list_entries(
        self,
        filter_: str | None = None,
        order_by: str | None = None,
        page_size: int | None = None,
        resource_names: list[str] | None = None,
    ) -> list[MockLogEntry]:
        """Mock list_entries method."""
        self.last_filter = filter_
        self.last_order_by = order_by
        self.last_page_size = page_size
        self.last_resource_names = resource_names

        if self.error:
            raise self.error

        return self.entries


class TestProjectIdValidation:
    """Tests for project ID validation."""

    def test_valid_project_ids(self) -> None:
        """Test valid project ID formats."""
        valid_ids = [
            "my-project",
            "project-123",
            "a12345",  # 6 chars minimum
            "my-very-long-project-name123",  # 28 chars (within 30)
            "test-project-abc",
            "project--name",  # Double hyphen is valid
        ]
        for project_id in valid_ids:
            _validate_project_id(project_id)  # Should not raise

    def test_invalid_project_ids(self) -> None:
        """Test invalid project ID formats."""
        invalid_ids = [
            ("My-Project", "uppercase"),
            ("my_project", "underscore"),
            ("12345a", "starts with number"),
            ("1project", "starts with number"),
            ("a", "too short"),
            ("ab", "too short"),
            ("abc", "too short"),
            ("abcd", "too short"),
            ("abcde", "too short"),
            ("project-", "ends with hyphen"),
            ("-project", "starts with hyphen"),
            ("a" * 31, "too long"),
            ("", "empty"),
        ]
        for project_id, _reason in invalid_ids:
            with pytest.raises(GCPInvalidProjectError, match="Invalid project ID"):
                _validate_project_id(project_id)


class TestFilterBuilding:
    """Tests for Cloud Logging filter string building."""

    def test_empty_filter(self) -> None:
        """Test building empty filter."""
        filter_str = _build_filter(Filter())
        assert filter_str == ""

    def test_severity_filter(self) -> None:
        """Test building severity filter."""
        filter_str = _build_filter(Filter(severity=Severity.ERROR))
        assert "severity >= ERROR" in filter_str

    def test_time_range_filter(self) -> None:
        """Test building time range filter with naive datetimes (appends Z)."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        end = datetime(2024, 1, 2, 0, 0, 0)
        time_range = TimeRange(start=start, end=end)
        filter_str = _build_filter(Filter(time_range=time_range))
        assert 'timestamp >= "2024-01-01T00:00:00Z"' in filter_str
        assert 'timestamp <= "2024-01-02T00:00:00Z"' in filter_str

    def test_time_range_filter_timezone_aware(self) -> None:
        """Test building time range filter with timezone-aware datetimes (uses existing offset)."""
        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        end = datetime(2024, 1, 2, 0, 0, 0, tzinfo=UTC)
        time_range = TimeRange(start=start, end=end)
        filter_str = _build_filter(Filter(time_range=time_range))
        # Should use the existing timezone offset, not append extra Z
        assert 'timestamp >= "2024-01-01T00:00:00+00:00"' in filter_str
        assert 'timestamp <= "2024-01-02T00:00:00+00:00"' in filter_str
        # Verify no double-Z (malformed timestamp)
        assert "+00:00Z" not in filter_str

    def test_text_search_filter(self) -> None:
        """Test building text search filter with parentheses for correct AND/OR precedence."""
        filter_str = _build_filter(Filter(text_search="error"))
        # Verify parentheses wrap the OR expression
        assert '(textPayload:"error" OR jsonPayload:"error")' in filter_str

    def test_text_search_escapes_quotes(self) -> None:
        """Test that quotes in text search are escaped."""
        filter_str = _build_filter(Filter(text_search='test "quoted"'))
        assert 'textPayload:"test \\"quoted\\""' in filter_str

    def test_log_name_filter(self) -> None:
        """Test building log name filter."""
        filter_str = _build_filter(Filter(), log_name="my-log")
        assert 'logName="my-log"' in filter_str

    def test_resource_type_filter(self) -> None:
        """Test building resource type filter."""
        filter_str = _build_filter(Filter(), resource_type="gce_instance")
        assert 'resource.type="gce_instance"' in filter_str

    def test_combined_filters(self) -> None:
        """Test building combined filters."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 2)
        log_filter = Filter(
            time_range=TimeRange(start=start, end=end),
            severity=Severity.WARN,
            text_search="error",
        )
        filter_str = _build_filter(
            log_filter,
            log_name="my-log",
            resource_type="gce_instance",
        )
        assert "timestamp >=" in filter_str
        assert "timestamp <=" in filter_str
        assert "severity >= WARNING" in filter_str
        assert 'logName="my-log"' in filter_str
        assert 'resource.type="gce_instance"' in filter_str
        assert "textPayload:" in filter_str

    def test_fields_filter(self) -> None:
        """Test filter fields from Filter.fields."""
        log_filter = Filter(
            fields={"log_name": "custom-log", "resource_type": "k8s_container"}
        )
        filter_str = _build_filter(log_filter)
        assert 'logName="custom-log"' in filter_str
        assert 'resource.type="k8s_container"' in filter_str

    def test_text_search_escapes_backslashes(self) -> None:
        """Test that backslashes in text search are escaped before quotes."""
        # Backslash followed by quote: test\"data
        filter_str = _build_filter(Filter(text_search='test\\"data'))
        # Should produce: test\\"data (backslash escaped, then quote escaped)
        assert 'textPayload:"test\\\\\\"data"' in filter_str

    def test_text_search_escapes_backslash_only(self) -> None:
        """Test that lone backslashes are escaped."""
        filter_str = _build_filter(Filter(text_search="path\\to\\file"))
        # Each backslash should be doubled
        assert 'textPayload:"path\\\\to\\\\file"' in filter_str

    def test_fields_skipped_when_params_provided(self) -> None:
        """Test that fields are skipped when parameters already provide log_name/resource_type."""
        log_filter = Filter(
            fields={"log_name": "field-log", "resource_type": "field-resource"}
        )
        # When parameters are provided, they take precedence and fields are skipped
        filter_str = _build_filter(log_filter, log_name="param-log", resource_type="param-resource")
        # Should only have param values, not field values (which would cause duplicate conditions)
        assert filter_str.count('logName=') == 1
        assert filter_str.count('resource.type=') == 1
        assert 'logName="param-log"' in filter_str
        assert 'resource.type="param-resource"' in filter_str
        assert 'logName="field-log"' not in filter_str
        assert 'resource.type="field-resource"' not in filter_str


class TestLogEntryParsing:
    """Tests for GCP log entry parsing."""

    def test_parse_text_payload(self) -> None:
        """Test parsing entry with text payload."""
        entry = MockLogEntry(
            text_payload="Test log message",
            severity="INFO",
        )
        result = _parse_log_entry(entry, "test-project")
        assert result.message == "Test log message"
        assert result.severity == Severity.INFO

    def test_parse_json_payload_with_message(self) -> None:
        """Test parsing entry with JSON payload containing message field."""
        entry = MockLogEntry(
            json_payload={"message": "JSON message", "extra": "data"},
        )
        result = _parse_log_entry(entry, "test-project")
        assert result.message == "JSON message"

    def test_parse_json_payload_with_msg(self) -> None:
        """Test parsing entry with JSON payload containing msg field."""
        entry = MockLogEntry(
            json_payload={"msg": "Short message", "level": "info"},
        )
        result = _parse_log_entry(entry, "test-project")
        assert result.message == "Short message"

    def test_parse_json_payload_no_message_field(self) -> None:
        """Test parsing entry with JSON payload without message field."""
        entry = MockLogEntry(
            json_payload={"data": "value", "count": 42},
        )
        result = _parse_log_entry(entry, "test-project")
        # Should stringify the entire payload
        assert "data" in result.message
        assert "value" in result.message

    def test_parse_severity_mapping(self) -> None:
        """Test severity mapping from GCP to internal model."""
        test_cases = [
            ("DEFAULT", Severity.DEBUG),
            ("DEBUG", Severity.DEBUG),
            ("INFO", Severity.INFO),
            ("NOTICE", Severity.INFO),
            ("WARNING", Severity.WARN),
            ("ERROR", Severity.ERROR),
            ("CRITICAL", Severity.CRITICAL),
            ("ALERT", Severity.CRITICAL),
            ("EMERGENCY", Severity.CRITICAL),
        ]
        for gcp_severity, expected in test_cases:
            entry = MockLogEntry(severity=gcp_severity, text_payload="test")
            result = _parse_log_entry(entry, "test-project")
            assert result.severity == expected, f"Failed for {gcp_severity}"

    def test_parse_timestamp_with_timezone(self) -> None:
        """Test parsing entry with timezone-aware timestamp."""
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        entry = MockLogEntry(timestamp=ts, text_payload="test")
        result = _parse_log_entry(entry, "test-project")
        # Should be converted to naive local time
        assert result.timestamp.tzinfo is None

    def test_parse_timestamp_none(self) -> None:
        """Test parsing entry with no timestamp."""
        entry = MockLogEntry(timestamp=None, text_payload="test")
        result = _parse_log_entry(entry, "test-project")
        # Should use current time
        assert result.timestamp is not None
        assert (datetime.now() - result.timestamp).total_seconds() < 5

    def test_parse_metadata_extraction(self) -> None:
        """Test metadata extraction from entry."""
        entry = MockLogEntry(
            text_payload="test",
            resource=MockResource(
                type="gce_instance",
                labels={"instance_id": "vm-123", "zone": "us-central1-a"},
            ),
            labels={"env": "prod"},
        )
        result = _parse_log_entry(entry, "test-project")
        assert result.metadata["project"] == "test-project"
        assert result.metadata["resource_type"] == "gce_instance"
        assert result.metadata["resource.instance_id"] == "vm-123"
        assert result.metadata["resource.zone"] == "us-central1-a"
        assert result.metadata["label.env"] == "prod"

    def test_parse_source_from_resource_labels(self) -> None:
        """Test source extraction from resource labels."""
        # Pod name takes priority
        entry = MockLogEntry(
            text_payload="test",
            resource=MockResource(labels={"pod_name": "my-pod"}),
        )
        result = _parse_log_entry(entry, "test-project")
        assert result.source == "my-pod"

        # Instance ID as fallback
        entry = MockLogEntry(
            text_payload="test",
            resource=MockResource(labels={"instance_id": "vm-123"}),
        )
        result = _parse_log_entry(entry, "test-project")
        assert result.source == "vm-123"


class TestGCPLogSource:
    """Tests for GCPLogSource class."""

    def test_name_property_default(self) -> None:
        """Test default name property."""
        client = MockLoggingClient()
        source = GCPLogSource(project_id="test-project-id", client=client)
        assert source.name == "GCP: test-project-id"

    def test_name_property_custom(self) -> None:
        """Test custom name property."""
        client = MockLoggingClient()
        source = GCPLogSource(
            project_id="test-project-id",
            name="Custom Name",
            client=client,
        )
        assert source.name == "Custom Name"

    def test_invalid_project_id_raises_error(self) -> None:
        """Test that invalid project ID raises error."""
        client = MockLoggingClient()
        with pytest.raises(GCPInvalidProjectError):
            GCPLogSource(project_id="INVALID", client=client)

    @pytest.mark.asyncio
    async def test_fetch_returns_entries(self) -> None:
        """Test fetch returns log entries."""
        entries = [
            MockLogEntry(text_payload="Message 1", severity="INFO"),
            MockLogEntry(text_payload="Message 2", severity="ERROR"),
        ]
        client = MockLoggingClient(entries=entries)
        source = GCPLogSource(project_id="test-project-id", client=client)

        results = []
        async for entry in source.fetch(Filter(limit=10)):
            results.append(entry)

        assert len(results) == 2
        assert results[0].message == "Message 1"
        assert results[1].message == "Message 2"

    @pytest.mark.asyncio
    async def test_fetch_respects_limit(self) -> None:
        """Test fetch respects the limit parameter."""
        entries = [
            MockLogEntry(text_payload=f"Message {i}")
            for i in range(10)
        ]
        client = MockLoggingClient(entries=entries)
        source = GCPLogSource(project_id="test-project-id", client=client)

        results = []
        async for entry in source.fetch(Filter(limit=3)):
            results.append(entry)

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_fetch_passes_filter_to_client(self) -> None:
        """Test fetch passes filter string to client."""
        client = MockLoggingClient(entries=[])
        source = GCPLogSource(
            project_id="test-project-id",
            log_name="my-log",
            resource_type="gce_instance",
            client=client,
        )

        log_filter = Filter(severity=Severity.ERROR, text_search="test")
        async for _ in source.fetch(log_filter):
            pass

        assert client.last_filter is not None
        assert "severity >= ERROR" in client.last_filter
        assert 'logName="my-log"' in client.last_filter
        assert 'resource.type="gce_instance"' in client.last_filter
        assert "textPayload:" in client.last_filter

    @pytest.mark.asyncio
    async def test_fetch_passes_resource_names_to_client(self) -> None:
        """Test fetch passes resource names to client."""
        client = MockLoggingClient(entries=[])
        source = GCPLogSource(project_id="my-project-123", client=client)

        async for _ in source.fetch(Filter()):
            pass

        assert client.last_resource_names == ["projects/my-project-123"]

    def test_validate_filter_valid(self) -> None:
        """Test validate_filter with valid filter."""
        client = MockLoggingClient()
        source = GCPLogSource(project_id="test-project-id", client=client)
        errors = source.validate_filter(Filter(limit=100))
        assert errors == []

    def test_validate_filter_valid_limits(self) -> None:
        """Test validate_filter with valid limit values."""
        client = MockLoggingClient()
        source = GCPLogSource(project_id="test-project-id", client=client)
        # Note: Filter already validates limits at construction time,
        # so validate_filter just confirms it's valid for GCP
        errors = source.validate_filter(Filter(limit=1))
        assert errors == []
        errors = source.validate_filter(Filter(limit=10000))
        assert errors == []

    def test_validate_filter_valid_time_range(self) -> None:
        """Test validate_filter with valid time range."""
        client = MockLoggingClient()
        source = GCPLogSource(project_id="test-project-id", client=client)
        time_range = TimeRange(
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 2),
        )
        errors = source.validate_filter(Filter(time_range=time_range))
        assert errors == []

    def test_available_filters(self) -> None:
        """Test available_filters returns expected fields."""
        client = MockLoggingClient()
        source = GCPLogSource(project_id="test-project-id", client=client)
        filters = source.available_filters()

        field_names = [f.name for f in filters]
        assert "project" in field_names
        assert "log_name" in field_names
        assert "resource_type" in field_names
        assert "severity" in field_names

        # Check resource_type has options
        resource_field = next(f for f in filters if f.name == "resource_type")
        assert resource_field.options is not None
        assert "gce_instance" in resource_field.options
        assert "k8s_container" in resource_field.options


class TestGCPErrors:
    """Tests for GCP error classes."""

    def test_not_installed_error_message(self) -> None:
        """Test GCPNotInstalledError message."""
        error = GCPNotInstalledError()
        assert "google-cloud-logging" in str(error)
        assert "pip install logview[gcp]" in str(error)

    def test_authentication_error_default_message(self) -> None:
        """Test GCPAuthenticationError default message."""
        error = GCPAuthenticationError()
        assert "gcloud auth application-default login" in str(error)

    def test_authentication_error_custom_message(self) -> None:
        """Test GCPAuthenticationError custom message."""
        error = GCPAuthenticationError("Custom auth error")
        assert str(error) == "Custom auth error"

    def test_permission_error_message(self) -> None:
        """Test GCPPermissionError message."""
        error = GCPPermissionError("my-project")
        assert "my-project" in str(error)
        assert "Permission denied" in str(error)

    def test_project_not_found_error_message(self) -> None:
        """Test GCPProjectNotFoundError message."""
        error = GCPProjectNotFoundError("missing-project")
        assert "missing-project" in str(error)
        assert "not found" in str(error)

    def test_quota_exceeded_error_message(self) -> None:
        """Test GCPQuotaExceededError message."""
        error = GCPQuotaExceededError()
        assert "quota exceeded" in str(error).lower()

    def test_invalid_project_error_message(self) -> None:
        """Test GCPInvalidProjectError message."""
        error = GCPInvalidProjectError("BAD_ID")
        assert "BAD_ID" in str(error)
        assert "Invalid project ID" in str(error)


class TestGCPNotInstalled:
    """Tests for when google-cloud-logging is not installed."""

    def test_source_without_client_raises_not_installed(self) -> None:
        """Test that creating source without client raises GCPNotInstalledError."""
        # This test only makes sense when GCP is not available
        if GCP_AVAILABLE:
            pytest.skip("GCP is installed, skipping not-installed test")

        with pytest.raises(GCPNotInstalledError):
            GCPLogSource(project_id="test-project-id")

    def test_source_with_mock_client_works(self) -> None:
        """Test that source with mock client works even without GCP installed."""
        client = MockLoggingClient()
        source = GCPLogSource(project_id="test-project-id", client=client)
        assert source.name == "GCP: test-project-id"
