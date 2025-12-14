"""Integration tests for GKE Kubernetes log adapter.

These tests require:
1. google-cloud-logging package installed: pip install logview[gcp]
2. GCP authentication configured: gcloud auth application-default login
3. A valid GKE cluster with workloads generating logs

To run these tests:
    GCP_TEST_PROJECT=my-project GKE_TEST_CLUSTER=my-cluster pytest tests/integration/test_gke.py -v

The tests are skipped by default in CI and when google-cloud-logging is not installed.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from logview.adapters.gcp import (
    GCP_AVAILABLE,
    GCPAuthenticationError,
    GCPNotInstalledError,
    GCPPermissionError,
    GCPProjectNotFoundError,
)
from logview.adapters.gke import (
    GKEError,
    GKELogSource,
)
from logview.domain.models import Filter, Severity

if TYPE_CHECKING:
    pass

# Skip all tests in this module if:
# 1. Running in CI (no GCP credentials available)
# 2. google-cloud-logging is not installed
# 3. GKE test environment variables not set
IS_CI = os.environ.get("CI", "false").lower() == "true"
GCP_PROJECT = os.environ.get("GCP_TEST_PROJECT", "")
GKE_CLUSTER = os.environ.get("GKE_TEST_CLUSTER", "")
GKE_LOCATION = os.environ.get("GKE_TEST_LOCATION", "")
GKE_NAMESPACE = os.environ.get("GKE_TEST_NAMESPACE", "default")

pytestmark = [
    pytest.mark.skipif(IS_CI, reason="GKE integration tests skipped in CI"),
    pytest.mark.skipif(not GCP_AVAILABLE, reason="google-cloud-logging not installed"),
    pytest.mark.skipif(not GCP_PROJECT, reason="GCP_TEST_PROJECT environment variable not set"),
    pytest.mark.skipif(not GKE_CLUSTER, reason="GKE_TEST_CLUSTER environment variable not set"),
]


class TestGKEIntegration:
    """Integration tests for GKELogSource with real GKE cluster."""

    def test_source_creation_with_valid_cluster(self) -> None:
        """Test creating a GKELogSource with a valid cluster."""
        source = GKELogSource(
            project_id=GCP_PROJECT,
            cluster=GKE_CLUSTER,
        )
        assert source.name == f"GKE: {GKE_CLUSTER}"

    def test_source_creation_with_namespace(self) -> None:
        """Test creating a GKELogSource with a default namespace."""
        source = GKELogSource(
            project_id=GCP_PROJECT,
            cluster=GKE_CLUSTER,
            default_namespace=GKE_NAMESPACE,
        )
        assert source.name == f"GKE: {GKE_CLUSTER}/{GKE_NAMESPACE}"

    def test_source_creation_with_location(self) -> None:
        """Test creating a GKELogSource with location."""
        if not GKE_LOCATION:
            pytest.skip("GKE_TEST_LOCATION not set")

        source = GKELogSource(
            project_id=GCP_PROJECT,
            cluster=GKE_CLUSTER,
            location=GKE_LOCATION,
        )
        assert source.name == f"GKE: {GKE_CLUSTER}"

    def test_source_creation_with_custom_name(self) -> None:
        """Test creating a GKELogSource with a custom name."""
        source = GKELogSource(
            project_id=GCP_PROJECT,
            cluster=GKE_CLUSTER,
            name="Production Cluster",
        )
        assert source.name == "Production Cluster"

    @pytest.mark.asyncio
    async def test_fetch_logs(self) -> None:
        """Test fetching logs from GKE (requires valid credentials and cluster)."""
        source = GKELogSource(
            project_id=GCP_PROJECT,
            cluster=GKE_CLUSTER,
        )
        log_filter = Filter(limit=5)

        entries = []
        async for entry in source.fetch(log_filter):
            entries.append(entry)
            if len(entries) >= 5:
                break

        # May return 0 entries if no logs in cluster, but should not error
        assert isinstance(entries, list)

    @pytest.mark.asyncio
    async def test_fetch_logs_with_namespace_filter(self) -> None:
        """Test fetching logs with namespace filter."""
        source = GKELogSource(
            project_id=GCP_PROJECT,
            cluster=GKE_CLUSTER,
            default_namespace=GKE_NAMESPACE,
        )
        log_filter = Filter(limit=5)

        entries = []
        async for entry in source.fetch(log_filter):
            entries.append(entry)

        # All entries should be from the specified namespace
        for entry in entries:
            assert entry.metadata.get("namespace") == GKE_NAMESPACE

    @pytest.mark.asyncio
    async def test_fetch_logs_with_severity_filter(self) -> None:
        """Test fetching logs with severity filter."""
        source = GKELogSource(
            project_id=GCP_PROJECT,
            cluster=GKE_CLUSTER,
        )
        log_filter = Filter(limit=5, severity=Severity.WARN)

        entries = []
        async for entry in source.fetch(log_filter):
            entries.append(entry)

        # All entries should be WARN or higher
        for entry in entries:
            assert entry.severity.value in ["WARN", "ERROR", "CRITICAL"]

    @pytest.mark.asyncio
    async def test_fetch_logs_with_text_search(self) -> None:
        """Test fetching logs with text search filter."""
        source = GKELogSource(
            project_id=GCP_PROJECT,
            cluster=GKE_CLUSTER,
        )
        log_filter = Filter(limit=5, text_search="error")

        entries = []
        async for entry in source.fetch(log_filter):
            entries.append(entry)

        # May return 0 entries if no matching logs, but should not error
        assert isinstance(entries, list)

    @pytest.mark.asyncio
    async def test_fetch_logs_with_pod_filter(self) -> None:
        """Test fetching logs with pod name filter."""
        source = GKELogSource(
            project_id=GCP_PROJECT,
            cluster=GKE_CLUSTER,
        )
        # Use wildcard to match any pod with common prefix
        log_filter = Filter(limit=5, fields={"pod": "kube-*"})

        entries = []
        async for entry in source.fetch(log_filter):
            entries.append(entry)

        # May return 0 entries, but should not error
        assert isinstance(entries, list)

    def test_validate_filter_valid(self) -> None:
        """Test filter validation with valid filter."""
        source = GKELogSource(
            project_id=GCP_PROJECT,
            cluster=GKE_CLUSTER,
        )
        log_filter = Filter(limit=100)
        errors = source.validate_filter(log_filter)
        assert errors == []

    def test_validate_filter_with_namespace(self) -> None:
        """Test filter validation with namespace field."""
        source = GKELogSource(
            project_id=GCP_PROJECT,
            cluster=GKE_CLUSTER,
        )
        log_filter = Filter(limit=100, fields={"namespace": "kube-system"})
        errors = source.validate_filter(log_filter)
        assert errors == []

    def test_validate_filter_with_wildcard_namespace(self) -> None:
        """Test filter validation with wildcard namespace."""
        source = GKELogSource(
            project_id=GCP_PROJECT,
            cluster=GKE_CLUSTER,
        )
        log_filter = Filter(limit=100, fields={"namespace": "kube-*"})
        errors = source.validate_filter(log_filter)
        assert errors == []

    def test_available_filters(self) -> None:
        """Test available_filters returns expected GKE fields."""
        source = GKELogSource(
            project_id=GCP_PROJECT,
            cluster=GKE_CLUSTER,
        )
        fields = source.available_filters()

        assert len(fields) >= 6
        field_names = [f.name for f in fields]
        assert "cluster" in field_names
        assert "namespace" in field_names
        assert "pod" in field_names
        assert "container" in field_names
        assert "labels" in field_names
        assert "severity" in field_names


class TestGKEInvalidCluster:
    """Tests for invalid cluster scenarios."""

    def test_invalid_cluster_name_format(self) -> None:
        """Test that invalid cluster name format raises error."""
        with pytest.raises(GKEError):
            GKELogSource(
                project_id=GCP_PROJECT,
                cluster="INVALID_CLUSTER_NAME",
            )

    def test_invalid_namespace_format(self) -> None:
        """Test that invalid namespace format raises error."""
        with pytest.raises(GKEError):
            GKELogSource(
                project_id=GCP_PROJECT,
                cluster=GKE_CLUSTER,
                default_namespace="INVALID_NAMESPACE",
            )

    @pytest.mark.asyncio
    async def test_nonexistent_project(self) -> None:
        """Test that nonexistent project raises error during fetch."""
        source = GKELogSource(
            project_id="nonexistent-project-12345",
            cluster="my-cluster",
        )
        log_filter = Filter(limit=1)

        with pytest.raises((GCPProjectNotFoundError, GCPPermissionError, GCPAuthenticationError)):
            async for _ in source.fetch(log_filter):
                pass


@pytest.mark.skipif(not GCP_AVAILABLE, reason="google-cloud-logging not installed")
class TestGKEErrorMessages:
    """Tests that verify error messages are helpful.

    These tests DON'T require GKE credentials and just test error formatting.
    They only require google-cloud-logging to be installed.
    """

    def test_gke_error_message(self) -> None:
        """Test GKEError has basic message."""
        error = GKEError("Test error")
        assert str(error) == "Test error"

    def test_gcp_not_installed_error_message(self) -> None:
        """Test GCPNotInstalledError has helpful message for GKE users."""
        error = GCPNotInstalledError()
        assert "pip install logview[gcp]" in str(error)

    def test_gcp_authentication_error_message(self) -> None:
        """Test GCPAuthenticationError has helpful message."""
        error = GCPAuthenticationError()
        assert "gcloud auth application-default login" in str(error)

    def test_gcp_permission_error_message(self) -> None:
        """Test GCPPermissionError has helpful message."""
        error = GCPPermissionError("my-project")
        assert "my-project" in str(error)
        assert "Logs Viewer" in str(error)
