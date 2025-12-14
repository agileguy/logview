"""GCP Cloud Logging adapter.

Requires the google-cloud-logging package:
    pip install logview[gcp]
"""

from __future__ import annotations

import asyncio
import itertools
import logging
import re
from collections.abc import AsyncIterator
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol

from logview.domain.models import Filter, FilterField, LogEntry, Severity

# Use standard logging - will be configured by app if available
logger = logging.getLogger("logview.adapters.gcp")

if TYPE_CHECKING:
    pass


# Check if google-cloud-logging is available
GCP_AVAILABLE = False
_logging_client_class: Any = None
_google_exceptions: Any = None

try:
    from google.api_core import exceptions as google_exceptions
    from google.cloud import logging as google_logging

    GCP_AVAILABLE = True
    _logging_client_class = google_logging.Client
    _google_exceptions = google_exceptions
except ImportError:
    pass


class GCPError(Exception):
    """Base exception for GCP adapter errors."""

    pass


class GCPNotInstalledError(GCPError):
    """Raised when google-cloud-logging is not installed."""

    def __init__(self) -> None:
        super().__init__(
            "GCP support requires the google-cloud-logging package. "
            "Install with: pip install logview[gcp]"
        )


class GCPAuthenticationError(GCPError):
    """Raised when authentication fails."""

    def __init__(self, message: str | None = None) -> None:
        default_msg = (
            "GCP authentication failed. Please run:\n"
            "  gcloud auth application-default login"
        )
        super().__init__(message or default_msg)


class GCPPermissionError(GCPError):
    """Raised when permission is denied."""

    def __init__(self, project: str) -> None:
        super().__init__(
            f"Permission denied for project '{project}'. "
            "Ensure you have 'Logs Viewer' role."
        )


class GCPProjectNotFoundError(GCPError):
    """Raised when project is not found."""

    def __init__(self, project: str) -> None:
        super().__init__(
            f"Project '{project}' not found. "
            "Check the project ID is correct."
        )


class GCPQuotaExceededError(GCPError):
    """Raised when quota is exceeded."""

    def __init__(self) -> None:
        super().__init__(
            "GCP quota exceeded. Please wait and try again, "
            "or request a quota increase."
        )


class GCPInvalidProjectError(GCPError):
    """Raised when project ID format is invalid."""

    def __init__(self, project: str) -> None:
        super().__init__(
            f"Invalid project ID '{project}'. "
            "Project IDs must be 6-30 characters, lowercase letters, "
            "digits, and hyphens only."
        )


# Protocol for the logging client (allows mocking)
class LoggingClientProtocol(Protocol):
    """Protocol for GCP logging client."""

    def list_entries(
        self,
        filter_: str | None = None,
        order_by: str | None = None,
        page_size: int | None = None,
        resource_names: list[str] | None = None,
    ) -> Any:
        """List log entries."""
        ...


# Severity mapping from GCP to our internal model
GCP_SEVERITY_MAP = {
    "DEFAULT": Severity.DEBUG,
    "DEBUG": Severity.DEBUG,
    "INFO": Severity.INFO,
    "NOTICE": Severity.INFO,
    "WARNING": Severity.WARN,
    "ERROR": Severity.ERROR,
    "CRITICAL": Severity.CRITICAL,
    "ALERT": Severity.CRITICAL,
    "EMERGENCY": Severity.CRITICAL,
}

# Reverse mapping for filter building
SEVERITY_TO_GCP = {
    Severity.DEBUG: "DEBUG",
    Severity.INFO: "INFO",
    Severity.WARN: "WARNING",
    Severity.ERROR: "ERROR",
    Severity.CRITICAL: "CRITICAL",
}


def _validate_project_id(project: str) -> None:
    """Validate GCP project ID format.

    Args:
        project: The project ID to validate.

    Raises:
        GCPInvalidProjectError: If the project ID is invalid.
    """
    # GCP project IDs: 6-30 chars, lowercase letters, digits, hyphens
    # Must start with a letter, cannot end with a hyphen
    pattern = r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$"
    if not re.match(pattern, project):
        logger.warning("Invalid project ID format: %s", project)
        raise GCPInvalidProjectError(project)
    logger.debug("Project ID validated: %s", project)


