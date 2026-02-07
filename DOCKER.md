# Docker Logs Support - Implementation Plan

## Overview

Add support for viewing Docker container logs within LogView. This will allow users to monitor logs from Docker containers alongside other log sources (syslog, GCP, GKE, log files).

## Goals

1. **View logs from any Docker container** (running or stopped)
2. **Filter by container name, ID, or labels**
3. **Support time-based filtering** (--since, --until)
4. **Parse Docker log formats** (JSON and plain text)
5. **Extract container metadata** (name, ID, image, labels, status)
6. **Handle both local and remote Docker daemons**
7. **Graceful error handling** when Docker is unavailable
8. **Optional dependency** - Docker SDK only required if using Docker contexts

## Architecture

### 1. Docker Adapter (`src/logview/adapters/docker.py`)

Implements the `LogSource` protocol:

```python
class DockerLogSource:
    """Docker container log source.

    Fetches logs from Docker containers using the Docker SDK.
    Supports filtering by container name/ID, time range, and severity.
    """

    def __init__(
        self,
        container: str,  # Container name or ID
        name: str | None = None,  # Display name
        client: DockerClient | None = None,  # For testing/custom daemon
    ):
        ...

    @property
    def name(self) -> str:
        """Returns 'Docker: <container_name>'"""
        ...

    async def fetch(self, log_filter: Filter) -> AsyncIterator[LogEntry]:
        """Fetch logs from Docker container."""
        ...

    def validate_filter(self, log_filter: Filter) -> list[str]:
        """Validate filter for Docker constraints."""
        ...

    def available_filters(self) -> list[FilterField]:
        """Return Docker-specific filter fields."""
        ...
```

#### Client Protocol (for testing):

```python
class DockerClientProtocol(Protocol):
    """Protocol for Docker client (allows mocking)."""

    @property
    def containers(self) -> Any:
        """Container manager."""
        ...
```

This follows the same pattern as `LoggingClientProtocol` in the GCP adapter, making unit tests cleaner.

#### Key Features:

1. **Optional Docker SDK dependency**:
   - Check if `docker` package is available
   - Raise `DockerNotInstalledError` with helpful message if missing
   - Support installation via `pip install logview-ag[docker]`

2. **Container resolution**:
   - Accept container name or ID
   - Resolve to full container ID on init
   - Cache container metadata (name, image, labels)

3. **Log fetching**:
   - Use `container.logs()` with appropriate parameters
   - Parse timestamps from Docker log format
   - Extract severity from log message (heuristic-based or JSON logs)
   - Handle both JSON logs (when using json-file driver) and plain text

4. **Filtering**:
   - **Time range**: Map to `--since` and `--until` Docker parameters
   - **Text search**: Client-side filtering on log messages
   - **Source filter**: Match against container name
   - **Severity**: Parse from JSON logs if available, or use heuristics

5. **Error handling**:
   - `DockerNotInstalledError`: Docker SDK not available
   - `DockerDaemonError`: Docker daemon unreachable
   - `DockerContainerNotFoundError`: Container doesn't exist
   - `DockerPermissionError`: No permission to access Docker
   - `DockerInvalidContainerError`: Invalid container name/ID format

### 2. Configuration Schema (`src/logview/config/schema.py`)

Add `DockerContext` to the configuration:

```python
class DockerContext(BaseModel):
    """Docker container log source configuration."""

    name: str  # Display name (e.g., "Docker: nginx")
    type: Literal["docker"]
    container: str  # Container name or ID
    docker_host: str | None = None  # Optional: tcp://host:port or unix:///var/run/docker.sock
```

Update the `Context` union type:

```python
Context = Annotated[
    GKEContext | GCPContext | SyslogContext | MockContext | LogFileContext | DockerContext,
    Field(discriminator="type"),
]
```

### 3. Docker Log Format Parsing

Docker logs can be in two formats:

#### JSON Format (json-file driver):
```json
{"log":"2024-01-15 10:23:45 INFO Starting application\n","stream":"stdout","time":"2024-01-15T10:23:45.123456789Z"}
```

#### Plain Text Format:
```
2024-01-15T10:23:45.123456789Z 2024-01-15 10:23:45 INFO Starting application
```

The adapter will:
1. Detect the format (JSON vs plain text)
2. Parse timestamps appropriately
3. Extract log message
4. Infer severity from message content or structured fields

### 4. Severity Inference

For containers without structured logging:

