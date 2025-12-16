# Server-Side Source Filtering Implementation Plan

## Overview

Add server-side source filtering to GCP and GKE adapters by translating `source_filter` values into Cloud Logging API resource label filters. This reduces data transfer from the API and improves query performance.

## Current Behavior vs. Proposed

### Current (Client-Side Only)
1. User sets `source_filter` in Filter (e.g., "api-server")
2. Adapter calls Cloud Logging API **without** source filtering
3. API returns **all** log entries
4. Client-side `LogEntry.matches_filter()` does substring matching
5. Large data transfer for filtered results

### Proposed (Hybrid Server + Client)
1. User sets `source_filter` in Filter
2. Adapter **detects pattern** and **builds resource label filter**
3. Cloud Logging API filters server-side (reduces data)
4. Client receives pre-filtered entries
5. Client-side fallback for unsupported patterns (mid-string matches)

## User Requirements (Confirmed)

- ✓ **Smart detection**: Auto-detect namespace/pod format, wildcards
- ✓ **Prioritized filtering**: Match source construction priority (pod → instance → function for GCP)
- ✓ **Prefix wildcard conversion**: Convert "api" to "api*" for server-side matching
- ✓ **Hybrid approach**: Server-side when possible, client-side fallback

## Architecture

### GCP Adapter: Source Construction Priority

Source field built from (gcp.py:285-295):
```python
if "pod_name" in labels:       source = labels["pod_name"]
elif "instance_id" in labels:  source = labels["instance_id"]
elif "function_name" in labels: source = labels["function_name"]
else:                           source = project_id
```

**Server-side strategy**: Filter by `resource.labels.pod_name` (most common)
**Client-side fallback**: Match instance_id, function_name, project_id

### GKE Adapter: Source Construction Logic

Source field built from (gke.py:328-338):
```python
if namespace and pod_name:  source = f"{namespace}/{pod_name}"
elif pod_name:              source = pod_name
else:                       source = cluster
```

**Server-side strategy**:
- If contains `/`: Filter by namespace AND pod
- Otherwise: Filter by pod_name

## Pattern Detection Logic

### GCP Pattern Detection

```python
def _detect_gcp_source_pattern(source_filter: str) -> tuple[str, bool]:
    """Detect GCP source filter pattern.

    Returns:
        (filter_string, client_side_needed)
    """
    # Invalid patterns → client-side only
    if "/" in source_filter:  # Namespace format invalid for GCP
        return ("", True)

    if "*" in source_filter and not source_filter.endswith("*"):
        # Mid-string or leading wildcard
        return ("", True)

    # Convert plain string to prefix wildcard
    pattern = source_filter if source_filter.endswith("*") else source_filter + "*"

    # Build regex filter for pod_name
    prefix = pattern[:-1]
    escaped = re.escape(prefix.replace("\\", "\\\\").replace('"', '\\"'))
    filter_str = f'resource.labels.pod_name=~"^{escaped}"'

    # Client-side still needed for instance_id, function_name fallback
    return (filter_str, True)
```

### GKE Pattern Detection

```python
def _detect_gke_source_pattern(source_filter: str) -> tuple[list[str], bool]:
    """Detect GKE source filter pattern.

    Returns:
        (filter_parts_list, client_side_needed)
    """
    parts = []

    if "/" in source_filter:
        # Namespace/pod format
        namespace, pod = source_filter.split("/", 1)

        # Wildcard in namespace → client-side fallback
        if "*" in namespace:
            return ([], True)

        # Exact namespace
        parts.append(f'resource.labels.namespace_name="{_escape_filter_value(namespace)}"')

        # Pod with optional wildcard
        if pod.endswith("*"):
            pod_filter = _build_wildcard_filter("pod", pod, "resource.labels.pod_name")
            parts.append(pod_filter)
            client_needed = False  # Explicit wildcard
        else:
            # Convert to prefix wildcard
            pod_filter = _build_wildcard_filter("pod", pod + "*", "resource.labels.pod_name")
            parts.append(pod_filter)
            client_needed = True  # Need substring matching

        return (parts, client_needed)
    else:
        # Pod-only format
        pattern = source_filter if source_filter.endswith("*") else source_filter + "*"

        pod_filter = _build_wildcard_filter("pod", pattern, "resource.labels.pod_name")
        parts.append(pod_filter)

        client_needed = not source_filter.endswith("*")
        return (parts, client_needed)
```