def _build_filter(
    log_filter: Filter,
    log_name: str | None = None,
    resource_type: str | None = None,
) -> str:
    """Build a Cloud Logging filter string.

    Args:
        log_filter: The filter configuration.
        log_name: Optional log name to filter by.
        resource_type: Optional resource type to filter by.

    Returns:
        Cloud Logging filter string.
    """
    parts: list[str] = []

    # Time range
    if log_filter.time_range:
        # Handle both naive and timezone-aware datetimes
        # For naive datetimes, append Z to indicate UTC
        # For timezone-aware, isoformat() already includes offset
        start = log_filter.time_range.start
        end = log_filter.time_range.end
        start_iso = start.isoformat() if start.tzinfo else start.isoformat() + "Z"
        end_iso = end.isoformat() if end.tzinfo else end.isoformat() + "Z"
        parts.append(f'timestamp >= "{start_iso}"')
        parts.append(f'timestamp <= "{end_iso}"')

    # Severity (minimum level)
    if log_filter.severity:
        gcp_severity = SEVERITY_TO_GCP.get(log_filter.severity, "DEBUG")
        parts.append(f"severity >= {gcp_severity}")

    # Log name
    if log_name:
        parts.append(f'logName="{log_name}"')

    # Resource type
    if resource_type:
        parts.append(f'resource.type="{resource_type}"')

    # Text search
    if log_filter.text_search:
        # Escape backslashes first, then quotes (order matters!)
        # Cloud Logging uses \\ for literal backslash and \" for literal quote
        # Wrap OR expression in parentheses to ensure correct precedence with AND
        escaped = log_filter.text_search.replace("\\", "\\\\").replace('"', '\\"')
        parts.append(f'(textPayload:"{escaped}" OR jsonPayload:"{escaped}")')

    # Custom fields from filter.fields
    # Skip log_name/resource_type if already provided via parameters to avoid
    # duplicate conditions like logName="a" AND logName="b" which returns nothing
    if log_filter.fields:
        for key, value in log_filter.fields.items():
            if key == "log_name" and value and not log_name:
                parts.append(f'logName="{value}"')
            elif key == "resource_type" and value and not resource_type:
                parts.append(f'resource.type="{value}"')

    return " AND ".join(parts) if parts else ""