1. **Pattern matching** for common log levels:
   - `ERROR`, `CRITICAL`, `FATAL` → `Severity.ERROR`
   - `WARN`, `WARNING` → `Severity.WARN`
   - `INFO`, `NOTICE` → `Severity.INFO`
   - `DEBUG`, `TRACE` → `Severity.DEBUG`
   - Default: `Severity.INFO`

2. **JSON logs**: Check for `level`, `severity`, `loglevel` fields

### 5. Metadata Extraction

Each `LogEntry` will include rich metadata:

```python
metadata = {
    "container_id": "abc123...",
    "container_name": "nginx",
    "image": "nginx:latest",
    "image_id": "sha256:...",
    "labels.app": "web",
    "labels.env": "prod",
    "status": "running",
    "stream": "stdout",  # or "stderr"
}
```

### 6. Integration with App (`src/logview/app.py`)

Update `_create_log_source()` to handle Docker contexts:

```python
def _create_log_source(self, context: Context) -> LogSource:
    if context.type == "docker":
        from logview.adapters.docker import DockerLogSource
        return DockerLogSource(
            container=context.container,
            name=context.name,
            docker_host=context.docker_host,
        )
    # ... existing context types
```

### 7. Docker Discovery (Optional Enhancement)

Add automatic discovery of running Docker containers:

```python
def discover_docker_containers() -> list[DockerContext]:
    """Discover running Docker containers on the local daemon.

    Returns:
        List of DockerContext objects for running containers.
    """
    if not DOCKER_AVAILABLE:
        return []

    try:
        client = docker.from_env()
        containers = client.containers.list(all=False)

        contexts = []
        for container in containers:
            contexts.append(DockerContext(
                name=f"Docker: {container.name}",
                type="docker",
                container=container.name,
            ))

        return contexts
    except Exception:
        return []
```

This can be integrated into the context detection modal (keyboard shortcut 'd').

## Implementation Steps

### Phase 1: Core Adapter
1. **Create `src/logview/adapters/docker.py`**
   - Implement `DockerLogSource` class
   - Handle optional dependency (docker SDK)
   - Implement error types
   - Add logging throughout

2. **Add Docker configuration schema**
   - Update `src/logview/config/schema.py`
   - Add `DockerContext` model
   - Update `Context` union type

3. **Write unit tests** (`tests/unit/test_docker_adapter.py`)
   - Test container resolution
   - Test log parsing (JSON and plain text)
   - Test filtering (time, text, severity)
   - Test error handling
   - Mock Docker SDK client

### Phase 2: Integration
4. **Integrate with main app**
   - Update `src/logview/app.py` to handle Docker contexts
   - Update context switcher to display Docker sources

5. **Write integration tests** (`tests/integration/test_docker.py`)
   - Test with real Docker containers (if available)
   - Skip if Docker not available
   - Test end-to-end log fetching

### Phase 3: Documentation & Quality
6. **Update documentation**
   - README.md: Add Docker section, installation instructions
   - CHANGELOG.md: Add Docker support to [Unreleased]
   - ACTIONS.md: Log implementation progress
   - Example config: Add Docker context example

7. **Run quality checks**
   - pytest: All tests pass
   - mypy: No type errors
   - ruff: No lint errors

8. **Create pull request**
   - Descriptive PR title and body
   - Summary of changes
   - Test plan

## Dependencies

### Docker SDK for Python

Add to `pyproject.toml`:

```toml
[project.optional-dependencies]
docker = ["docker>=7.0.0"]
```

Install with: `pip install logview-ag[docker]`

### Why Optional?

- Not all users need Docker support
- Docker SDK has significant dependencies
- Follows same pattern as GCP/GKE (optional extras)

## Error Handling

### Custom Exception Hierarchy

```python
class DockerError(Exception):
    """Base exception for Docker adapter errors."""
    pass

class DockerNotInstalledError(DockerError):
    """Raised when Docker SDK is not installed."""
    def __init__(self):
        super().__init__(
            "Docker support requires the docker package. "
            "Install with: pip install logview-ag[docker]"
        )

class DockerDaemonError(DockerError):
    """Raised when Docker daemon is unreachable."""
    def __init__(self):
        super().__init__(
            "Cannot connect to Docker daemon. "
            "Ensure Docker is running and accessible."
        )

class DockerContainerNotFoundError(DockerError):
    """Raised when container is not found."""
    def __init__(self, container: str):
        super().__init__(f"Container '{container}' not found.")

class DockerPermissionError(DockerError):
    """Raised when permission is denied."""
    def __init__(self):
        super().__init__(
            "Permission denied accessing Docker. "
            "Ensure user is in 'docker' group or has appropriate permissions."
        )
```

