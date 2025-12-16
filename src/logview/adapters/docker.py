"""Docker container log adapter.

Requires the docker package:
    pip install logview[docker]
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol

from logview.domain.models import Filter, FilterField, LogEntry, Severity

# Use standard logging - will be configured by app if available
logger = logging.getLogger("logview.adapters.docker")

if TYPE_CHECKING:
    pass


# Check if docker is available
DOCKER_AVAILABLE = False
_docker_module: Any = None

try:
    import docker

    DOCKER_AVAILABLE = True
    _docker_module = docker
except ImportError:
    pass


class DockerError(Exception):
    """Base exception for Docker adapter errors."""

    pass


class DockerNotInstalledError(DockerError):
    """Raised when docker package is not installed."""

    def __init__(self) -> None:
        super().__init__(
            "Docker support requires the docker package. "
            "Install with: pip install logview[docker]"
        )


class DockerDaemonError(DockerError):
    """Raised when Docker daemon is unreachable."""

    def __init__(self, message: str | None = None) -> None:
        default_msg = (
            "Cannot connect to Docker daemon. "
            "Ensure Docker is running and accessible."
        )
        super().__init__(message or default_msg)


class DockerContainerNotFoundError(DockerError):
    """Raised when container is not found."""

    def __init__(self, container: str) -> None:
        super().__init__(f"Container '{container}' not found.")


class DockerPermissionError(DockerError):
    """Raised when permission is denied."""

    def __init__(self) -> None:
        super().__init__(
            "Permission denied accessing Docker. "
            "Ensure user is in 'docker' group or has appropriate permissions."
        )


class DockerInvalidContainerError(DockerError):
    """Raised when container name/ID format is invalid."""

    def __init__(self, container: str) -> None:
        super().__init__(f"Invalid container identifier: '{container}'")


# Protocol for the Docker client (allows mocking)
class DockerClientProtocol(Protocol):
    """Protocol for Docker client."""

    @property
    def containers(self) -> Any:
        """Container manager."""
        ...


# Severity inference patterns
SEVERITY_PATTERNS = {
    Severity.CRITICAL: re.compile(
        r"\b(CRITICAL|FATAL|EMERGENCY|ALERT)\b", re.IGNORECASE
    ),
    Severity.ERROR: re.compile(r"\b(ERROR|ERR)\b", re.IGNORECASE),
    Severity.WARN: re.compile(r"\b(WARN|WARNING)\b", re.IGNORECASE),
    Severity.INFO: re.compile(r"\b(INFO|NOTICE)\b", re.IGNORECASE),
    Severity.DEBUG: re.compile(r"\b(DEBUG|TRACE)\b", re.IGNORECASE),
}


def _infer_severity(message: str, json_log: dict[str, Any] | None = None) -> Severity:
    """Infer severity from log message or JSON fields.

    Args:
        message: The log message.
        json_log: Optional JSON log object.

    Returns:
        The inferred severity level.
    """
    # Try to extract from JSON log fields
    if json_log:
        for field in ["level", "severity", "loglevel", "log_level"]:
            if field in json_log:
                try:
                    level_str = str(json_log[field]).upper()
                    return Severity.from_string(level_str)
                except (ValueError, KeyError):
                    continue

    # Pattern matching on message
    for severity, pattern in SEVERITY_PATTERNS.items():
        if pattern.search(message):
            return severity

    # Default to INFO
    return Severity.INFO


def _sanitize_message(message: str) -> str:
    """Remove ANSI escape codes and control characters from message.

    Args:
        message: The log message.

    Returns:
        Sanitized message with ANSI codes removed.
    """
    # Remove ANSI escape sequences
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    message = ansi_escape.sub("", message)

    # Remove other control characters except tab and newline
    message = "".join(
        char if char in ("\t", "\n") or (ord(char) >= 32) else "" for char in message
    )

    return message


def _parse_docker_timestamp(timestamp_str: str) -> datetime:
    """Parse Docker timestamp to datetime.

    Args:
        timestamp_str: ISO format timestamp from Docker.

    Returns:
        Naive datetime in local time.
    """
    try:
        # Docker timestamps are in RFC3339 format with nanosecond precision
        # Example: 2024-01-15T10:23:45.123456789Z
        # Python datetime doesn't support nanoseconds, so we truncate
        if "." in timestamp_str:
            # Split at decimal point
            base, fraction = timestamp_str.split(".")
            # Take only first 6 digits (microseconds)
            fraction = fraction[:6]
            # Reconstruct without timezone letter
            timestamp_str = f"{base}.{fraction}"
            if timestamp_str.endswith("Z"):
                timestamp_str = timestamp_str[:-1]

        # Parse as UTC
        dt = datetime.fromisoformat(timestamp_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)

        # Convert to local time and remove timezone
        return dt.astimezone().replace(tzinfo=None)
    except Exception as e:
        logger.debug("Failed to parse timestamp '%s': %s", timestamp_str, e)
        return datetime.now()


def _parse_log_line(
    line: bytes, container_name: str, container_metadata: dict[str, str]
) -> LogEntry | None:
    """Parse a Docker log line into a LogEntry.

    Args:
        line: Raw log line from Docker.
        container_name: Name of the container.
        container_metadata: Container metadata to include.

    Returns:
        LogEntry object or None if parsing fails.
    """
    try:
        # Decode bytes to string
        line_str = line.decode("utf-8").strip()
        if not line_str:
            return None

        # Try parsing as JSON (json-file driver format)
        try:
            log_obj = json.loads(line_str)
            timestamp_str = log_obj.get("time", "")
            message = log_obj.get("log", "").rstrip("\n")
            stream = log_obj.get("stream", "stdout")

            # Sanitize message to remove ANSI codes
            message = _sanitize_message(message)

            timestamp = _parse_docker_timestamp(timestamp_str) if timestamp_str else datetime.now()
            severity = _infer_severity(message, log_obj)

            # Build metadata
            metadata = container_metadata.copy()
            metadata["stream"] = stream

            return LogEntry(
                timestamp=timestamp,
                severity=severity,
                message=message,
                source=container_name,
                metadata=metadata,
                raw=line_str,
            )
        except (json.JSONDecodeError, KeyError):
            # Not JSON format, try plain text parsing
            pass

        # Plain text format: "2024-01-15T10:23:45.123456789Z log message here"
        # Timestamp is optional
        parts = line_str.split(" ", 1)
        if len(parts) == 2 and "T" in parts[0]:
            timestamp_str, message = parts
            timestamp = _parse_docker_timestamp(timestamp_str)
        else:
            timestamp = datetime.now()
            message = line_str

        # Sanitize message to remove ANSI codes
        message = _sanitize_message(message)

        severity = _infer_severity(message)

        return LogEntry(
            timestamp=timestamp,
            severity=severity,
            message=message,
            source=container_name,
            metadata=container_metadata.copy(),
            raw=line_str,
        )
    except Exception as e:
        logger.debug("Failed to parse log line: %s", e)
        return None


class DockerLogSource:
    """Docker container log source.

    Fetches logs from Docker containers using the Docker SDK.
    Supports filtering by container name/ID, time range, and severity.

    Example:
        >>> source = DockerLogSource(container="nginx")
        >>> async for entry in source.fetch(Filter(limit=100)):
        ...     print(entry.message)
    """

    def __init__(
        self,
        container: str,
        name: str | None = None,
        docker_host: str | None = None,
        client: DockerClientProtocol | None = None,
    ) -> None:
        """Initialize the Docker log source.

        Args:
            container: Container name or ID.
            name: Optional custom display name. Defaults to "Docker: {container}".
            docker_host: Optional Docker daemon URL (e.g., "tcp://host:port").
            client: Optional Docker client (for testing). If not provided,
                   creates a real client using the Docker daemon.

        Raises:
            DockerNotInstalledError: If docker package is not installed.
        """
        if not DOCKER_AVAILABLE and client is None:
            logger.error("Docker support not available - docker package not installed")
            raise DockerNotInstalledError()

        self._container_id = container
        self._custom_name = name
        self._docker_host = docker_host
        self._client = client
        self._container_name: str | None = None
        self._container_metadata: dict[str, str] = {}
        logger.info(
            "DockerLogSource initialized: container=%s, docker_host=%s",
            container,
            docker_host,
        )

    def _get_client(self) -> DockerClientProtocol:
        """Get or create the Docker client.

        Returns:
            The Docker client.

        Raises:
            DockerDaemonError: If connection to Docker daemon fails.
            DockerPermissionError: If permission is denied.
        """
        if self._client is not None:
            logger.debug("Using existing Docker client")
            return self._client

        if not DOCKER_AVAILABLE:
            logger.error("Docker library not available when creating client")
            raise DockerNotInstalledError()

        logger.debug("Creating new Docker client (host: %s)", self._docker_host or "default")
        try:
            if self._docker_host:
                self._client = _docker_module.DockerClient(base_url=self._docker_host)
            else:
                self._client = _docker_module.from_env()
            logger.info("Docker client created successfully")
            return self._client
        except Exception as e:
            error_msg = str(e).lower()
            logger.error("Failed to create Docker client: %s", e)

            if "permission denied" in error_msg:
                logger.error("Permission denied - user may not be in docker group")
                raise DockerPermissionError() from e
            else:
                logger.error("Docker daemon unreachable")
                raise DockerDaemonError() from e

    def _resolve_container(self, client: DockerClientProtocol) -> Any:
        """Resolve container name/ID to container object and cache metadata.

        Args:
            client: The Docker client.

        Returns:
            The container object.

        Raises:
            DockerContainerNotFoundError: If container not found.
        """
        try:
            logger.debug("Resolving container: %s", self._container_id)
            container = client.containers.get(self._container_id)

            # Cache container metadata
            self._container_name = container.name
            attrs = container.attrs

            self._container_metadata = {
                "container_id": container.id[:12],  # Short ID
                "container_name": container.name,
                "image": attrs.get("Config", {}).get("Image", ""),
                "status": attrs.get("State", {}).get("Status", ""),
            }

            # Add image ID
            image_id = attrs.get("Image", "")
            if image_id.startswith("sha256:"):
                image_id = image_id[7:19]  # Short hash
            self._container_metadata["image_id"] = image_id

            # Add labels
            labels = attrs.get("Config", {}).get("Labels") or {}
            for key, value in labels.items():
                self._container_metadata[f"label.{key}"] = str(value)

            logger.info(
                "Container resolved: %s (id: %s, status: %s)",
                self._container_name,
                self._container_metadata["container_id"],
                self._container_metadata["status"],
            )
            return container
        except Exception as e:
            logger.error("Container not found: %s", self._container_id)
            raise DockerContainerNotFoundError(self._container_id) from e

    @property
    def name(self) -> str:
        """Human-readable name for this source."""
        if self._custom_name:
            return self._custom_name
        if self._container_name:
            return f"Docker: {self._container_name}"
        return f"Docker: {self._container_id}"

    @property
    def source_type(self) -> str:
        """Get the source type identifier."""
        return "docker"

    async def fetch(self, log_filter: Filter) -> AsyncIterator[LogEntry]:
        """Fetch logs from Docker container.

        Args:
            log_filter: The filter to apply.

        Yields:
            LogEntry objects from the container.

        Raises:
            DockerDaemonError: If Docker daemon is unreachable.
            DockerContainerNotFoundError: If container is not found.
            DockerPermissionError: If permission is denied.
        """
        logger.info(
            "Fetching logs from container: %s (limit: %d)",
            self._container_id,
            log_filter.limit,
        )
        client = self._get_client()
        container = self._resolve_container(client)

        # Build Docker logs() parameters
        kwargs: dict[str, Any] = {
            "stdout": True,
            "stderr": True,
            "timestamps": True,
        }

        # Time range filtering
        if log_filter.time_range:
            # Docker accepts Unix timestamp or datetime object
            kwargs["since"] = log_filter.time_range.start
            kwargs["until"] = log_filter.time_range.end
            logger.debug(
                "Time range filter: %s to %s",
                log_filter.time_range.start,
                log_filter.time_range.end,
            )

        # Fetch logs in executor (blocking call)
        loop = asyncio.get_running_loop()
        count = 0
        parse_errors = 0

        try:
            logger.debug("Executing container.logs()...")
            # Get logs as iterator
            logs_iter = await loop.run_in_executor(
                None, lambda: container.logs(**kwargs, stream=True)
            )

            # Process log lines
            for line in logs_iter:
                if count >= log_filter.limit:
                    break

                entry = _parse_log_line(
                    line, self._container_name or self._container_id, self._container_metadata
                )
                if entry is None:
                    parse_errors += 1
                    continue

                # Apply client-side filtering
                if not entry.matches_filter(log_filter):
                    logger.debug("Client-side filtered out: %s", entry.message[:50])
                    continue

                yield entry
                count += 1

                # Yield to event loop periodically
                if count % 100 == 0:
                    await asyncio.sleep(0)

            logger.info(
                "Docker fetch complete: %d entries returned, %d parse errors",
                count,
                parse_errors,
            )

        except Exception as e:
            logger.error("Docker fetch failed: %s (%s)", e, type(e).__name__)
            raise DockerError(f"Failed to fetch logs: {e}") from e

    def validate_filter(self, log_filter: Filter) -> list[str]:
        """Validate a filter for Docker.

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
        """Get available filter fields for Docker.

        Returns:
            List of Docker-specific filter fields.
        """
        return [
            FilterField(name="container", label="Container", required=True),
            FilterField(
                name="severity",
                label="Severity",
                options=[s.value for s in Severity],
            ),
        ]
