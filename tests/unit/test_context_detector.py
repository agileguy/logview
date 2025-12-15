"""Unit tests for context detector."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

from logview.adapters.context_detector import (
    ContextDetector,
    DetectionNotInstalledError,
    DiscoveredCluster,
    DiscoveredContext,
    DiscoveredProject,
    merge_contexts,
    _context_matches,
)
from logview.config.schema import GCPContext, GKEContext, SyslogContext


class TestDiscoveredModels:
    """Test discovered data models."""

    def test_discovered_project(self):
        """Test DiscoveredProject model."""
        project = DiscoveredProject(
            project_id="my-project",
            display_name="My Project",
            state="ACTIVE",
        )
        assert project.project_id == "my-project"
        assert project.display_name == "My Project"
        assert project.state == "ACTIVE"

    def test_discovered_cluster(self):
        """Test DiscoveredCluster model."""
        cluster = DiscoveredCluster(
            name="my-cluster",
            project_id="my-project",
            location="us-central1-a",
            status="RUNNING",
        )
        assert cluster.name == "my-cluster"
        assert cluster.project_id == "my-project"
        assert cluster.location == "us-central1-a"
        assert cluster.status == "RUNNING"

    def test_discovered_context(self):
        """Test DiscoveredContext model."""
        ctx = DiscoveredContext(
            context_type="gcp",
            name="[detected] my-project",
            project="my-project",
        )
        assert ctx.context_type == "gcp"
        assert ctx.name == "[detected] my-project"
        assert ctx.project == "my-project"
        assert ctx.cluster is None
        assert ctx.location is None

    def test_discovered_context_gke(self):
        """Test DiscoveredContext model for GKE."""
        ctx = DiscoveredContext(
            context_type="gke",
            name="[detected] my-cluster (my-project)",
            project="my-project",
            cluster="my-cluster",
            location="us-central1-a",
        )
        assert ctx.context_type == "gke"
        assert ctx.project == "my-project"
        assert ctx.cluster == "my-cluster"
        assert ctx.location == "us-central1-a"


class TestContextMatching:
    """Test context matching logic."""

    def test_gcp_context_match(self):
        """Test matching GCP contexts."""
        discovered = DiscoveredContext(
            context_type="gcp",
            name="[detected] my-project",
            project="my-project",
        )
        existing = GCPContext(
            name="prod-logs",
            type="gcp",
            project="my-project",
        )
        assert _context_matches(discovered, existing)

    def test_gcp_context_no_match_different_project(self):
        """Test non-matching GCP contexts with different projects."""
        discovered = DiscoveredContext(
            context_type="gcp",
            name="[detected] my-project",
            project="my-project",
        )
        existing = GCPContext(
            name="other-logs",
            type="gcp",
            project="other-project",
        )
        assert not _context_matches(discovered, existing)

    def test_gke_context_match(self):
        """Test matching GKE contexts."""
        discovered = DiscoveredContext(
            context_type="gke",
            name="[detected] my-cluster (my-project)",
            project="my-project",
            cluster="my-cluster",
            location="us-central1-a",
        )
        existing = GKEContext(
            name="prod-gke",
            type="gke",
            project="my-project",
            cluster="my-cluster",
            location="us-central1-a",
        )
        assert _context_matches(discovered, existing)

    def test_gke_context_no_match_different_cluster(self):
        """Test non-matching GKE contexts with different clusters."""
        discovered = DiscoveredContext(
            context_type="gke",
            name="[detected] my-cluster (my-project)",
            project="my-project",
            cluster="my-cluster",
        )
        existing = GKEContext(
            name="other-gke",
            type="gke",
            project="my-project",
            cluster="other-cluster",
        )
        assert not _context_matches(discovered, existing)

    def test_different_types_no_match(self):
        """Test non-matching contexts with different types."""
        discovered = DiscoveredContext(
            context_type="gcp",
            name="[detected] my-project",
            project="my-project",
        )
        existing = SyslogContext(
            name="syslog",
            type="syslog",
            path="/var/log/syslog",
        )
        assert not _context_matches(discovered, existing)


class TestMergeContexts:
    """Test context merging logic."""

    def test_merge_with_no_existing(self):
        """Test merging when no existing contexts."""
        discovered = [
            DiscoveredContext(
                context_type="gcp",
                name="[detected] my-project",
                project="my-project",
            ),
        ]
        existing: list = []
        new_contexts = merge_contexts(discovered, existing)
        assert len(new_contexts) == 1
        assert isinstance(new_contexts[0], GCPContext)
        assert new_contexts[0].project == "my-project"

    def test_merge_skip_duplicates(self):
        """Test that duplicate contexts are skipped."""
        discovered = [
            DiscoveredContext(
                context_type="gcp",
                name="[detected] my-project",
                project="my-project",
            ),
        ]
        existing = [
            GCPContext(
                name="existing-project",
                type="gcp",
                project="my-project",
            ),
        ]
        new_contexts = merge_contexts(discovered, existing)
        assert len(new_contexts) == 0

    def test_merge_gke_contexts(self):
        """Test merging GKE contexts."""
        discovered = [
            DiscoveredContext(
                context_type="gke",
                name="[detected] cluster-1 (my-project)",
                project="my-project",
                cluster="cluster-1",
                location="us-central1-a",
            ),
            DiscoveredContext(
                context_type="gke",
                name="[detected] cluster-2 (my-project)",
                project="my-project",
                cluster="cluster-2",
                location="us-west1-b",
            ),
        ]
        existing: list = []
        new_contexts = merge_contexts(discovered, existing)
        assert len(new_contexts) == 2
        assert all(isinstance(ctx, GKEContext) for ctx in new_contexts)

    def test_merge_mixed_types(self):
        """Test merging GCP and GKE contexts together."""
        discovered = [
            DiscoveredContext(
                context_type="gcp",
                name="[detected] my-project",
                project="my-project",
            ),
            DiscoveredContext(
                context_type="gke",
                name="[detected] my-cluster (my-project)",
                project="my-project",
                cluster="my-cluster",
            ),
        ]
        existing: list = []
        new_contexts = merge_contexts(discovered, existing)
        assert len(new_contexts) == 2
        assert isinstance(new_contexts[0], GCPContext)
        assert isinstance(new_contexts[1], GKEContext)


class TestContextDetector:
    """Test ContextDetector class."""

    def test_init_without_libraries(self):
        """Test initialization fails without libraries."""
        with patch("logview.adapters.context_detector.DETECTION_AVAILABLE", False):
            with pytest.raises(DetectionNotInstalledError):
                ContextDetector()

    def test_init_with_clients(self):
        """Test initialization with provided clients."""
        projects_client = Mock()
        clusters_client = Mock()
        detector = ContextDetector(
            projects_client=projects_client,
            clusters_client=clusters_client,
        )
        assert detector._projects_client == projects_client
        assert detector._clusters_client == clusters_client

    def test_project_filtering_include(self):
        """Test project filtering with include patterns."""
        detector = ContextDetector(
            project_filter=["prod-*", "staging-*"],
            projects_client=Mock(),
            clusters_client=Mock(),
        )
        assert detector._matches_filter("prod-project-1")
        assert detector._matches_filter("staging-project-2")
        assert not detector._matches_filter("test-project")

    def test_project_filtering_skip(self):
        """Test project filtering with skip patterns."""
        detector = ContextDetector(
            skip_projects=["test-*", "temp-*"],
            projects_client=Mock(),
            clusters_client=Mock(),
        )
        assert not detector._matches_filter("test-project")
        assert not detector._matches_filter("temp-project")
        assert detector._matches_filter("prod-project")

    def test_project_filtering_skip_takes_precedence(self):
        """Test that skip patterns take precedence over include."""
        detector = ContextDetector(
            project_filter=["prod-*"],
            skip_projects=["prod-test-*"],
            projects_client=Mock(),
            clusters_client=Mock(),
        )
        assert detector._matches_filter("prod-project")
        assert not detector._matches_filter("prod-test-project")

    @pytest.mark.asyncio
    async def test_discover_projects(self):
        """Test project discovery."""
        # Mock project response
        mock_project = Mock()
        mock_project.project_id = "my-project"
        mock_project.display_name = "My Project"
        mock_project.state.name = "ACTIVE"

        projects_client = Mock()
        projects_client.search_projects.return_value = [mock_project]

        clusters_client = Mock()

        detector = ContextDetector(
            projects_client=projects_client,
            clusters_client=clusters_client,
        )

        projects = await detector.discover_projects()
        assert len(projects) == 1
        assert projects[0].project_id == "my-project"
        assert projects[0].display_name == "My Project"

    @pytest.mark.asyncio
    async def test_discover_clusters(self):
        """Test cluster discovery."""
        # Mock cluster response
        mock_cluster = Mock()
        mock_cluster.name = "my-cluster"
        mock_cluster.location = "us-central1-a"
        mock_cluster.status.name = "RUNNING"

        mock_response = Mock()
        mock_response.clusters = [mock_cluster]

        clusters_client = Mock()
        clusters_client.list_clusters.return_value = mock_response

        projects_client = Mock()

        detector = ContextDetector(
            projects_client=projects_client,
            clusters_client=clusters_client,
        )

        clusters = await detector.discover_clusters("my-project")
        assert len(clusters) == 1
        assert clusters[0].name == "my-cluster"
        assert clusters[0].project_id == "my-project"
        assert clusters[0].location == "us-central1-a"

    @pytest.mark.asyncio
    async def test_discover_all_contexts(self):
        """Test full context discovery."""
        # Mock project
        mock_project = Mock()
        mock_project.project_id = "my-project"
        mock_project.display_name = "My Project"
        mock_project.state.name = "ACTIVE"

        # Mock cluster
        mock_cluster = Mock()
        mock_cluster.name = "my-cluster"
        mock_cluster.location = "us-central1-a"
        mock_cluster.status.name = "RUNNING"

        mock_response = Mock()
        mock_response.clusters = [mock_cluster]

        projects_client = Mock()
        projects_client.search_projects.return_value = [mock_project]

        clusters_client = Mock()
        clusters_client.list_clusters.return_value = mock_response

        detector = ContextDetector(
            projects_client=projects_client,
            clusters_client=clusters_client,
        )

        contexts = await detector.discover()
        assert len(contexts) == 2  # 1 GCP + 1 GKE
        assert contexts[0].context_type == "gcp"
        assert contexts[0].project == "my-project"
        assert contexts[1].context_type == "gke"
        assert contexts[1].project == "my-project"
        assert contexts[1].cluster == "my-cluster"

    @pytest.mark.asyncio
    async def test_discover_with_cache(self):
        """Test that caching works."""
        mock_project = Mock()
        mock_project.project_id = "my-project"
        mock_project.display_name = "My Project"
        mock_project.state.name = "ACTIVE"

        projects_client = Mock()
        projects_client.search_projects.return_value = [mock_project]

        clusters_client = Mock()
        clusters_client.list_clusters.return_value = Mock(clusters=[])

        detector = ContextDetector(
            projects_client=projects_client,
            clusters_client=clusters_client,
            cache_ttl_seconds=60,
        )

        # First discovery
        contexts1 = await detector.discover()
        assert len(contexts1) == 1

        # Second discovery (should use cache)
        contexts2 = await detector.discover()
        assert len(contexts2) == 1

        # Verify search_projects was only called once (cached)
        assert projects_client.search_projects.call_count == 1

    @pytest.mark.asyncio
    async def test_discover_force_refresh(self):
        """Test that force_refresh bypasses cache."""
        mock_project = Mock()
        mock_project.project_id = "my-project"
        mock_project.display_name = "My Project"
        mock_project.state.name = "ACTIVE"

        projects_client = Mock()
        projects_client.search_projects.return_value = [mock_project]

        clusters_client = Mock()
        clusters_client.list_clusters.return_value = Mock(clusters=[])

        detector = ContextDetector(
            projects_client=projects_client,
            clusters_client=clusters_client,
            cache_ttl_seconds=60,
        )

        # First discovery
        await detector.discover()

        # Second discovery with force_refresh
        await detector.discover(force_refresh=True)

        # Verify search_projects was called twice
        assert projects_client.search_projects.call_count == 2

    @pytest.mark.asyncio
    async def test_discover_only_gcp(self):
        """Test discovery with only GCP contexts enabled."""
        mock_project = Mock()
        mock_project.project_id = "my-project"
        mock_project.display_name = "My Project"
        mock_project.state.name = "ACTIVE"

        projects_client = Mock()
        projects_client.search_projects.return_value = [mock_project]

        clusters_client = Mock()

        detector = ContextDetector(
            projects_client=projects_client,
            clusters_client=clusters_client,
            include_gcp_contexts=True,
            include_gke_contexts=False,
        )

        contexts = await detector.discover()
        assert len(contexts) == 1
        assert contexts[0].context_type == "gcp"

    @pytest.mark.asyncio
    async def test_discover_only_gke(self):
        """Test discovery with only GKE contexts enabled."""
        mock_project = Mock()
        mock_project.project_id = "my-project"
        mock_project.display_name = "My Project"
        mock_project.state.name = "ACTIVE"

        mock_cluster = Mock()
        mock_cluster.name = "my-cluster"
        mock_cluster.location = "us-central1-a"
        mock_cluster.status.name = "RUNNING"

        projects_client = Mock()
        projects_client.search_projects.return_value = [mock_project]

        clusters_client = Mock()
        clusters_client.list_clusters.return_value = Mock(clusters=[mock_cluster])

        detector = ContextDetector(
            projects_client=projects_client,
            clusters_client=clusters_client,
            include_gcp_contexts=False,
            include_gke_contexts=True,
        )

        contexts = await detector.discover()
        assert len(contexts) == 1
        assert contexts[0].context_type == "gke"