def _parse_log_entry(entry: Any, project: str) -> LogEntry:
    """Convert a GCP log entry to our LogEntry model.

    Args:
        entry: The GCP log entry object.
        project: The project ID.

    Returns:
        A LogEntry instance.
    """
    # Get timestamp
    timestamp = entry.timestamp
    if timestamp and timestamp.tzinfo:
        # Convert to naive datetime in local time
        timestamp = timestamp.astimezone().replace(tzinfo=None)
    elif not timestamp:
        timestamp = datetime.now()

    # Get severity
    severity_str = getattr(entry, "severity", "DEFAULT") or "DEFAULT"
    severity = GCP_SEVERITY_MAP.get(severity_str, Severity.INFO)

    # Get message - try different payload types
    # The google-cloud-logging library uses 'payload' property which returns the appropriate payload
    message = ""

    # Try the unified payload property first (returns text_payload, json_payload, or proto_payload)
    if hasattr(entry, "payload") and entry.payload:
        payload = entry.payload
        if isinstance(payload, str):
            message = payload
        elif isinstance(payload, dict):
            message = payload.get("message") or payload.get("msg") or payload.get("textPayload") or str(payload)
        else:
            message = str(payload)
    # Fall back to individual payload attributes
    elif hasattr(entry, "text_payload") and entry.text_payload:
        message = entry.text_payload
    elif hasattr(entry, "json_payload") and entry.json_payload:
        # For JSON payloads, look for common message fields
        payload = entry.json_payload
        if isinstance(payload, dict):
            message = payload.get("message") or payload.get("msg") or str(payload)
        else:
            message = str(payload)
    elif hasattr(entry, "proto_payload") and entry.proto_payload:
        message = str(entry.proto_payload)

    # Log entry attributes for debugging empty messages
    if not message:
        logger.debug(
            "Empty message for entry. Attributes: %s",
            [attr for attr in dir(entry) if not attr.startswith("_")]
        )

    # Get source (resource info)
    source = project
    resource = getattr(entry, "resource", None)
    if resource:
        labels = getattr(resource, "labels", {}) or {}
        if "pod_name" in labels:
            source = labels["pod_name"]
        elif "instance_id" in labels:
            source = labels["instance_id"]
        elif "function_name" in labels:
            source = labels["function_name"]

    # Build metadata
    metadata: dict[str, str] = {
        "project": project,
        "log_name": getattr(entry, "log_name", "") or "",
    }

    if resource:
        metadata["resource_type"] = getattr(resource, "type", "") or ""
        labels = getattr(resource, "labels", {}) or {}
        for key, value in labels.items():
            metadata[f"resource.{key}"] = str(value)

    # Add labels from entry
    entry_labels = getattr(entry, "labels", {}) or {}
    for key, value in entry_labels.items():
        metadata[f"label.{key}"] = str(value)

    # Get insert ID for uniqueness
    insert_id = getattr(entry, "insert_id", "") or ""
    if insert_id:
        metadata["insert_id"] = insert_id

    # Build raw representation
    raw_parts = [
        f"timestamp: {timestamp.isoformat()}",
        f"severity: {severity_str}",
        f"message: {message}",
    ]
    if resource:
        raw_parts.append(f"resource.type: {metadata.get('resource_type', '')}")
    raw = "\n".join(raw_parts)

    return LogEntry(
        timestamp=timestamp,
        severity=severity,
        message=message,
        source=source,
        metadata=metadata,
        raw=raw,
    )


