"""Unit tests for GKE Kubernetes log adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest

from logview.adapters.gcp import GCP_AVAILABLE
from logview.adapters.gke import (
    GKEClusterNotFoundError,
    GKEError,
    GKEInvalidFilterError,
    GKELogSource,
    _build_gke_filter,
    _build_source_filter_gke,
    _parse_gke_log_entry,
    _validate_cluster_name,
    _validate_namespace,
)
from logview.domain.models import Filter, Severity, TimeRange


# Mock classes for testing (reuse pattern from GCP tests)
@dataclass
class MockResource:
    """Mock GCP resource for GKE logs."""

    type: str = "k8s_container"
    labels: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if self.labels is None:
            self.labels = {
                "project_id": "test-project",
                "cluster_name": "test-cluster",
                "namespace_name": "default",
                "pod_name": "test-pod-abc123",
                "container_name": "app",
                "location": "us-central1-a",
            }


@dataclass
class MockGKELogEntry:
    """Mock GCP log entry for GKE testing."""

    timestamp: datetime | None = None
    severity: str = "INFO"
    text_payload: str | None = None
    json_payload: dict[str, Any] | None = None
    payload: str | dict[str, Any] | None = None
    resource: MockResource | None = None
    log_name: str = "projects/test-project/logs/stdout"
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
    """Mock GCP logging client for GKE testing."""

    def __init__(
        self,
        entries: list[MockGKELogEntry] | None = None,
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
    ) -> list[MockGKELogEntry]:
        """Mock list_entries method."""
        self.last_filter = filter_
        self.last_order_by = order_by
        self.last_page_size = page_size
        self.last_resource_names = resource_names

        if self.error:
            raise self.error

        return self.entries


class TestClusterNameValidation:
    """Tests for cluster name validation."""

    def test_valid_cluster_names(self) -> None:
        """Test valid cluster name formats."""
        valid_names = [
            "a",  # Single char
            "my-cluster",
            "cluster-123",
            "prod-cluster-v2",
            "a1",  # Two chars
            "a" * 40,  # Max length
            "test-cluster-name",
            "cluster--double-hyphen",
        ]
        for name in valid_names:
            _validate_cluster_name(name)  # Should not raise

    def test_invalid_cluster_names(self) -> None:
        """Test invalid cluster name formats."""
        invalid_names = [
            ("My-Cluster", "uppercase"),
            ("my_cluster", "underscore"),
            ("1cluster", "starts with number"),
            ("cluster-", "ends with hyphen"),
            ("-cluster", "starts with hyphen"),
            ("a" * 41, "too long"),
            ("", "empty"),
        ]
        for name, _reason in invalid_names:
            with pytest.raises(GKEError):
                _validate_cluster_name(name)


class TestNamespaceValidation:
    """Tests for Kubernetes namespace validation."""

    def test_valid_namespaces(self) -> None:
        """Test valid namespace formats."""
        valid_namespaces = [
            "default",
            "kube-system",
            "my-namespace",
            "prod",
            "a",  # Single char
            "a1",
            "namespace-123",
            "a" * 63,  # Max length
        ]
        for ns in valid_namespaces:
            _validate_namespace(ns)  # Should not raise

    def test_invalid_namespaces(self) -> None:
        """Test invalid namespace formats."""
        invalid_namespaces = [
            ("My-Namespace", "uppercase"),
            ("my_namespace", "underscore"),
            ("-namespace", "starts with hyphen"),
            ("namespace-", "ends with hyphen"),
            ("a" * 64, "too long"),
            ("", "empty"),
        ]
        for ns, _reason in invalid_namespaces:
            with pytest.raises(GKEError):
                _validate_namespace(ns)


class TestGKEFilterBuilding:
    """Tests for GKE-specific Cloud Logging filter building."""

    def test_basic_filter(self) -> None:
        """Test basic GKE filter with required fields."""
        filter_str = _build_gke_filter(
            Filter(),
            project="test-project",
            cluster="my-cluster",
        )
        assert 'resource.type="k8s_container"' in filter_str
        assert 'resource.labels.project_id="test-project"' in filter_str
        assert 'resource.labels.cluster_name="my-cluster"' in filter_str

    def test_namespace_filter(self) -> None:
        """Test namespace filter from default_namespace."""
        filter_str = _build_gke_filter(
            Filter(),
            project="test-project",
            cluster="my-cluster",
            default_namespace="default",
        )
        assert 'resource.labels.namespace_name="default"' in filter_str

    def test_namespace_wildcard_filter(self) -> None:
        """Test namespace filter with wildcard."""
        filter_str = _build_gke_filter(
            Filter(fields={"namespace": "kube-*"}),
            project="test-project",
            cluster="my-cluster",
        )
        assert 'resource.labels.namespace_name=~"^kube\\-"' in filter_str

    def test_pod_filter(self) -> None:
        """Test pod name filter."""
        filter_str = _build_gke_filter(
            Filter(fields={"pod": "api-server-abc123"}),
            project="test-project",
            cluster="my-cluster",
        )
        assert 'resource.labels.pod_name="api-server-abc123"' in filter_str

    def test_pod_wildcard_filter(self) -> None:
        """Test pod name filter with wildcard."""
        filter_str = _build_gke_filter(
            Filter(fields={"pod": "api-server-*"}),
            project="test-project",
            cluster="my-cluster",
        )
        assert 'resource.labels.pod_name=~"^api\\-server\\-"' in filter_str

    def test_container_filter(self) -> None:
        """Test container name filter."""
        filter_str = _build_gke_filter(
            Filter(fields={"container": "nginx"}),
            project="test-project",
            cluster="my-cluster",
        )
        assert 'resource.labels.container_name="nginx"' in filter_str

    def test_labels_filter(self) -> None:
        """Test pod labels filter."""
        filter_str = _build_gke_filter(
            Filter(fields={"labels": "app=nginx,env=prod"}),
            project="test-project",
            cluster="my-cluster",
        )
        assert 'labels."k8s-pod/app"="nginx"' in filter_str
        assert 'labels."k8s-pod/env"="prod"' in filter_str

    def test_location_filter(self) -> None:
        """Test location/zone filter."""
        filter_str = _build_gke_filter(
            Filter(),
            project="test-project",
            cluster="my-cluster",
            location="us-central1-a",
        )
        assert 'resource.labels.location="us-central1-a"' in filter_str

    def test_severity_filter(self) -> None:
        """Test severity filter."""
        filter_str = _build_gke_filter(
            Filter(severity=Severity.ERROR),
            project="test-project",
            cluster="my-cluster",
        )
        assert "severity >= ERROR" in filter_str

    def test_time_range_filter(self) -> None:
        """Test time range filter with naive datetimes."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        end = datetime(2024, 1, 2, 0, 0, 0)
        time_range = TimeRange(start=start, end=end)
        filter_str = _build_gke_filter(
            Filter(time_range=time_range),
            project="test-project",
            cluster="my-cluster",
        )
        assert 'timestamp >= "2024-01-01T00:00:00Z"' in filter_str
        assert 'timestamp <= "2024-01-02T00:00:00Z"' in filter_str

    def test_text_search_filter(self) -> None:
        """Test text search filter."""
        filter_str = _build_gke_filter(
            Filter(text_search="error"),
            project="test-project",
            cluster="my-cluster",
        )
        assert '(textPayload:"error" OR jsonPayload:"error")' in filter_str

    def test_combined_filters(self) -> None:
        """Test combined filters."""
        filter_str = _build_gke_filter(
            Filter(
                severity=Severity.WARN,
                text_search="connection",
                fields={"namespace": "default", "pod": "api-*"},
            ),
            project="test-project",
            cluster="my-cluster",
            location="us-central1-a",
        )
        assert 'resource.type="k8s_container"' in filter_str
        assert 'resource.labels.namespace_name="default"' in filter_str
        assert 'resource.labels.pod_name=~"^api\\-"' in filter_str
        assert "severity >= WARNING" in filter_str
        assert "textPayload:" in filter_str

    def test_internal_wildcard_namespace_rejected(self) -> None:
        """Test that internal wildcards in namespace raise error."""
        with pytest.raises(GKEInvalidFilterError) as exc_info:
            _build_gke_filter(
                Filter(fields={"namespace": "kube-*-system"}),
                project="test-project",
                cluster="my-cluster",
            )
        assert "only trailing wildcards" in str(exc_info.value)

    def test_internal_wildcard_pod_rejected(self) -> None:
        """Test that internal wildcards in pod name raise error."""
        with pytest.raises(GKEInvalidFilterError) as exc_info:
            _build_gke_filter(
                Filter(fields={"pod": "api-*-server"}),
                project="test-project",
                cluster="my-cluster",
            )
        assert "only trailing wildcards" in str(exc_info.value)

    def test_non_trailing_wildcard_rejected(self) -> None:
        """Test that non-trailing wildcards raise error."""
        with pytest.raises(GKEInvalidFilterError) as exc_info:
            _build_gke_filter(
                Filter(fields={"namespace": "*-system"}),
                project="test-project",
                cluster="my-cluster",
            )
        assert "only trailing wildcards" in str(exc_info.value)

    def test_wildcard_only_namespace_rejected(self) -> None:
        """Test that wildcard-only namespace pattern raises error."""
        with pytest.raises(GKEInvalidFilterError) as exc_info:
            _build_gke_filter(
                Filter(fields={"namespace": "*"}),
                project="test-project",
                cluster="my-cluster",
            )
        assert "wildcard-only patterns are not allowed" in str(exc_info.value)

    def test_wildcard_only_pod_rejected(self) -> None:
        """Test that wildcard-only pod pattern raises error."""
        with pytest.raises(GKEInvalidFilterError) as exc_info:
            _build_gke_filter(
                Filter(fields={"pod": "*"}),
                project="test-project",
                cluster="my-cluster",
            )
        assert "wildcard-only patterns are not allowed" in str(exc_info.value)

    def test_labels_invalid_pair_ignored(self) -> None:
        """Test that label pairs without = are ignored."""
        filter_str = _build_gke_filter(
            Filter(fields={"labels": "app=nginx,invalid-label,env=prod"}),
            project="test-project",
            cluster="my-cluster",
        )
        # Valid labels should be present
        assert 'labels."k8s-pod/app"="nginx"' in filter_str
        assert 'labels."k8s-pod/env"="prod"' in filter_str
        # Invalid label should NOT be present
        assert "invalid-label" not in filter_str

    def test_labels_empty_key_ignored(self) -> None:
        """Test that empty label keys are ignored."""
        filter_str = _build_gke_filter(
            Filter(fields={"labels": "=value,app=nginx"}),
            project="test-project",
            cluster="my-cluster",
        )
        # Valid label should be present
        assert 'labels."k8s-pod/app"="nginx"' in filter_str
        # Empty key should NOT create a filter
        assert 'labels."k8s-pod/"' not in filter_str

    def test_empty_text_search_ignored(self) -> None:
        """Test that empty/whitespace text search is ignored."""
        filter_str = _build_gke_filter(
            Filter(text_search="   "),
            project="test-project",
            cluster="my-cluster",
        )
        # Should NOT contain text search filter
        assert "textPayload" not in filter_str
        assert "jsonPayload" not in filter_str

    def test_labels_trailing_comma_handled(self) -> None:
        """Test that trailing commas in labels are handled."""
        filter_str = _build_gke_filter(
            Filter(fields={"labels": "app=nginx,"}),
            project="test-project",
            cluster="my-cluster",
        )
        assert 'labels."k8s-pod/app"="nginx"' in filter_str

    def test_labels_special_chars_escaped(self) -> None:
        """Test that special characters in label values are escaped."""
        filter_str = _build_gke_filter(
            Filter(fields={"labels": 'app="quoted",path=back\\slash'}),
            project="test-project",
            cluster="my-cluster",
        )
        # Quotes and backslashes should be escaped
        assert 'labels."k8s-pod/app"="\\"quoted\\""' in filter_str
        assert 'labels."k8s-pod/path"="back\\\\slash"' in filter_str


