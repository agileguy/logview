"""Context detection for GCP projects and GKE clusters.

Automatically discovers accessible GCP projects and GKE clusters using
Application Default Credentials (ADC).

Requires optional dependencies:
    pip install logview-ag[detection]
"""

from __future__ import annotations

import asyncio
import fnmatch
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Protocol

from logview.config.schema import Context, GCPContext, GKEContext

logger = logging.getLogger("logview.adapters.context_detector")

if TYPE_CHECKING:
    pass


# Check if required libraries are available
DETECTION_AVAILABLE = False
_resourcemanager_client_class: Any = None
_container_client_class: Any = None
_google_exceptions: Any = None

try:
    from google.api_core import exceptions as google_exceptions
    from google.cloud import container_v1, resourcemanager_v3

    DETECTION_AVAILABLE = True
    _resourcemanager_client_class = resourcemanager_v3.ProjectsClient
    _container_client_class = container_v1.ClusterManagerClient
    _google_exceptions = google_exceptions
except ImportError:
    pass


# Error types
class ContextDetectionError(Exception):
    """Base exception for context detection errors."""

    pass


class DetectionNotInstalledError(ContextDetectionError):
    """Raised when required detection libraries are not installed."""

    def __init__(self) -> None:
        super().__init__(
            "Context detection requires additional dependencies. "
            "Install with: pip install logview-ag[detection]"
        )


class DetectionAuthenticationError(ContextDetectionError):
    """Raised when authentication fails."""

    def __init__(self, message: str | None = None) -> None:
        default_msg = (
            "Authentication failed for context detection. Please run:\n"
            "  gcloud auth application-default login"
        )
        super().__init__(message or default_msg)


class DetectionQuotaExceededError(ContextDetectionError):
    """Raised when API quota is exceeded."""

    def __init__(self) -> None:
        super().__init__(
            "API quota exceeded during context detection. "
            "Please wait and try again."
        )


# Protocols for client interfaces (allows mocking)
class ProjectsClientProtocol(Protocol):
    """Protocol for GCP Projects client."""

    def search_projects(
        self,
        query: str | None = None,
        page_size: int | None = None,
    ) -> Any:
        """Search for projects."""
        ...

    def close(self) -> None:
        """Close the client and release resources."""
        ...


class ClusterManagerClientProtocol(Protocol):
    """Protocol for GKE Cluster Manager client."""

    def list_clusters(
        self,
        parent: str,
    ) -> Any:
        """List clusters in a project."""
        ...

    def close(self) -> None:
        """Close the client and release resources."""
        ...


# Data models
@dataclass
class DiscoveredProject:
    """A discovered GCP project."""

    project_id: str
    display_name: str
    state: str  # ACTIVE, DELETE_REQUESTED, etc.


@dataclass
class DiscoveredCluster:
    """A discovered GKE cluster."""

    name: str
    project_id: str
    location: str  # zone or region
    status: str  # RUNNING, STOPPING, ERROR, etc.


@dataclass
class DiscoveredContext:
    """A discovered context (GCP project or GKE cluster)."""

    context_type: str  # "gcp" or "gke"
    name: str  # Display name for UI
    project: str
    cluster: str | None = None  # Only for GKE contexts
    location: str | None = None  # Only for GKE contexts


# Cache for discovery results
@dataclass
class DetectionCache:
    """Cache for discovery results."""

    discovered_contexts: list[DiscoveredContext]
    timestamp: datetime


# Merge utility functions
def _context_matches(discovered: DiscoveredContext, existing: Context) -> bool:
    """Check if a discovered context matches an existing context.

    Args:
        discovered: The discovered context.
        existing: The existing context from configuration.

    Returns:
        True if they represent the same resource, False otherwise.
    """
    # Type must match
    if discovered.context_type != existing.type:
        return False

    # For GCP contexts, match on project
    if discovered.context_type == "gcp" and isinstance(existing, GCPContext):
        return discovered.project == existing.project

    # For GKE contexts, match on project + cluster
    if discovered.context_type == "gke" and isinstance(existing, GKEContext):
        return (
            discovered.project == existing.project
            and discovered.cluster == existing.cluster
        )

    return False