class GCPLogSource:
    """GCP Cloud Logging source.

    Fetches logs from Google Cloud Logging using Application Default Credentials.
    Requires the google-cloud-logging package to be installed.

    Example:
        >>> source = GCPLogSource(project_id="my-project")
        >>> async for entry in source.fetch(Filter(limit=100)):
        ...     print(entry.message)
    """

    def __init__(
        self,
        project_id: str,
        log_name: str | None = None,
        resource_type: str | None = None,
        name: str | None = None,
        client: LoggingClientProtocol | None = None,
    ) -> None:
        """Initialize the GCP log source.

        Args:
            project_id: The GCP project ID to fetch logs from.
            log_name: Optional log name filter (e.g., 'cloudaudit.googleapis.com%2Factivity').
            resource_type: Optional resource type filter (e.g., 'gce_instance').
            name: Optional custom display name. Defaults to "GCP: {project_id}".
            client: Optional logging client (for testing). If not provided,
                   creates a real client using ADC.

        Raises:
            GCPNotInstalledError: If google-cloud-logging is not installed.
            GCPInvalidProjectError: If the project ID format is invalid.
        """
        if not GCP_AVAILABLE and client is None:
            logger.error("GCP support not available - google-cloud-logging not installed")
            raise GCPNotInstalledError()

        _validate_project_id(project_id)

        self._project_id = project_id
        self._log_name = log_name
        self._resource_type = resource_type
        self._custom_name = name
        self._client = client
        logger.info(
            "GCPLogSource initialized: project=%s, log_name=%s, resource_type=%s",
            project_id,
            log_name,
            resource_type,
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
            # Check for auth-related errors
            error_msg = str(e).lower()
            logger.error("Failed to create GCP client: %s", e)
            if "credentials" in error_msg or "authentication" in error_msg:
                logger.error("Authentication error detected - credentials may be missing or invalid")
                raise GCPAuthenticationError() from e
            raise GCPError(f"Failed to create GCP client: {e}") from e

    @property
    def name(self) -> str:
        """Human-readable name for this source."""
        if self._custom_name:
            return self._custom_name
        return f"GCP: {self._project_id}"

    async def fetch(self, log_filter: Filter) -> AsyncIterator[LogEntry]:
        """Fetch logs from GCP Cloud Logging.

        Args:
            log_filter: The filter to apply.

        Yields:
            LogEntry objects from GCP.

        Raises:
            GCPAuthenticationError: If authentication fails.
            GCPPermissionError: If permission is denied.
            GCPProjectNotFoundError: If project is not found.
            GCPQuotaExceededError: If quota is exceeded.
        """
        logger.info("Fetching logs from GCP project: %s (limit: %d)", self._project_id, log_filter.limit)
        client = self._get_client()

        # Build the filter string
        filter_str = _build_filter(
            log_filter,
            log_name=self._log_name,
            resource_type=self._resource_type,
        )
        logger.debug("GCP filter string: %s", filter_str or "(empty)")

        # Fetch entries
        count = 0
        parse_errors = 0
        try:
            # Run in executor to not block the event loop
            # Use islice to limit entries fetched - prevents loading millions of
            # entries into memory when only a small limit is requested
            logger.debug("Executing GCP list_entries request...")
            loop = asyncio.get_running_loop()
            entries = await loop.run_in_executor(
                None,
                lambda: list(
                    itertools.islice(
                        client.list_entries(
                            filter_=filter_str or None,
                            order_by="timestamp desc",
                            page_size=min(log_filter.limit, 1000),
                            resource_names=[f"projects/{self._project_id}"],
                        ),
                        log_filter.limit,
                    )
                ),
            )
            logger.debug("GCP returned %d entries", len(entries))

            for entry in entries:
                try:
                    log_entry = _parse_log_entry(entry, self._project_id)
                    yield log_entry
                    count += 1
                except Exception as e:
                    # Skip entries that fail to parse
                    parse_errors += 1
                    logger.debug("Failed to parse entry: %s", e)
                    continue

                # Yield to event loop periodically
                if count % 100 == 0:
                    await asyncio.sleep(0)

            logger.info("GCP fetch complete: %d entries returned, %d parse errors", count, parse_errors)

        except Exception as e:
            logger.error("GCP fetch failed: %s (%s)", e, type(e).__name__)
            self._handle_gcp_error(e)

    def _handle_gcp_error(self, error: Exception) -> None:
        """Convert GCP exceptions to our error types.

        Args:
            error: The exception to handle.

        Raises:
            Appropriate GCP error type.
        """
        if not GCP_AVAILABLE or _google_exceptions is None:
            logger.error("GCP error (library not available): %s", error)
            raise GCPError(f"GCP error: {error}") from error

        if isinstance(error, _google_exceptions.Unauthenticated):
            logger.error("GCP authentication failed - run: gcloud auth application-default login")
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
            raise GCPError(f"GCP API error: {error}") from error
        else:
            logger.error("Unknown GCP error: %s (%s)", error, type(error).__name__)
            raise GCPError(f"GCP error: {error}") from error

    def validate_filter(self, log_filter: Filter) -> list[str]:
        """Validate a filter for GCP.

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

        # Validate time range
        if log_filter.time_range:
            if log_filter.time_range.start > log_filter.time_range.end:
                errors.append("Start time must be before end time")

        return errors

    def available_filters(self) -> list[FilterField]:
        """Get available filter fields for GCP.

        Returns:
            List of GCP-specific filter fields.
        """
        return [
            FilterField(name="project", label="Project ID", required=True),
            FilterField(name="log_name", label="Log Name"),
            FilterField(
                name="resource_type",
                label="Resource Type",
                options=[
                    "gce_instance",
                    "k8s_container",
                    "cloud_function",
                    "gae_app",
                    "cloud_run_revision",
                ],
            ),
            FilterField(
                name="severity",
                label="Severity",
                options=[s.value for s in Severity],
            ),
        ]