class TestGKELogEntryParsing:
    """Tests for GKE log entry parsing."""

    def test_parse_text_payload(self) -> None:
        """Test parsing entry with text payload."""
        entry = MockGKELogEntry(
            text_payload="Test log message",
            severity="INFO",
        )
        result = _parse_gke_log_entry(entry, "test-cluster")
        assert result.message == "Test log message"
        assert result.severity == Severity.INFO

    def test_parse_json_payload_with_message(self) -> None:
        """Test parsing entry with JSON payload containing message field."""
        entry = MockGKELogEntry(
            json_payload={"message": "JSON message", "extra": "data"},
        )
        result = _parse_gke_log_entry(entry, "test-cluster")
        assert result.message == "JSON message"

    def test_parse_json_payload_with_log_field(self) -> None:
        """Test parsing entry with JSON payload containing log field (common in k8s)."""
        entry = MockGKELogEntry(
            json_payload={"log": "Container log line", "stream": "stdout"},
        )
        result = _parse_gke_log_entry(entry, "test-cluster")
        assert result.message == "Container log line"

    def test_parse_payload_property(self) -> None:
        """Test parsing entry using payload property."""
        entry = MockGKELogEntry(
            payload="Direct payload message",
        )
        result = _parse_gke_log_entry(entry, "test-cluster")
        assert result.message == "Direct payload message"

    def test_parse_source_with_namespace_and_pod(self) -> None:
        """Test source extraction includes namespace/pod."""
        entry = MockGKELogEntry(
            text_payload="test",
            resource=MockResource(
                labels={
                    "namespace_name": "prod",
                    "pod_name": "api-server-xyz",
                    "container_name": "app",
                }
            ),
        )
        result = _parse_gke_log_entry(entry, "test-cluster")
        assert result.source == "prod/api-server-xyz"

    def test_parse_source_with_pod_only(self) -> None:
        """Test source extraction with just pod name."""
        entry = MockGKELogEntry(
            text_payload="test",
            resource=MockResource(
                labels={"pod_name": "standalone-pod"}
            ),
        )
        result = _parse_gke_log_entry(entry, "test-cluster")
        assert result.source == "standalone-pod"

    def test_parse_source_fallback_to_cluster(self) -> None:
        """Test source fallback to cluster name."""
        entry = MockGKELogEntry(
            text_payload="test",
            resource=MockResource(labels={}),
        )
        result = _parse_gke_log_entry(entry, "my-cluster")
        assert result.source == "my-cluster"

    def test_parse_metadata_extraction(self) -> None:
        """Test metadata extraction from GKE entry."""
        entry = MockGKELogEntry(
            text_payload="test",
            resource=MockResource(
                labels={
                    "namespace_name": "default",
                    "pod_name": "my-pod",
                    "container_name": "app",
                    "location": "us-central1-a",
                }
            ),
            labels={"k8s-pod/app": "nginx", "k8s-pod/version": "1.0"},
        )
        result = _parse_gke_log_entry(entry, "test-cluster")
        assert result.metadata["cluster"] == "test-cluster"
        assert result.metadata["namespace"] == "default"
        assert result.metadata["pod"] == "my-pod"
        assert result.metadata["container"] == "app"
        assert result.metadata["location"] == "us-central1-a"
        # Pod labels should have k8s-pod/ prefix removed
        assert result.metadata["label.app"] == "nginx"
        assert result.metadata["label.version"] == "1.0"

    def test_parse_timestamp_conversion(self) -> None:
        """Test timestamp conversion from timezone-aware to naive."""
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        entry = MockGKELogEntry(timestamp=ts, text_payload="test")
        result = _parse_gke_log_entry(entry, "test-cluster")
        assert result.timestamp.tzinfo is None

    def test_parse_severity_mapping(self) -> None:
        """Test severity mapping from GCP to internal model."""
        test_cases = [
            ("DEBUG", Severity.DEBUG),
            ("INFO", Severity.INFO),
            ("WARNING", Severity.WARN),
            ("ERROR", Severity.ERROR),
            ("CRITICAL", Severity.CRITICAL),
        ]
        for gcp_severity, expected in test_cases:
            entry = MockGKELogEntry(severity=gcp_severity, text_payload="test")
            result = _parse_gke_log_entry(entry, "test-cluster")
            assert result.severity == expected, f"Failed for {gcp_severity}"


