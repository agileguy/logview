"""GKE Kubernetes log adapter using Cloud Logging API.

GKE logs are stored in Google Cloud Logging, not the Kubernetes API.
This adapter queries Cloud Logging with k8s-specific resource filters.

Requires the google-cloud-logging package:
    pip install logview-ag[gcp]
"""

from __future__ import annotations

import asyncio
import functools
import itertools
import logging
import re
from collections.abc import AsyncIterator
from datetime import datetime
from typing import TYPE_CHECKING, Any

from logview.adapters.gcp import (
    GCP_AVAILABLE,
    GCP_SEVERITY_MAP,
    SEVERITY_TO_GCP,
    GCPAuthenticationError,
    GCPError,
    GCPNotInstalledError,
    GCPPermissionError,
    GCPProjectNotFoundError,
    GCPQuotaExceededError,
    LoggingClientProtocol,
    _google_exceptions,
    _logging_client_class,
    _validate_project_id,
)
from logview.domain.models import Filter, FilterField, LogEntry, Severity

logger = logging.getLogger("logview.adapters.gke")

if TYPE_CHECKING:
    pass


# GKE-specific errors
class GKEError(GCPError):
    """Base exception for GKE adapter errors."""

    pass


class GKEClusterNotFoundError(GKEError):
    """Raised when the GKE cluster is not found in logs."""

    def __init__(self, cluster: str, project: str) -> None:
        super().__init__(
            f"No logs found for cluster '{cluster}' in project '{project}'. "
            "Ensure the cluster exists and has workloads generating logs."
        )


class GKEInvalidFilterError(GKEError):
    """Raised when an invalid filter pattern is provided."""

    pass


def _validate_cluster_name(cluster: str) -> None:
    """Validate GKE cluster name format.

    Args:
        cluster: The cluster name to validate.

    Raises:
        GKEError: If the cluster name is invalid.
    """
    # GKE cluster names: 1-40 chars, lowercase letters, digits, hyphens
    # Must start with letter, cannot end with hyphen
    pattern = r"^[a-z][a-z0-9-]{0,38}[a-z0-9]$|^[a-z]$"
    if not re.match(pattern, cluster):
        logger.warning("Invalid cluster name format: %s", cluster)
        raise GKEError(
            f"Invalid cluster name '{cluster}'. "
            "Cluster names must be 1-40 characters, lowercase letters, "
            "digits, and hyphens only."
        )
    logger.debug("Cluster name validated: %s", cluster)


def _validate_namespace(namespace: str) -> None:
    """Validate Kubernetes namespace format.

    Args:
        namespace: The namespace to validate.

    Raises:
        GKEError: If the namespace is invalid.
    """
    # K8s namespaces: DNS-1123 label (max 63 chars, lowercase alphanumeric or -)
    pattern = r"^[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$|^[a-z0-9]$"
    if not re.match(pattern, namespace):
        logger.warning("Invalid namespace format: %s", namespace)
        raise GKEError(
            f"Invalid namespace '{namespace}'. "
            "Namespaces must be valid DNS labels."
        )
    logger.debug("Namespace validated: %s", namespace)


