"""Integration tests for GCP Cloud Logging adapter.

These tests require:
1. google-cloud-logging package installed: pip install logview-ag[gcp]
2. GCP authentication configured: gcloud auth application-default login
3. A valid GCP project with Cloud Logging API enabled

To run these tests:
    pytest tests/integration/test_gcp.py -v

The tests are skipped by default in CI and when google-cloud-logging is not installed.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from logview.adapters.gcp import (
    GCP_AVAILABLE,
    GCPAuthenticationError,
    GCPInvalidProjectError,
    GCPLogSource,
    GCPNotInstalledError,
    GCPPermissionError,
    GCPProjectNotFoundError,
)
from logview.domain.models import Filter

if TYPE_CHECKING:
    pass

# Skip all tests in this module if:
# 1. Running in CI (no GCP credentials available)
# 2. google-cloud-logging is not installed
IS_CI = os.environ.get("CI", "false").lower() == "true"
GCP_PROJECT = os.environ.get("GCP_TEST_PROJECT", "")

pytestmark = [
    pytest.mark.skipif(IS_CI, reason="GCP integration tests skipped in CI"),
    pytest.mark.skipif(not GCP_AVAILABLE, reason="google-cloud-logging not installed"),
    pytest.mark.skipif(not GCP_PROJECT, reason="GCP_TEST_PROJECT environment variable not set"),
]


class TestGCPIntegration:
    """Integration tests for GCPLogSource with real GCP credentials."""

    def test_source_creation_with_valid_project(self) -> None:
        """Test creating a GCPLogSource with a valid project ID."""
        source = GCPLogSource(project_id=GCP_PROJECT)
        assert source.name == f"GCP: {GCP_PROJECT}"

    def test_source_creation_with_custom_name(self) -> None:
        """Test creating a GCPLogSource with a custom name."""
        source = GCPLogSource(project_id=GCP_PROJECT, name="My Custom Name")
        assert source.name == "My Custom Name"

    def test_source_creation_with_log_name(self) -> None:
        """Test creating a GCPLogSource with a log name filter."""
        source = GCPLogSource(
            project_id=GCP_PROJECT,
            log_name="cloudaudit.googleapis.com%2Factivity",
        )
        assert source.name == f"GCP: {GCP_PROJECT}"

    def test_source_creation_with_resource_type(self) -> None:
        """Test creating a GCPLogSource with a resource type filter."""
        source = GCPLogSource(
            project_id=GCP_PROJECT,
            resource_type="gce_instance",
        )
        assert source.name == f"GCP: {GCP_PROJECT}"

    @pytest.mark.asyncio
    async def test_fetch_logs(self) -> None:
        """Test fetching logs from GCP (requires valid credentials)."""
        source = GCPLogSource(project_id=GCP_PROJECT)
        log_filter = Filter(limit=5)

        entries = []
        async for entry in source.fetch(log_filter):
            entries.append(entry)
            if len(entries) >= 5:
                break

        # May return 0 entries if no logs in project, but should not error
        assert isinstance(entries, list)

    @pytest.mark.asyncio
    async def test_fetch_logs_with_small_limit(self) -> None:
        """Test fetching logs with a small limit."""
        source = GCPLogSource(project_id=GCP_PROJECT)
        log_filter = Filter(limit=1)

        entries = []
        async for entry in source.fetch(log_filter):
            entries.append(entry)

        # Should return at most 1 entry
        assert len(entries) <= 1

    @pytest.mark.asyncio
    async def test_fetch_logs_with_text_search(self) -> None:
        """Test fetching logs with text search filter."""
        source = GCPLogSource(project_id=GCP_PROJECT)
        log_filter = Filter(limit=5, text_search="error")

        entries = []
        async for entry in source.fetch(log_filter):
            entries.append(entry)

        # May return 0 entries if no matching logs, but should not error
        assert isinstance(entries, list)

    def test_validate_filter_valid(self) -> None:
        """Test filter validation with valid filter."""
        source = GCPLogSource(project_id=GCP_PROJECT)
        log_filter = Filter(limit=100)
        errors = source.validate_filter(log_filter)
        assert errors == []

    def test_available_filters(self) -> None:
        """Test available_filters returns expected fields."""
        source = GCPLogSource(project_id=GCP_PROJECT)
        fields = source.available_filters()

        assert len(fields) >= 4
        field_names = [f.name for f in fields]
        assert "project" in field_names
        assert "log_name" in field_names
        assert "resource_type" in field_names
        assert "severity" in field_names


class TestGCPInvalidProject:
    """Tests for invalid project scenarios (skipped in CI)."""

    @pytest.mark.asyncio
    async def test_invalid_project_format(self) -> None:
        """Test that invalid project ID format raises error."""
        with pytest.raises(GCPInvalidProjectError):
            GCPLogSource(project_id="INVALID_PROJECT_ID")

    @pytest.mark.asyncio
    async def test_nonexistent_project(self) -> None:
        """Test that nonexistent project raises error during fetch."""
        # Use a valid format but nonexistent project
        source = GCPLogSource(project_id="nonexistent-project-12345")
        log_filter = Filter(limit=1)

        with pytest.raises((GCPProjectNotFoundError, GCPPermissionError, GCPAuthenticationError)):
            async for _ in source.fetch(log_filter):
                pass


@pytest.mark.skipif(not GCP_AVAILABLE, reason="google-cloud-logging not installed")
class TestGCPWithoutCredentials:
    """Tests that verify behavior without GCP credentials.

    These tests DON'T require GCP credentials and test error handling.
    They only require google-cloud-logging to be installed.
    """

    def test_gcp_not_installed_error_message(self) -> None:
        """Test GCPNotInstalledError has helpful message."""
        error = GCPNotInstalledError()
        assert "pip install logview-ag[gcp]" in str(error)

    def test_gcp_authentication_error_message(self) -> None:
        """Test GCPAuthenticationError has helpful message."""
        error = GCPAuthenticationError()
        assert "gcloud auth application-default login" in str(error)

    def test_gcp_permission_error_message(self) -> None:
        """Test GCPPermissionError has helpful message."""
        error = GCPPermissionError("my-project")
        assert "my-project" in str(error)
        assert "Logs Viewer" in str(error)

    def test_gcp_project_not_found_error_message(self) -> None:
        """Test GCPProjectNotFoundError has helpful message."""
        error = GCPProjectNotFoundError("my-project")
        assert "my-project" in str(error)

    def test_gcp_invalid_project_error_message(self) -> None:
        """Test GCPInvalidProjectError has helpful message."""
        error = GCPInvalidProjectError("BAD_ID")
        assert "BAD_ID" in str(error)
        assert "6-30 characters" in str(error)