class TestGKELogSource:
    """Tests for GKELogSource class."""

    def test_name_property_default(self) -> None:
        """Test default name property."""
        client = MockLoggingClient()
        source = GKELogSource(
            project_id="test-project-id",
            cluster="my-cluster",
            client=client,
        )
        assert source.name == "GKE: my-cluster"

    def test_name_property_with_namespace(self) -> None:
        """Test name property with default namespace."""
        client = MockLoggingClient()
        source = GKELogSource(
            project_id="test-project-id",
            cluster="my-cluster",
            default_namespace="default",
            client=client,
        )
        assert source.name == "GKE: my-cluster/default"

    def test_name_property_custom(self) -> None:
        """Test custom name property."""
        client = MockLoggingClient()
        source = GKELogSource(
            project_id="test-project-id",
            cluster="my-cluster",
            name="Production Cluster",
            client=client,
        )
        assert source.name == "Production Cluster"

    def test_invalid_project_id_raises_error(self) -> None:
        """Test that invalid project ID raises error."""
        from logview.adapters.gcp import GCPInvalidProjectError

        client = MockLoggingClient()
        with pytest.raises(GCPInvalidProjectError):
            GKELogSource(
                project_id="INVALID",
                cluster="my-cluster",
                client=client,
            )

    def test_invalid_cluster_name_raises_error(self) -> None:
        """Test that invalid cluster name raises error."""
        client = MockLoggingClient()
        with pytest.raises(GKEError):
            GKELogSource(
                project_id="test-project-id",
                cluster="INVALID_CLUSTER",
                client=client,
            )

    def test_invalid_namespace_raises_error(self) -> None:
        """Test that invalid namespace raises error."""
        client = MockLoggingClient()
        with pytest.raises(GKEError):
            GKELogSource(
                project_id="test-project-id",
                cluster="my-cluster",
                default_namespace="INVALID_NS",
                client=client,
            )

    @pytest.mark.asyncio
    async def test_fetch_returns_entries(self) -> None:
        """Test fetch returns log entries."""
        entries = [
            MockGKELogEntry(text_payload="Message 1", severity="INFO"),
            MockGKELogEntry(text_payload="Message 2", severity="ERROR"),
        ]
        client = MockLoggingClient(entries=entries)
        source = GKELogSource(
            project_id="test-project-id",
            cluster="my-cluster",
            client=client,
        )

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
            MockGKELogEntry(text_payload=f"Message {i}")
            for i in range(10)
        ]
        client = MockLoggingClient(entries=entries)
        source = GKELogSource(
            project_id="test-project-id",
            cluster="my-cluster",
            client=client,
        )

        results = []
        async for entry in source.fetch(Filter(limit=3)):
            results.append(entry)

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_fetch_passes_gke_filter_to_client(self) -> None:
        """Test fetch passes GKE-specific filter to client."""
        client = MockLoggingClient(entries=[])
        source = GKELogSource(
            project_id="test-project-id",
            cluster="my-cluster",
            location="us-central1-a",
            default_namespace="default",
            client=client,
        )

        log_filter = Filter(severity=Severity.ERROR, text_search="error")
        async for _ in source.fetch(log_filter):
            pass

        assert client.last_filter is not None
        assert 'resource.type="k8s_container"' in client.last_filter
        assert 'resource.labels.cluster_name="my-cluster"' in client.last_filter
        assert 'resource.labels.location="us-central1-a"' in client.last_filter
        assert 'resource.labels.namespace_name="default"' in client.last_filter
        assert "severity >= ERROR" in client.last_filter

    @pytest.mark.asyncio
    async def test_fetch_passes_resource_names_to_client(self) -> None:
        """Test fetch passes resource names to client."""
        client = MockLoggingClient(entries=[])
        source = GKELogSource(
            project_id="my-project-123",
            cluster="my-cluster",
            client=client,
        )

        async for _ in source.fetch(Filter()):
            pass

        assert client.last_resource_names == ["projects/my-project-123"]

    @pytest.mark.asyncio
    async def test_fetch_applies_source_filter(self) -> None:
        """Test fetch applies source_filter client-side."""
        entries = [
            MockGKELogEntry(
                text_payload="API log",
                resource=MockResource(labels={
                    "project_id": "test-project",
                    "cluster_name": "test-cluster",
                    "namespace_name": "default",
                    "pod_name": "api-server-abc123",
                    "container_name": "app",
                }),
            ),
            MockGKELogEntry(
                text_payload="Worker log",
                resource=MockResource(labels={
                    "project_id": "test-project",
                    "cluster_name": "test-cluster",
                    "namespace_name": "default",
                    "pod_name": "worker-def456",
                    "container_name": "app",
                }),
            ),
            MockGKELogEntry(
                text_payload="Another API log",
                resource=MockResource(labels={
                    "project_id": "test-project",
                    "cluster_name": "test-cluster",
                    "namespace_name": "production",
                    "pod_name": "api-gateway-xyz789",
                    "container_name": "app",
                }),
            ),
        ]
        client = MockLoggingClient(entries=entries)
        source = GKELogSource(
            project_id="test-project",
            cluster="test-cluster",
            client=client,
        )

        # Filter by source containing "api"
        results = []
        async for entry in source.fetch(Filter(source_filter="api", limit=10)):
            results.append(entry)

        # Should only get entries with "api" in source (default/api-server and production/api-gateway)
        assert len(results) == 2
        assert "api" in results[0].source.lower()
        assert "api" in results[1].source.lower()

    def test_validate_filter_valid(self) -> None:
        """Test validate_filter with valid filter."""
        client = MockLoggingClient()
        source = GKELogSource(
            project_id="test-project-id",
            cluster="my-cluster",
            client=client,
        )
        errors = source.validate_filter(Filter(limit=100))
        assert errors == []

    def test_validate_filter_invalid_namespace(self) -> None:
        """Test validate_filter with invalid namespace in fields."""
        client = MockLoggingClient()
        source = GKELogSource(
            project_id="test-project-id",
            cluster="my-cluster",
            client=client,
        )
        errors = source.validate_filter(Filter(fields={"namespace": "INVALID_NS"}))
        assert len(errors) == 1
        assert "namespace" in errors[0].lower()

    def test_validate_filter_wildcard_namespace_allowed(self) -> None:
        """Test validate_filter allows valid wildcard namespace."""
        client = MockLoggingClient()
        source = GKELogSource(
            project_id="test-project-id",
            cluster="my-cluster",
            client=client,
        )
        errors = source.validate_filter(Filter(fields={"namespace": "kube-*"}))
        assert errors == []

    def test_validate_filter_rejects_wildcard_only_namespace(self) -> None:
        """Test validate_filter rejects wildcard-only namespace."""
        client = MockLoggingClient()
        source = GKELogSource(
            project_id="test-project-id",
            cluster="my-cluster",
            client=client,
        )
        errors = source.validate_filter(Filter(fields={"namespace": "*"}))
        assert len(errors) == 1
        assert "wildcard-only" in errors[0].lower()

    def test_validate_filter_rejects_internal_wildcard_namespace(self) -> None:
        """Test validate_filter rejects internal wildcard in namespace."""
        client = MockLoggingClient()
        source = GKELogSource(
            project_id="test-project-id",
            cluster="my-cluster",
            client=client,
        )
        errors = source.validate_filter(Filter(fields={"namespace": "kube-*-system"}))
        assert len(errors) == 1
        assert "trailing wildcards" in errors[0].lower()

    def test_validate_filter_rejects_non_trailing_wildcard_namespace(self) -> None:
        """Test validate_filter rejects non-trailing wildcard in namespace."""
        client = MockLoggingClient()
        source = GKELogSource(
            project_id="test-project-id",
            cluster="my-cluster",
            client=client,
        )
        errors = source.validate_filter(Filter(fields={"namespace": "*-system"}))
        assert len(errors) == 1
        assert "trailing wildcards" in errors[0].lower()

    def test_validate_filter_rejects_invalid_wildcard_pod(self) -> None:
        """Test validate_filter rejects invalid wildcard in pod."""
        client = MockLoggingClient()
        source = GKELogSource(
            project_id="test-project-id",
            cluster="my-cluster",
            client=client,
        )
        errors = source.validate_filter(Filter(fields={"pod": "api-*-server"}))
        assert len(errors) == 1
        assert "pod" in errors[0].lower()

    def test_available_filters(self) -> None:
        """Test available_filters returns expected fields."""
        client = MockLoggingClient()
        source = GKELogSource(
            project_id="test-project-id",
            cluster="my-cluster",
            client=client,
        )
        filters = source.available_filters()

        field_names = [f.name for f in filters]
        assert "cluster" in field_names
        assert "namespace" in field_names
        assert "pod" in field_names
        assert "container" in field_names
        assert "labels" in field_names
        assert "severity" in field_names

        # Check cluster is required
        cluster_field = next(f for f in filters if f.name == "cluster")
        assert cluster_field.required is True