## Implementation Steps

### Step 1: Add Helper Functions

**File**: `src/logview/adapters/gcp.py`

Add before `_build_filter()`:
```python
def _build_source_filter_gcp(source_filter: str) -> tuple[str, bool]:
    """Build GCP resource label filter for source_filter.

    Args:
        source_filter: Source filter value (e.g., "api-server", "api-*")

    Returns:
        Tuple of (filter_string, client_side_needed)
    """
    if not source_filter:
        return ("", False)

    # Slash invalid for GCP
    if "/" in source_filter:
        logger.debug("Source filter contains '/', using client-side filtering")
        return ("", True)

    # Convert to prefix wildcard
    pattern = source_filter if source_filter.endswith("*") else source_filter + "*"

    # Validate wildcard position
    if "*" in pattern and not pattern.endswith("*"):
        logger.debug("Mid-string wildcard, using client-side filtering")
        return ("", True)

    # Build filter for pod_name (most common source)
    prefix = pattern[:-1]
    if not prefix:
        logger.debug("Wildcard-only pattern, using client-side filtering")
        return ("", True)

    # Escape for Cloud Logging
    safe_prefix = prefix.replace("\\", "\\\\").replace('"', '\\"')
    escaped_prefix = re.escape(safe_prefix)
    filter_str = f'resource.labels.pod_name=~"^{escaped_prefix}"'

    # Client-side still needed for non-pod sources
    return (filter_str, True)
```

**File**: `src/logview/adapters/gke.py`

Add before `_build_gke_filter()`:
```python
def _build_source_filter_gke(source_filter: str) -> tuple[list[str], bool]:
    """Build GKE resource label filters for source_filter.

    Args:
        source_filter: Source filter value

    Returns:
        Tuple of (filter_parts, client_side_needed)
    """
    if not source_filter:
        return ([], False)

    parts = []
    client_side_needed = False

    if "/" in source_filter:
        # Namespace/pod format
        ns_pod = source_filter.split("/", 1)
        namespace, pod = ns_pod[0], ns_pod[1]

        # Wildcard in namespace problematic with AND
        if "*" in namespace:
            logger.debug("Wildcard in namespace, using client-side filtering")
            return ([], True)

        # Exact namespace
        parts.append(f'resource.labels.namespace_name="{_escape_filter_value(namespace)}"')

        # Pod with optional wildcard
        if "*" in pod:
            if not pod.endswith("*"):
                return ([], True)  # Mid-string wildcard
            try:
                pod_filter = _build_wildcard_filter("pod", pod, "resource.labels.pod_name")
                parts.append(pod_filter)
            except GKEInvalidFilterError:
                return ([], True)
        else:
            # Convert to prefix
            pod_filter = _build_wildcard_filter("pod", pod + "*", "resource.labels.pod_name")
            parts.append(pod_filter)
            client_side_needed = True  # Need exact substring matching
    else:
        # Pod-only format
        pattern = source_filter if source_filter.endswith("*") else source_filter + "*"

        if "*" in pattern and not pattern.endswith("*"):
            return ([], True)

        try:
            pod_filter = _build_wildcard_filter("pod", pattern, "resource.labels.pod_name")
            parts.append(pod_filter)
            client_side_needed = not source_filter.endswith("*")
        except GKEInvalidFilterError:
            return ([], True)

    return (parts, client_side_needed)
```

### Step 2: Modify Filter Building Functions

**File**: `src/logview/adapters/gcp.py`