def merge_contexts(
    discovered: list[DiscoveredContext],
    existing: list[Context],
) -> list[Context]:
    """Merge discovered contexts with existing contexts.

    Filters out discovered contexts that already exist in the configuration.
    Preserves existing contexts unchanged.

    Args:
        discovered: List of discovered contexts.
        existing: List of existing contexts from configuration.

    Returns:
        List of new contexts to add (discovered contexts not in existing).
    """
    new_contexts: list[Context] = []

    for disc_ctx in discovered:
        # Check if this context already exists
        exists = any(_context_matches(disc_ctx, existing_ctx) for existing_ctx in existing)

        if exists:
            logger.debug(
                "Skipping discovered context (already exists): %s %s",
                disc_ctx.context_type,
                disc_ctx.project,
            )
            continue

        # Convert to Config context model
        if disc_ctx.context_type == "gcp":
            new_contexts.append(
                GCPContext(
                    name=disc_ctx.name,
                    type="gcp",
                    project=disc_ctx.project,
                )
            )
        elif disc_ctx.context_type == "gke":
            new_contexts.append(
                GKEContext(
                    name=disc_ctx.name,
                    type="gke",
                    project=disc_ctx.project,
                    cluster=disc_ctx.cluster or "",  # Should always be set for GKE
                    location=disc_ctx.location,
                )
            )

    logger.info(
        "Merge complete: %d discovered, %d existing, %d new",
        len(discovered),
        len(existing),
        len(new_contexts),
    )

    return new_contexts