class TestGKEErrors:
    """Tests for GKE error classes."""

    def test_gke_error_message(self) -> None:
        """Test GKEError message."""
        error = GKEError("Test error")
        assert str(error) == "Test error"

    def test_cluster_not_found_error_message(self) -> None:
        """Test GKEClusterNotFoundError message."""
        error = GKEClusterNotFoundError("my-cluster", "my-project")
        assert "my-cluster" in str(error)
        assert "my-project" in str(error)
        assert "No logs found" in str(error)


class TestGKENotInstalled:
    """Tests for when google-cloud-logging is not installed."""

    def test_source_without_client_raises_not_installed(self) -> None:
        """Test that creating source without client raises error when GCP not available."""
        if GCP_AVAILABLE:
            pytest.skip("GCP is installed, skipping not-installed test")

        from logview.adapters.gcp import GCPNotInstalledError

        with pytest.raises(GCPNotInstalledError):
            GKELogSource(
                project_id="test-project-id",
                cluster="my-cluster",
            )

    def test_source_with_mock_client_works(self) -> None:
        """Test that source with mock client works even without GCP installed."""
        client = MockLoggingClient()
        source = GKELogSource(
            project_id="test-project-id",
            cluster="my-cluster",
            client=client,
        )
        assert source.name == "GKE: my-cluster"