Change `_build_filter()` signature and return:
```python
def _build_filter(
    log_filter: Filter,
    log_name: str | None = None,
    resource_type: str | None = None,
) -> tuple[str, bool]:  # NEW: Return tuple
    """Build Cloud Logging filter string.

    Returns:
        Tuple of (filter_string, client_side_needed)
    """
    parts = []

    # ... existing filter logic ...

    # NEW: Source filter
    client_side_needed = False
    if log_filter.source_filter:
        source_filter_str, needs_client = _build_source_filter_gcp(log_filter.source_filter)
        if source_filter_str:
            parts.append(source_filter_str)
        client_side_needed = needs_client

    return (" AND ".join(parts) if parts else "", client_side_needed)
```

**File**: `src/logview/adapters/gke.py`

Change `_build_gke_filter()` signature and return:
```python
def _build_gke_filter(
    log_filter: Filter,
    project: str,
    cluster: str,
    location: str | None = None,
    default_namespace: str | None = None,
) -> tuple[str, bool]:  # NEW: Return tuple
    """Build GKE Cloud Logging filter string.

    Returns:
        Tuple of (filter_string, client_side_needed)
    """
    parts = []

    # ... existing filter logic ...

    # NEW: Source filter
    client_side_needed = False
    if log_filter.source_filter:
        source_parts, needs_client = _build_source_filter_gke(log_filter.source_filter)
        parts.extend(source_parts)
        client_side_needed = needs_client

    return (" AND ".join(parts), client_side_needed)
```

### Step 3: Update Fetch Methods

**File**: `src/logview/adapters/gcp.py` - `GCPLogSource.fetch()`

Line ~458 (filter building):
```python
# OLD:
filter_str = _build_filter(
    log_filter,
    log_name=self._log_name,
    resource_type=self._resource_type,
)

# NEW:
filter_str, needs_client_filter = _build_filter(
    log_filter,
    log_name=self._log_name,
    resource_type=self._resource_type,
)
logger.debug(
    "Filter: %s, client-side needed: %s",
    filter_str or "(empty)",
    needs_client_filter
)
```

Line ~505 (batch processing):
```python
# OLD:
for entry in batch:
    try:
        log_entry = _parse_log_entry(entry, self._project_id)
        # Apply client-side filtering (e.g., source_filter)
        if log_entry.matches_filter(log_filter):
            yield log_entry
            count += 1

# NEW:
for entry in batch:
    try:
        log_entry = _parse_log_entry(entry, self._project_id)

        # Apply client-side filtering if needed
        # (server-side already filtered, but may need additional checks)
        if needs_client_filter and not log_entry.matches_filter(log_filter):
            logger.debug("Client-side filtered out: %s", log_entry.source)
            continue

        yield log_entry
        count += 1
```

**File**: `src/logview/adapters/gke.py` - `GKELogSource.fetch()`

Same pattern as GCP above (lines ~543, ~587).

### Step 4: Add Tests

**File**: `tests/unit/test_gcp_adapter.py`

Add test class:
```python
class TestGCPSourceFiltering:
    def test_source_filter_plain_string(self):
        """Test plain string converts to prefix wildcard"""
        log_filter = Filter(source_filter="api")
        filter_str, needs_client = _build_filter(log_filter)
        assert 'resource.labels.pod_name=~"^api"' in filter_str
        assert needs_client is True

    def test_source_filter_explicit_wildcard(self):
        """Test explicit wildcard preserved"""
        log_filter = Filter(source_filter="api-*")
        filter_str, needs_client = _build_filter(log_filter)
        assert 'resource.labels.pod_name=~"^api\\-"' in filter_str
        assert needs_client is True

    def test_source_filter_with_slash_falls_back(self):
        """Test namespace/pod format falls back to client-side"""
        log_filter = Filter(source_filter="default/api")
        filter_str, needs_client = _build_filter(log_filter)
        assert "pod_name" not in filter_str
        assert needs_client is True

    @pytest.mark.asyncio
    async def test_fetch_with_source_filter_includes_in_api_call(self):
        """Test source_filter passed to API"""
        client = MockLoggingClient(entries=[])
        source = GCPLogSource(project_id="test-project", client=client)

        async for _ in source.fetch(Filter(source_filter="api")):
            pass

        assert 'resource.labels.pod_name=~"^api"' in client.last_filter

    @pytest.mark.asyncio
    async def test_hybrid_filtering_non_pod_sources(self):
        """Test client-side handles instance_id, function_name"""
        entries = [
            MockLogEntry(
                text_payload="pod log",
                resource=MockResource(labels={"pod_name": "api-server"}),
            ),
            MockLogEntry(
                text_payload="instance log",
                resource=MockResource(labels={"instance_id": "api-vm-001"}),
            ),
            MockLogEntry(
                text_payload="function log",
                resource=MockResource(labels={"function_name": "worker"}),
            ),
        ]
        client = MockLoggingClient(entries=entries)
        source = GCPLogSource(project_id="test-project", client=client)

        results = []
        async for entry in source.fetch(Filter(source_filter="api")):
            results.append(entry)

        # Server-side filters pod_name, client-side handles instance_id
        assert len(results) == 2  # pod + instance, not function
```