## Testing Strategy

### Unit Tests

1. **Container resolution**:
   - Valid container name
   - Valid container ID
   - Invalid container (error)
   - Container not found (error)

2. **Log parsing**:
   - JSON format logs
   - Plain text format logs
   - Mixed format handling
   - Timestamp parsing
   - Severity inference

3. **Filtering**:
   - Time range filtering
   - Text search
   - Source filter (container name matching)
   - Severity filtering

4. **Error handling**:
   - Docker SDK not installed
   - Docker daemon unreachable
   - Container not found
   - Permission denied

### Integration Tests

1. **Real Docker container** (conditional):
   - Create test container
   - Write logs to it
   - Fetch and verify logs
   - Clean up container
   - Skip if Docker not available

2. **Multiple containers**:
   - Verify container isolation
   - Correct source attribution

### Mock Strategy

Use `unittest.mock` to mock Docker SDK client:

```python
from unittest.mock import MagicMock, patch

@patch('logview.adapters.docker.docker')
def test_fetch_logs(mock_docker):
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.logs.return_value = [
        b'{"log":"test message\n","stream":"stdout","time":"2024-01-15T10:00:00Z"}\n'
    ]
    mock_client.containers.get.return_value = mock_container
    mock_docker.from_env.return_value = mock_client

    source = DockerLogSource(container="test")
    # ... test fetch
```

## Example Configuration

```json
{
  "contexts": [
    {
      "name": "Docker: nginx",
      "type": "docker",
      "container": "nginx"
    },
    {
      "name": "Docker: postgres",
      "type": "docker",
      "container": "my-postgres-db"
    },
    {
      "name": "Docker: remote-app",
      "type": "docker",
      "container": "app",
      "docker_host": "tcp://192.168.1.100:2375"
    }
  ]
}
```

## UI/UX Considerations

1. **Context switcher**: Docker sources appear alongside GCP, GKE, syslog
2. **Source field**: Shows container name (e.g., "nginx")
3. **Metadata view**: Rich container metadata (image, labels, status)
4. **Error messages**: Clear instructions when Docker unavailable
5. **Discovery modal**: Optional "Discover Docker Containers" feature

## Performance Considerations

1. **Lazy loading**: Don't connect to Docker daemon until `fetch()` is called
2. **Streaming**: Use Docker SDK's streaming API for large log volumes
3. **Batching**: Fetch logs in batches (similar to GCP adapter)
4. **Caching**: Cache container metadata on initialization
5. **Limit enforcement**: Respect `filter.limit` to avoid memory issues

## Security Considerations

1. **No credential storage**: Rely on Docker daemon authentication
2. **Docker socket permissions**: Document security implications
3. **Remote daemon**: Warn about unencrypted TCP connections
4. **Container isolation**: No cross-container data leakage
5. **Audit logging**: Log all Docker API interactions

## Future Enhancements (Out of Scope)

1. **Docker Compose support**: View logs from all services in a compose project
2. **Multi-container aggregation**: Merge logs from multiple containers
3. **Live tailing**: Real-time log streaming with `--follow`
4. **Log driver support**: Handle different Docker log drivers (json-file, journald, syslog)
5. **Docker Swarm**: Support for Docker Swarm services
6. **Kubernetes via Docker**: Bridge to Kubernetes containers

## Success Criteria

- [ ] DockerLogSource implements LogSource protocol
- [ ] Unit tests achieve >70% coverage
- [ ] Integration tests pass (when Docker available)
- [ ] mypy passes with no errors
- [ ] ruff passes with no errors
- [ ] Documentation updated (README, CHANGELOG, example config)
- [ ] Docker dependency is optional
- [ ] Graceful error handling when Docker unavailable
- [ ] PR created with comprehensive summary

## Timeline

This plan will be implemented incrementally in separate commits:

1. **Commit 1**: Core adapter implementation
2. **Commit 2**: Configuration schema and integration
3. **Commit 3**: Unit tests
4. **Commit 4**: Integration tests
5. **Commit 5**: Documentation updates
6. **Commit 6**: Quality fixes and refinements

Each commit will maintain passing tests and quality checks.