class TestGKESourceFiltering:
    """Tests for server-side source filtering in GKE adapter."""

    def test_source_filter_namespace_pod(self) -> None:
        """Test namespace/pod format."""
        log_filter = Filter(source_filter="default/api-server")
        filter_str, needs_client = _build_gke_filter(
            log_filter,
            project="test-project",
            cluster="test-cluster",
        )
        assert 'resource.labels.namespace_name="default"' in filter_str
        assert 'resource.labels.pod_name=~"^api\\-server"' in filter_str
        assert needs_client is True  # Added wildcard for substring

    def test_source_filter_namespace_pod_explicit_wildcard(self) -> None:
        """Test namespace/pod format with explicit wildcard."""
        log_filter = Filter(source_filter="default/api-*")
        filter_str, needs_client = _build_gke_filter(
            log_filter,
            project="test-project",
            cluster="test-cluster",
        )
        assert 'resource.labels.namespace_name="default"' in filter_str
        assert 'resource.labels.pod_name=~"^api\\-"' in filter_str
        assert needs_client is False  # Explicit wildcard, no client-side needed

    def test_source_filter_pod_only(self) -> None:
        """Test pod-only format."""
        log_filter = Filter(source_filter="api")
        filter_str, needs_client = _build_gke_filter(
            log_filter,
            project="test-project",
            cluster="test-cluster",
        )
        assert 'resource.labels.pod_name=~"^api"' in filter_str
        assert needs_client is True  # Added wildcard for prefix matching

    def test_source_filter_pod_only_explicit_wildcard(self) -> None:
        """Test pod-only format with explicit wildcard."""
        log_filter = Filter(source_filter="api-*")
        filter_str, needs_client = _build_gke_filter(
            log_filter,
            project="test-project",
            cluster="test-cluster",
        )
        assert 'resource.labels.pod_name=~"^api\\-"' in filter_str
        assert needs_client is False  # Explicit wildcard, server-side is sufficient

    def test_source_filter_wildcard_in_namespace_falls_back(self) -> None:
        """Test wildcard in namespace falls back."""
        log_filter = Filter(source_filter="prod-*/api")
        filter_str, needs_client = _build_gke_filter(
            log_filter,
            project="test-project",
            cluster="test-cluster",
        )
        assert "namespace_name" not in filter_str or 'resource.labels.namespace_name=' not in filter_str
        assert needs_client is True

    def test_source_filter_mid_wildcard_falls_back(self) -> None:
        """Test mid-string wildcard falls back."""
        log_filter = Filter(source_filter="api-*-server")
        filter_str, needs_client = _build_gke_filter(
            log_filter,
            project="test-project",
            cluster="test-cluster",
        )
        # Should not add source filter
        assert needs_client is True

    def test_no_source_filter_returns_false(self) -> None:
        """Test no source filter returns client_side_needed=False."""
        log_filter = Filter()
        filter_str, needs_client = _build_gke_filter(
            log_filter,
            project="test-project",
            cluster="test-cluster",
        )
        assert needs_client is False

    def test_build_source_filter_gke_empty(self) -> None:
        """Test _build_source_filter_gke with empty string."""
        parts, needs_client = _build_source_filter_gke("")
        assert parts == []
        assert needs_client is False

    def test_build_source_filter_gke_namespace_slash_pod(self) -> None:
        """Test _build_source_filter_gke with namespace/pod format."""
        parts, needs_client = _build_source_filter_gke("kube-system/coredns-*")
        assert len(parts) == 2
        assert 'resource.labels.namespace_name="kube-system"' in parts
        assert any("coredns" in p for p in parts)
        assert needs_client is False  # Explicit wildcard

    @pytest.mark.asyncio
    async def test_fetch_with_source_filter_includes_in_api_call(self) -> None:
        """Test source_filter passed to API."""
        client = MockLoggingClient(entries=[])
        source = GKELogSource(
            project_id="test-project",
            cluster="test-cluster",
            client=client,
        )

        async for _ in source.fetch(Filter(source_filter="default/api", limit=10)):
            pass

        assert 'resource.labels.namespace_name="default"' in client.last_filter
        assert 'resource.labels.pod_name=~"^api"' in client.last_filter

    @pytest.mark.asyncio
    async def test_hybrid_filtering_cluster_sources(self) -> None:
        """Test client-side handles cluster-level sources."""
        entries = [
            MockGKELogEntry(
                text_payload="pod log",
                resource=MockResource(
                    labels={
                        "project_id": "test-project",
                        "cluster_name": "test-cluster",
                        "namespace_name": "default",
                        "pod_name": "api-server-abc123",
                        "container_name": "app",
                    }
                ),
            ),
            MockGKELogEntry(
                text_payload="different pod",
                resource=MockResource(
                    labels={
                        "project_id": "test-project",
                        "cluster_name": "test-cluster",
                        "namespace_name": "default",
                        "pod_name": "worker-def456",
                        "container_name": "app",
                    }
                ),
            ),
        ]
        client = MockLoggingClient(entries=entries)
        source = GKELogSource(
            project_id="test-project",
            cluster="test-cluster",
            client=client,
        )

        results = []
        async for entry in source.fetch(Filter(source_filter="api", limit=10)):
            results.append(entry)

        # Only the api-server pod should match
        assert len(results) == 1
        assert "api" in results[0].source.lower()