**File**: `tests/unit/test_gke_adapter.py`

Add test class:
```python
class TestGKESourceFiltering:
    def test_source_filter_namespace_pod(self):
        """Test namespace/pod format"""
        log_filter = Filter(source_filter="default/api-server")
        filter_str, needs_client = _build_gke_filter(
            log_filter,
            project="test-project",
            cluster="test-cluster",
        )
        assert 'resource.labels.namespace_name="default"' in filter_str
        assert 'resource.labels.pod_name=~"^api\\-server"' in filter_str
        assert needs_client is True  # Added wildcard for substring

    def test_source_filter_pod_only(self):
        """Test pod-only format"""
        log_filter = Filter(source_filter="api")
        filter_str, needs_client = _build_gke_filter(
            log_filter,
            project="test-project",
            cluster="test-cluster",
        )
        assert 'resource.labels.pod_name=~"^api"' in filter_str
        assert needs_client is True

    def test_source_filter_wildcard_in_namespace_falls_back(self):
        """Test wildcard in namespace falls back"""
        log_filter = Filter(source_filter="prod-*/api")
        filter_str, needs_client = _build_gke_filter(
            log_filter,
            project="test-project",
            cluster="test-cluster",
        )
        assert "namespace_name" not in filter_str
        assert needs_client is True
```

## Edge Cases Handled

1. ✓ Empty source_filter → No filtering
2. ✓ Wildcard-only (`*`) → Client-side fallback
3. ✓ Mid-string wildcards (`api-*-server`) → Client-side fallback
4. ✓ Leading wildcards (`*-server`) → Client-side fallback
5. ✓ Special characters → Proper escaping
6. ✓ GCP namespace/pod format → Client-side fallback (invalid)
7. ✓ GKE wildcard in namespace → Client-side fallback
8. ✓ Multiple source labels → Client-side handles non-pod labels
9. ✓ Empty results → Return empty gracefully
10. ✓ Integration with existing filters → AND-join all conditions

## Performance Impact

### Benefits
- **Reduced API data transfer**: Filter at source reduces network overhead
- **Faster queries**: API filters more efficiently than client-side iteration
- **Lower memory usage**: Fewer entries to process in memory

### Example Metrics (Expected)
- Large project (100K+ entries): **80-90% reduction** in data transferred
- Specific pod filter: **95%+ reduction** in data
- Query time: **2-5x faster** for filtered queries

## Migration & Compatibility

- ✓ **100% backward compatible**: No API changes to Filter or LogEntry
- ✓ **Transparent**: Existing code gets performance boost automatically
- ✓ **No breaking changes**: Client-side filtering still works as fallback

## Files Modified

### Core Implementation
- `src/logview/adapters/gcp.py` - Add `_build_source_filter_gcp()`, modify `_build_filter()` and `fetch()`
- `src/logview/adapters/gke.py` - Add `_build_source_filter_gke()`, modify `_build_gke_filter()` and `fetch()`

### Tests
- `tests/unit/test_gcp_adapter.py` - Add `TestGCPSourceFiltering` class
- `tests/unit/test_gke_adapter.py` - Add `TestGKESourceFiltering` class

### Documentation
- `ACTIONS.md` - Log implementation
- `CHANGELOG.md` - Document feature (version bump)
- `README.md` - Document server-side filtering behavior