def _escape_filter_value(value: str) -> str:
    """Escape a value for use in Cloud Logging filter strings.

    Args:
        value: The value to escape.

    Returns:
        Escaped value safe for Cloud Logging filter syntax.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _build_wildcard_filter(
    field_name: str,
    pattern: str,
    label_name: str,
) -> str:
    """Build a wildcard or exact match filter for a resource label.

    Args:
        field_name: Human-readable field name for error messages (e.g., "namespace", "pod").
        pattern: The filter pattern, possibly ending with * for wildcard.
        label_name: The Cloud Logging label name (e.g., "resource.labels.namespace_name").

    Returns:
        Filter expression for the label.

    Raises:
        GKEInvalidFilterError: If the pattern contains invalid wildcards.
    """
    if pattern.endswith("*"):
        prefix = pattern[:-1]  # Remove trailing *
        if not prefix:
            raise GKEInvalidFilterError(
                f"Invalid {field_name} pattern '{pattern}': "
                "wildcard-only patterns are not allowed"
            )
        if "*" in prefix:
            raise GKEInvalidFilterError(
                f"Invalid {field_name} pattern '{pattern}': "
                f"only trailing wildcards are allowed (e.g., 'prefix-*')"
            )
        # Escape for regex first, then for Cloud Logging string literal
        # 1. re.escape() handles regex metacharacters (., *, +, ?, etc.)
        # 2. Then escape backslashes and quotes for Cloud Logging string literal syntax
        regex_escaped = re.escape(prefix)
        escaped_prefix = regex_escaped.replace("\\", "\\\\").replace('"', '\\"')
        return f'{label_name}=~"^{escaped_prefix}"'
    elif "*" in pattern:
        raise GKEInvalidFilterError(
            f"Invalid {field_name} pattern '{pattern}': "
            f"only trailing wildcards are allowed (e.g., 'prefix-*')"
        )
    else:
        escaped = _escape_filter_value(pattern)
        return f'{label_name}="{escaped}"'


def _build_source_filter_gke(source_filter: str) -> tuple[list[str], bool]:
    """Build GKE resource label filters for source_filter using OR for broad matching.

    Converts source_filter to Cloud Logging filters for GKE logs. For pod-only format,
    uses OR to match entries where EITHER namespace OR pod matches the pattern, covering
    most cases server-side.

    Args:
        source_filter: Source filter value (e.g., "default/api-server", "api-*")

    Returns:
        Tuple of (filter_parts, client_side_needed):
        - filter_parts: List of Cloud Logging filter strings (may include OR conditions)
        - client_side_needed: True if client-side fallback needed (cluster sources, exact matching)
    """
    if not source_filter:
        return ([], False)

    parts: list[str] = []
    client_side_needed = False

    if "/" in source_filter:
        # Namespace/pod format
        ns_pod = source_filter.split("/", 1)
        namespace, pod = ns_pod[0], ns_pod[1]

        # Wildcard in namespace is problematic with AND logic
        if "*" in namespace:
            logger.debug("Wildcard in namespace, using client-side filtering only")
            return ([], True)

        # Exact namespace
        parts.append(f'resource.labels.namespace_name="{_escape_filter_value(namespace)}"')

        # Pod with optional wildcard
        if "*" in pod:
            if not pod.endswith("*"):
                logger.debug("Mid-string wildcard in pod, using client-side filtering only")
                return ([], True)
            try:
                pod_filter = _build_wildcard_filter("pod", pod, "resource.labels.pod_name")
                parts.append(pod_filter)
                # Explicit wildcard - server-side handles it completely
                client_side_needed = False
            except GKEInvalidFilterError:
                logger.debug("Invalid pod filter pattern, using client-side filtering only")
                return ([], True)
        else:
            # Convert to prefix wildcard for server-side matching
            try:
                pod_filter = _build_wildcard_filter("pod", pod + "*", "resource.labels.pod_name")
                parts.append(pod_filter)
                # Need client-side for exact substring matching
                client_side_needed = True
            except GKEInvalidFilterError:
                logger.debug("Invalid pod filter pattern, using client-side filtering only")
                return ([], True)

        return (parts, client_side_needed)
    else:
        # Pod-only format - match on namespace OR pod using OR operator
        # Source could be: "namespace/pod", "pod", or "cluster"
        # Using OR covers entries where namespace OR pod matches the pattern

        # Validate wildcard position BEFORE converting (only trailing wildcards supported)
        # Leading wildcards (*api) or mid-string wildcards (api-*-server) not supported
        if "*" in source_filter and not source_filter.endswith("*"):
            logger.debug("Mid-string wildcard in pod, using client-side filtering only")
            return ([], True)
        if source_filter.startswith("*"):
            logger.debug("Leading wildcard in pod, using client-side filtering only")
            return ([], True)

        pattern = source_filter if source_filter.endswith("*") else source_filter + "*"

        try:
            # Build filters for both namespace and pod labels
            namespace_filter = _build_wildcard_filter("namespace", pattern, "resource.labels.namespace_name")
            pod_filter = _build_wildcard_filter("pod", pattern, "resource.labels.pod_name")

            # Wrap in OR to match either label
            or_filter = f"({namespace_filter} OR {pod_filter})"
            parts.append(or_filter)

            # Always need client-side for cluster-level sources (no namespace/pod labels)
            # Server-side OR filter only matches entries with namespace_name or pod_name labels
            client_side_needed = True
        except GKEInvalidFilterError:
            logger.debug("Invalid pod filter pattern, using client-side filtering only")
            return ([], True)

        return (parts, client_side_needed)


def _build_gke_filter(
    log_filter: Filter,
    project: str,
    cluster: str,
    location: str | None = None,
    default_namespace: str | None = None,
) -> tuple[str, bool]:
    """Build a Cloud Logging filter string for GKE logs.

    Args:
        log_filter: The filter configuration (may contain namespace, pod,
            container, labels fields).
        project: GCP project ID.
        cluster: GKE cluster name.
        location: Optional cluster location (zone or region).
        default_namespace: Optional default namespace (used if not in log_filter.fields).

    Returns:
        Tuple of (filter_string, client_side_needed):
        - filter_string: Cloud Logging filter string
        - client_side_needed: Whether client-side filtering is needed for source_filter
    """
    parts: list[str] = []

    # GKE resource type
    parts.append('resource.type="k8s_container"')

    # Required resource labels
    parts.append(f'resource.labels.project_id="{project}"')
    parts.append(f'resource.labels.cluster_name="{cluster}"')

    # Optional location
    if location:
        parts.append(f'resource.labels.location="{location}"')

    # Namespace filter (from log_filter.fields or default_namespace)
    effective_namespace = default_namespace
    if log_filter.fields and "namespace" in log_filter.fields:
        effective_namespace = log_filter.fields["namespace"]

    if effective_namespace:
        parts.append(
            _build_wildcard_filter("namespace", effective_namespace, "resource.labels.namespace_name")
        )

    # Pod filter (from log_filter.fields)
    effective_pod = log_filter.fields.get("pod") if log_filter.fields else None

    if effective_pod:
        parts.append(
            _build_wildcard_filter("pod", effective_pod, "resource.labels.pod_name")
        )

    # Container filter (from log_filter.fields)
    effective_container = log_filter.fields.get("container") if log_filter.fields else None

    if effective_container:
        escaped_container = _escape_filter_value(effective_container)
        parts.append(f'resource.labels.container_name="{escaped_container}"')

    # Label filters (k8s pod labels, from log_filter.fields)
    effective_labels: dict[str, str] = {}
    if log_filter.fields and "labels" in log_filter.fields:
        # Parse labels string: "key1=value1,key2=value2"
        labels_str = log_filter.fields["labels"]
        for pair in labels_str.split(","):
            pair = pair.strip()
            if not pair:
                continue
            if "=" in pair:
                k, v = pair.split("=", 1)
                key_stripped = k.strip()
                val_stripped = v.strip()
                if key_stripped:
                    effective_labels[key_stripped] = val_stripped
                else:
                    logger.warning("Invalid label pair (empty key): %s", pair)
            else:
                logger.warning("Invalid label pair (missing '='): %s", pair)

    for key, value in effective_labels.items():
        # Pod labels are stored as labels."k8s-pod/<key>"
        escaped_key = _escape_filter_value(key)
        escaped_value = _escape_filter_value(value)
        parts.append(f'labels."k8s-pod/{escaped_key}"="{escaped_value}"')

    # Time range
    if log_filter.time_range:
        start = log_filter.time_range.start
        end = log_filter.time_range.end
        start_iso = start.isoformat() if start.tzinfo else start.isoformat() + "Z"
        end_iso = end.isoformat() if end.tzinfo else end.isoformat() + "Z"
        parts.append(f'timestamp >= "{start_iso}"')
        parts.append(f'timestamp <= "{end_iso}"')

    # Severity
    if log_filter.severity:
        gcp_severity = SEVERITY_TO_GCP.get(log_filter.severity, "DEBUG")
        parts.append(f"severity >= {gcp_severity}")

    # Text search
    if log_filter.text_search and log_filter.text_search.strip():
        escaped = _escape_filter_value(log_filter.text_search)
        parts.append(f'(textPayload:"{escaped}" OR jsonPayload:"{escaped}")')

    # Source filter (server-side when possible, with client-side fallback)
    client_side_needed = False
    if log_filter.source_filter:
        source_parts, needs_client = _build_source_filter_gke(log_filter.source_filter)
        parts.extend(source_parts)
        client_side_needed = needs_client

    return (" AND ".join(parts), client_side_needed)


def _parse_gke_log_entry(entry: Any, cluster: str) -> LogEntry:
    """Convert a GCP log entry to our LogEntry model with GKE context.

    Args:
        entry: The GCP log entry object.
        cluster: The GKE cluster name.

    Returns:
        A LogEntry instance.
    """
    # Get timestamp
    timestamp = entry.timestamp
    if timestamp and timestamp.tzinfo:
        timestamp = timestamp.astimezone().replace(tzinfo=None)
    elif not timestamp:
        timestamp = datetime.now()

    # Get severity
    severity_str = getattr(entry, "severity", "DEFAULT") or "DEFAULT"
    severity = GCP_SEVERITY_MAP.get(severity_str, Severity.INFO)

    # Get message
    message = ""
    if hasattr(entry, "payload") and entry.payload:
        payload = entry.payload
        if isinstance(payload, str):
            message = payload
        elif isinstance(payload, dict):
            message = (
                payload.get("message")
                or payload.get("msg")
                or payload.get("log")
                or str(payload)
            )
        else:
            message = str(payload)
    elif hasattr(entry, "text_payload") and entry.text_payload:
        message = entry.text_payload
    elif hasattr(entry, "json_payload") and entry.json_payload:
        payload = entry.json_payload
        if isinstance(payload, dict):
            message = (
                payload.get("message")
                or payload.get("msg")
                or payload.get("log")
                or str(payload)
            )
        else:
            message = str(payload)

    # Build source from pod info
    resource = getattr(entry, "resource", None)
    labels: dict[str, str] = {}
    if resource:
        labels = getattr(resource, "labels", {}) or {}

    # Source: namespace/pod (or just pod if no namespace)
    namespace = labels.get("namespace_name", "")
    pod_name = labels.get("pod_name", "")
    container_name = labels.get("container_name", "")

    if namespace and pod_name:
        source = f"{namespace}/{pod_name}"
    elif pod_name:
        source = pod_name
    else:
        source = cluster

    # Build metadata
    metadata: dict[str, str] = {
        "cluster": cluster,
    }

    if namespace:
        metadata["namespace"] = namespace
    if pod_name:
        metadata["pod"] = pod_name
    if container_name:
        metadata["container"] = container_name

    # Add location if available
    location = labels.get("location", "")
    if location:
        metadata["location"] = location

    # Add log name
    log_name = getattr(entry, "log_name", "") or ""
    if log_name:
        metadata["log_name"] = log_name

    # Add entry labels (pod labels)
    entry_labels = getattr(entry, "labels", {}) or {}
    for key, value in entry_labels.items():
        # Remove k8s-pod/ prefix for cleaner display
        if key.startswith("k8s-pod/"):
            clean_key = key[8:]  # Remove "k8s-pod/" prefix
            metadata[f"label.{clean_key}"] = str(value)
        else:
            metadata[f"label.{key}"] = str(value)

    # Add insert ID
    insert_id = getattr(entry, "insert_id", "") or ""
    if insert_id:
        metadata["insert_id"] = insert_id

    # Build raw representation
    raw_parts = [
        f"timestamp: {timestamp.isoformat()}",
        f"severity: {severity_str}",
        f"cluster: {cluster}",
        f"namespace: {namespace}",
        f"pod: {pod_name}",
        f"container: {container_name}",
        f"message: {message}",
    ]
    raw = "\n".join(raw_parts)

    return LogEntry(
        timestamp=timestamp,
        severity=severity,
        message=message,
        source=source,
        metadata=metadata,
        raw=raw,
    )


class GKELogSource:
    """GKE Kubernetes log source.

    Fetches logs from Google Cloud Logging using k8s_container resource type.
    GKE logs are stored in Cloud Logging, not the Kubernetes API directly.

    Example:
        >>> source = GKELogSource(
        ...     project_id="my-project",
        ...     cluster="my-cluster",
        ...     default_namespace="default",
        ... )
        >>> async for entry in source.fetch(Filter(limit=100)):
        ...     print(entry.message)
    """

    def __init__(
        self,
        project_id: str,
        cluster: str,
        location: str | None = None,
        default_namespace: str | None = None,
        name: str | None = None,
        client: LoggingClientProtocol | None = None,
    ) -> None:
        """Initialize the GKE log source.

        Args:
            project_id: The GCP project ID.
            cluster: The GKE cluster name.
            location: Optional cluster location (zone or region).
            default_namespace: Optional default namespace filter.
            name: Optional custom display name.
            client: Optional logging client (for testing).

        Raises:
            GCPNotInstalledError: If google-cloud-logging is not installed.
            GCPInvalidProjectError: If the project ID format is invalid.
            GKEError: If the cluster name format is invalid.
        """
        if not GCP_AVAILABLE and client is None:
            logger.error("GCP support not available - google-cloud-logging not installed")
            raise GCPNotInstalledError()

        _validate_project_id(project_id)
        _validate_cluster_name(cluster)
        if default_namespace:
            _validate_namespace(default_namespace)

        self._project_id = project_id
        self._cluster = cluster
        self._location = location
        self._namespace = default_namespace
        self._custom_name = name
        self._client = client

        logger.info(
            "GKELogSource initialized: project=%s, cluster=%s, location=%s, namespace=%s",
            project_id,
            cluster,
            location,
            default_namespace,
        )

    def _get_client(self) -> LoggingClientProtocol:
        """Get or create the logging client.

        Returns:
            The logging client.

        Raises:
            GCPAuthenticationError: If authentication fails.
        """
        if self._client is not None:
            logger.debug("Using existing GCP client")
            return self._client

        if not GCP_AVAILABLE:
            logger.error("GCP library not available when creating client")
            raise GCPNotInstalledError()

        logger.debug("Creating new GCP logging client for project: %s", self._project_id)
        try:
            self._client = _logging_client_class(project=self._project_id)
            logger.info("GCP client created successfully for project: %s", self._project_id)
            return self._client
        except Exception as e:
            error_msg = str(e).lower()
            logger.error("Failed to create GCP client: %s", e)
            if "credentials" in error_msg or "authentication" in error_msg:
                logger.error(
                    "Authentication error detected - credentials may be missing or invalid"
                )
                raise GCPAuthenticationError() from e
            raise GCPError(f"Failed to create GCP client: {e}") from e

    @property
    def name(self) -> str:
        """Human-readable name for this source."""
        if self._custom_name:
            return self._custom_name
        if self._namespace:
            return f"GKE: {self._cluster}/{self._namespace}"
        return f"GKE: {self._cluster}"

    @property
    def project_id(self) -> str:
        """Get the GCP project ID."""
        return self._project_id

    @property
    def cluster(self) -> str:
        """Get the GKE cluster name."""
        return self._cluster

    @property
    def source_type(self) -> str:
        """Get the source type identifier."""
        return "gke"

    async def fetch(self, log_filter: Filter) -> AsyncIterator[LogEntry]:
        """Fetch logs from GKE via Cloud Logging.

        Args:
            log_filter: The filter to apply.

        Yields:
            LogEntry objects from GKE.

        Raises:
            GCPAuthenticationError: If authentication fails.
            GCPPermissionError: If permission is denied.
            GCPProjectNotFoundError: If project is not found.
            GCPQuotaExceededError: If quota is exceeded.
        """
        logger.info(
            "Fetching GKE logs: project=%s, cluster=%s (limit: %d)",
            self._project_id,
            self._cluster,
            log_filter.limit,
        )
        client = self._get_client()

        # Build the GKE-specific filter (server-side filtering)
        filter_str, client_side_needed = _build_gke_filter(
            log_filter,
            project=self._project_id,
            cluster=self._cluster,
            location=self._location,
            default_namespace=self._namespace,
        )
        logger.debug(
            "GKE filter: %s, client-side filtering needed: %s",
            filter_str,
            client_side_needed
        )

        # Fetch entries with batch processing (same pattern as GCP adapter)
        count = 0
        parse_errors = 0
        batch_size = 100

        try:
            logger.debug("Executing GKE list_entries request...")
            loop = asyncio.get_running_loop()

            entries_iter = iter(
                client.list_entries(
                    filter_=filter_str,
                    order_by="timestamp desc",
                    page_size=min(log_filter.limit, 1000),
                    resource_names=[f"projects/{self._project_id}"],
                )
            )

            remaining = log_filter.limit
            while remaining > 0:
                # Request extra entries when client-side filtering is active to reduce round-trips
                buffer_size = 50 if client_side_needed else 0
                current_batch_size = min(batch_size, remaining + buffer_size)
                batch = await loop.run_in_executor(
                    None,
                    functools.partial(
                        lambda it, n: list(itertools.islice(it, n)),
                        entries_iter,
                        current_batch_size,
                    ),
                )

                if not batch:
                    break

                logger.debug("GKE batch: %d entries fetched", len(batch))

                for entry in batch:
                    try:
                        log_entry = _parse_gke_log_entry(entry, self._cluster)

                        # Apply client-side filtering as a safety net
                        # Server-side filters handle most cases, but we use matches_filter() to ensure
                        # correctness for all filter types (especially source_filter substring matching)
                        if not log_entry.matches_filter(log_filter):
                            logger.debug("Client-side filtered out: %s", log_entry.source)
                            continue

                        yield log_entry
                        count += 1
                    except Exception as e:
                        parse_errors += 1
                        logger.debug("Failed to parse GKE entry: %s", e)
                        continue

                remaining -= len(batch)
                await asyncio.sleep(0)

            logger.info(
                "GKE fetch complete: %d entries returned, %d parse errors",
                count,
                parse_errors,
            )

        except Exception as e:
            logger.error("GKE fetch failed: %s (%s)", e, type(e).__name__)
            self._handle_gke_error(e)

    def _handle_gke_error(self, error: Exception) -> None:
        """Convert GCP exceptions to appropriate error types.

        Args:
            error: The exception to handle.

        Raises:
            Appropriate GKE/GCP error type.
        """
        if not GCP_AVAILABLE or _google_exceptions is None:
            logger.error("GKE error (library not available): %s", error)
            raise GKEError(f"GKE error: {error}") from error

        if isinstance(error, _google_exceptions.Unauthenticated):
            logger.error("GCP authentication failed")
            raise GCPAuthenticationError() from error
        elif isinstance(error, _google_exceptions.PermissionDenied):
            logger.error("GCP permission denied for project: %s", self._project_id)
            raise GCPPermissionError(self._project_id) from error
        elif isinstance(error, _google_exceptions.NotFound):
            logger.error("GCP project not found: %s", self._project_id)
            raise GCPProjectNotFoundError(self._project_id) from error
        elif isinstance(error, _google_exceptions.ResourceExhausted):
            logger.error("GCP quota exceeded")
            raise GCPQuotaExceededError() from error
        elif isinstance(error, _google_exceptions.GoogleAPIError):
            logger.error("GCP API error: %s", error)
            raise GKEError(f"GKE error: {error}") from error
        else:
            logger.error("Unknown GKE error: %s (%s)", error, type(error).__name__)
            raise GKEError(f"GKE error: {error}") from error

    def validate_filter(self, log_filter: Filter) -> list[str]:
        """Validate a filter for GKE.

        Args:
            log_filter: The filter to validate.

        Returns:
            List of validation errors.
        """
        errors: list[str] = []

        if log_filter.limit < 1:
            errors.append("Limit must be at least 1")

        if log_filter.limit > 10000:
            errors.append("Limit cannot exceed 10000")

        if log_filter.time_range:
            if log_filter.time_range.start > log_filter.time_range.end:
                errors.append("Start time must be before end time")

        # Validate namespace format if provided
        if log_filter.fields and "namespace" in log_filter.fields:
            ns = log_filter.fields["namespace"]
            if ns:
                ns_error = self._validate_wildcard_or_name(ns, "namespace")
                if ns_error:
                    errors.append(ns_error)

        # Validate pod format if provided
        if log_filter.fields and "pod" in log_filter.fields:
            pod = log_filter.fields["pod"]
            if pod:
                pod_error = self._validate_wildcard_or_name(pod, "pod")
                if pod_error:
                    errors.append(pod_error)

        return errors

    def _validate_wildcard_or_name(self, value: str, field_name: str) -> str | None:
        """Validate a value that may be a name or wildcard pattern.

        Args:
            value: The value to validate.
            field_name: Human-readable field name for error messages.

        Returns:
            Error message if invalid, None if valid.
        """
        if "*" in value:
            # Wildcard pattern validation
            if value == "*":
                return f"Invalid {field_name} pattern '{value}': wildcard-only patterns are not allowed"
            if not value.endswith("*"):
                return f"Invalid {field_name} pattern '{value}': only trailing wildcards are allowed"
            prefix = value[:-1]
            if "*" in prefix:
                return f"Invalid {field_name} pattern '{value}': only trailing wildcards are allowed"
            # Validate the prefix as a partial DNS label
            if prefix and not re.match(r"^[a-z0-9][a-z0-9-]*$", prefix):
                return f"Invalid {field_name} pattern '{value}': prefix must be a valid partial DNS label"
        else:
            # Exact name validation
            pattern = r"^[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$|^[a-z0-9]$"
            if not re.match(pattern, value):
                return f"Invalid {field_name} format: {value}"
        return None

    def available_filters(self) -> list[FilterField]:
        """Get available filter fields for GKE.

        Returns:
            List of GKE-specific filter fields.
        """
        return [
            FilterField(name="cluster", label="Cluster", required=True),
            FilterField(name="namespace", label="Namespace"),
            FilterField(name="pod", label="Pod Name"),
            FilterField(name="container", label="Container"),
            FilterField(name="labels", label="Labels (key=value,...)"),
            FilterField(
                name="severity",
                label="Severity",
                options=[s.value for s in Severity],
            ),
        ]