class ContextDetector:
    """Detects available GCP projects and GKE clusters.

    Uses Application Default Credentials to discover accessible resources.
    Results are cached to avoid repeated API calls.

    This class manages GCP client resources and should be used as an async
    context manager to ensure proper cleanup:

    Example:
        >>> async with ContextDetector() as detector:
        ...     contexts = await detector.discover()
        ...     for ctx in contexts:
        ...         print(f"{ctx.context_type}: {ctx.name}")
    """

    def __init__(
        self,
        project_filter: list[str] | None = None,
        skip_projects: list[str] | None = None,
        include_gcp_contexts: bool = True,
        include_gke_contexts: bool = True,
        cache_ttl_seconds: int = 300,
        projects_client: ProjectsClientProtocol | None = None,
        clusters_client: ClusterManagerClientProtocol | None = None,
    ) -> None:
        """Initialize the context detector.

        Args:
            project_filter: List of fnmatch patterns to include (e.g., ["prod-*"]).
            skip_projects: List of fnmatch patterns to exclude (e.g., ["test-*"]).
            include_gcp_contexts: Whether to create GCP contexts.
            include_gke_contexts: Whether to create GKE contexts.
            cache_ttl_seconds: Cache TTL in seconds.
            projects_client: Optional projects client (for testing).
            clusters_client: Optional clusters client (for testing).

        Raises:
            DetectionNotInstalledError: If required libraries are not installed.
        """
        if not DETECTION_AVAILABLE and (
            projects_client is None or clusters_client is None
        ):
            logger.error(
                "Context detection not available - required libraries not installed"
            )
            raise DetectionNotInstalledError()

        self._project_filter = project_filter or []
        self._skip_projects = skip_projects or []
        self._include_gcp = include_gcp_contexts
        self._include_gke = include_gke_contexts
        self._cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._projects_client = projects_client
        self._clusters_client = clusters_client
        self._cache: DetectionCache | None = None

        logger.info(
            "ContextDetector initialized: gcp=%s, gke=%s, cache_ttl=%ds",
            include_gcp_contexts,
            include_gke_contexts,
            cache_ttl_seconds,
        )

    async def __aenter__(self) -> ContextDetector:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit - cleanup clients."""
        await self.close()

    async def close(self) -> None:
        """Close and cleanup GCP clients.

        This method should be called when done with the detector to release
        resources. It's automatically called when using the detector as an
        async context manager.
        """
        if self._projects_client is not None:
            # GCP clients have a close() method (not async)
            try:
                self._projects_client.close()
                logger.debug("Closed projects client")
            except Exception as e:
                logger.warning("Error closing projects client: %s", e)
            finally:
                self._projects_client = None

        if self._clusters_client is not None:
            try:
                self._clusters_client.close()
                logger.debug("Closed clusters client")
            except Exception as e:
                logger.warning("Error closing clusters client: %s", e)
            finally:
                self._clusters_client = None

    def _get_projects_client(self) -> ProjectsClientProtocol:
        """Get or create the projects client.

        Returns:
            The projects client.

        Raises:
            DetectionAuthenticationError: If authentication fails.
        """
        if self._projects_client is not None:
            logger.debug("Using existing projects client")
            return self._projects_client

        if not DETECTION_AVAILABLE:
            logger.error("Detection libraries not available when creating client")
            raise DetectionNotInstalledError()

        logger.debug("Creating new projects client")
        try:
            self._projects_client = _resourcemanager_client_class()
            logger.info("Projects client created successfully")
            return self._projects_client
        except Exception as e:
            error_msg = str(e).lower()
            logger.error("Failed to create projects client: %s", e)
            if "credentials" in error_msg or "authentication" in error_msg:
                logger.error("Authentication error - credentials may be missing")
                raise DetectionAuthenticationError() from e
            raise ContextDetectionError(f"Failed to create projects client: {e}") from e

    def _get_clusters_client(self) -> ClusterManagerClientProtocol:
        """Get or create the clusters client.

        Returns:
            The clusters client.

        Raises:
            DetectionAuthenticationError: If authentication fails.
        """
        if self._clusters_client is not None:
            logger.debug("Using existing clusters client")
            return self._clusters_client

        if not DETECTION_AVAILABLE:
            logger.error("Detection libraries not available when creating client")
            raise DetectionNotInstalledError()

        logger.debug("Creating new clusters client")
        try:
            self._clusters_client = _container_client_class()
            logger.info("Clusters client created successfully")
            return self._clusters_client
        except Exception as e:
            error_msg = str(e).lower()
            logger.error("Failed to create clusters client: %s", e)
            if "credentials" in error_msg or "authentication" in error_msg:
                logger.error("Authentication error - credentials may be missing")
                raise DetectionAuthenticationError() from e
            raise ContextDetectionError(
                f"Failed to create clusters client: {e}"
            ) from e

    def _matches_filter(self, project_id: str) -> bool:
        """Check if a project matches the filter criteria.

        Args:
            project_id: The project ID to check.

        Returns:
            True if the project should be included, False otherwise.
        """
        # Check skip patterns first
        for pattern in self._skip_projects:
            if fnmatch.fnmatch(project_id, pattern):
                logger.debug("Project %s skipped by pattern: %s", project_id, pattern)
                return False

        # If no include filter, accept all (that aren't skipped)
        if not self._project_filter:
            return True

        # Check include patterns
        for pattern in self._project_filter:
            if fnmatch.fnmatch(project_id, pattern):
                logger.debug("Project %s matched pattern: %s", project_id, pattern)
                return True

        # Not matched by any include pattern
        logger.debug("Project %s did not match any include pattern", project_id)
        return False

    async def discover_projects(self) -> list[DiscoveredProject]:
        """Discover accessible GCP projects.

        Returns:
            List of discovered projects.

        Raises:
            DetectionAuthenticationError: If authentication fails.
            DetectionQuotaExceededError: If quota is exceeded.
        """
        logger.info("Discovering GCP projects...")
        client = self._get_projects_client()

        projects: list[DiscoveredProject] = []

        try:
            loop = asyncio.get_running_loop()

            # Run the API call in executor (blocking I/O)
            search_results = await loop.run_in_executor(
                None,
                lambda: list(client.search_projects()),
            )

            logger.debug("Found %d projects before filtering", len(search_results))

            for project in search_results:
                project_id = project.project_id
                display_name = project.display_name or project_id
                state = project.state.name if hasattr(project.state, "name") else "UNKNOWN"

                # Only include active projects that match filters
                if state == "ACTIVE" and self._matches_filter(project_id):
                    projects.append(
                        DiscoveredProject(
                            project_id=project_id,
                            display_name=display_name,
                            state=state,
                        )
                    )
                    logger.debug("Added project: %s (%s)", project_id, display_name)

            logger.info("Discovered %d active projects after filtering", len(projects))
            return projects

        except Exception as e:
            logger.error("Project discovery failed: %s (%s)", e, type(e).__name__)
            # Propagate authentication and quota errors
            self._handle_detection_error(e)
            return []  # Unreachable - _handle_detection_error always raises

    async def discover_clusters(self, project_id: str) -> list[DiscoveredCluster]:
        """Discover GKE clusters in a project.

        Args:
            project_id: The GCP project ID.

        Returns:
            List of discovered clusters.

        Raises:
            DetectionAuthenticationError: If authentication fails.
            DetectionQuotaExceededError: If quota is exceeded.
        """
        logger.info("Discovering GKE clusters in project: %s", project_id)
        client = self._get_clusters_client()

        clusters: list[DiscoveredCluster] = []

        try:
            loop = asyncio.get_running_loop()

            # List clusters in all locations (using "-" wildcard)
            parent = f"projects/{project_id}/locations/-"

            # Run the API call in executor (blocking I/O)
            response = await loop.run_in_executor(
                None,
                lambda: client.list_clusters(parent=parent),
            )

            # Extract clusters from response
            cluster_list = getattr(response, "clusters", [])

            for cluster in cluster_list:
                name = cluster.name
                location = cluster.location
                status = cluster.status.name if hasattr(cluster.status, "name") else "UNKNOWN"

                # Only include running clusters
                if status == "RUNNING":
                    clusters.append(
                        DiscoveredCluster(
                            name=name,
                            project_id=project_id,
                            location=location,
                            status=status,
                        )
                    )
                    logger.debug(
                        "Added cluster: %s in %s (%s)", name, location, status
                    )

            logger.info(
                "Discovered %d running clusters in project %s", len(clusters), project_id
            )
            return clusters

        except Exception as e:
            # Check if this is a serious error that should propagate
            error_msg = str(e).lower()

            # API not enabled is expected for projects without GKE
            if "api" in error_msg and ("not enabled" in error_msg or "disabled" in error_msg):
                logger.debug(
                    "GKE API not enabled for project %s, skipping cluster discovery",
                    project_id
                )
                return []

            # Permission denied is expected for projects we can't access
            if "permission" in error_msg or "forbidden" in error_msg or "403" in error_msg:
                logger.debug(
                    "No permission to list clusters in project %s, skipping",
                    project_id
                )
                return []

            # For other errors, log as warning but don't fail entire discovery
            logger.warning(
                "Cluster discovery failed for project %s: %s (%s)",
                project_id, e, type(e).__name__
            )
            return []

    async def discover(
        self,
        force_refresh: bool = False,
    ) -> list[DiscoveredContext]:
        """Discover all accessible contexts.

        Uses cached results if available and not expired (based on cache_ttl_seconds
        from initialization). The cache is timezone-aware and remains valid across
        daylight saving time changes.

        Args:
            force_refresh: Bypass cache and force a fresh discovery.

        Returns:
            List of discovered contexts (GCP projects and/or GKE clusters).

        Raises:
            DetectionAuthenticationError: If authentication fails.
            DetectionQuotaExceededError: If quota is exceeded.

        Note:
            GKE cluster discovery is performed in parallel across all projects
            for better performance.
        """
        # Check cache
        if not force_refresh and self._cache is not None:
            age = datetime.now(UTC) - self._cache.timestamp
            if age < self._cache_ttl:
                logger.info("Returning cached contexts (age: %s)", age)
                return self._cache.discovered_contexts

        logger.info("Starting context discovery...")
        contexts: list[DiscoveredContext] = []

        # Discover projects
        projects = await self.discover_projects()
        logger.info("Discovered %d projects", len(projects))

        # Create GCP contexts
        if self._include_gcp:
            for project in projects:
                contexts.append(
                    DiscoveredContext(
                        context_type="gcp",
                        name=f"[detected] {project.project_id}",
                        project=project.project_id,
                    )
                )
            logger.info("Created %d GCP contexts", len(projects))

        # Discover and create GKE contexts (in parallel for better performance)
        if self._include_gke:
            # Discover clusters in all projects concurrently
            cluster_results = await asyncio.gather(
                *[self.discover_clusters(project.project_id) for project in projects],
                return_exceptions=False,  # Let errors propagate
            )

            # Flatten results and create contexts
            cluster_count = 0
            for clusters in cluster_results:
                cluster_count += len(clusters)
                for cluster in clusters:
                    contexts.append(
                        DiscoveredContext(
                            context_type="gke",
                            name=f"[detected] {cluster.name} ({cluster.project_id})",
                            project=cluster.project_id,
                            cluster=cluster.name,
                            location=cluster.location,
                        )
                    )

            logger.info("Created %d GKE contexts from %d clusters", cluster_count, cluster_count)

        # Update cache
        self._cache = DetectionCache(
            discovered_contexts=contexts,
            timestamp=datetime.now(UTC),
        )

        logger.info("Discovery complete: %d total contexts", len(contexts))
        return contexts

    def _handle_detection_error(self, error: Exception) -> None:
        """Convert API exceptions to our error types.

        Args:
            error: The exception to handle.

        Raises:
            Appropriate detection error type.
        """
        if not DETECTION_AVAILABLE or _google_exceptions is None:
            logger.error("Detection error (library not available): %s", error)
            raise ContextDetectionError(f"Detection error: {error}") from error

        if isinstance(error, _google_exceptions.Unauthenticated):
            logger.error("Authentication failed")
            raise DetectionAuthenticationError() from error
        elif isinstance(error, _google_exceptions.PermissionDenied):
            logger.error("Permission denied")
            raise DetectionAuthenticationError(
                "Permission denied. Ensure you have the necessary IAM roles."
            ) from error
        elif isinstance(error, _google_exceptions.ResourceExhausted):
            logger.error("API quota exceeded")
            raise DetectionQuotaExceededError() from error
        elif isinstance(error, _google_exceptions.GoogleAPIError):
            logger.error("API error: %s", error)
            raise ContextDetectionError(f"API error: {error}") from error
        else:
            logger.error("Unknown detection error: %s (%s)", error, type(error).__name__)
            raise ContextDetectionError(f"Detection error: {error}") from error
