# LogView TUI - Project Plan

A testable, responsive log viewer TUI with pluggable log source contexts.

## Core Principles

### 1. Security
- **No plaintext credentials**: Use system keyring or environment variables for secrets
- **Delegate authentication**: Leverage existing auth tools (gcloud, kubectl) rather than handling credentials directly
- **Input sanitization**: All user input validated before constructing queries
- **Minimal permissions**: Request only read access to log sources
- **No sensitive data in logs**: Application logs must never contain credentials or PII

### 2. Testability
- **Interface-driven design**: All log sources implement a common protocol/ABC
- **Dependency injection**: External services injected, never instantiated directly
- **Pure business logic**: Separate pure functions from I/O operations
- **Mock adapters**: Every log source has a corresponding mock for testing
- **Property-based tests**: Filter parsing and query construction use hypothesis

### 3. Simplicity of User Interface
- **Single main view**: Log list is always visible and primary
- **Modal pop-ups**: All configuration/selection via dismissable overlays
- **Consistent keybindings**: Same keys work everywhere (Esc to dismiss, Enter to select)
- **Progressive disclosure**: Show simple options first, advanced only when needed
- **Keyboard-first**: Full functionality without mouse (mouse optional)

---

## Technology Stack

### Recommended: Python + Textual

**Rationale:**
- Textual is a modern, reactive TUI framework with excellent testing support
- Built-in CSS-like styling for responsive layouts
- Strong typing with Protocol classes enables interface-driven design
- Rich ecosystem for cloud integrations (google-cloud-logging, kubernetes)
- Async-first architecture ideal for streaming logs
- pytest + hypothesis provide excellent testing story
- Wide developer familiarity

**Dependencies:**
```
textual>=0.45.0
google-cloud-logging>=3.0.0
kubernetes>=28.0.0
pydantic>=2.0.0
httpx>=0.25.0
pytest>=7.0.0
pytest-asyncio>=0.21.0
hypothesis>=6.0.0
```

**Alternatives considered:**
- Go + Bubbletea: Excellent but smaller developer pool
- Rust + Ratatui: Performance overkill, steeper learning curve

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        TUI Layer                            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │  ListView   │ │ FilterPopup │ │ DetailPopup │  ...      │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     Core Domain                             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │  LogEntry   │ │   Filter    │ │   Context   │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Adapter Layer                             │
│  ┌───────┐ ┌───────┐ ┌─────────┐ ┌─────────┐ ┌───────┐    │
│  │  GCP  │ │  GKE  │ │ Syslog  │ │ LogFile │ │ Mock  │    │
│  └───────┘ └───────┘ └─────────┘ └─────────┘ └───────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Key Interfaces

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import AsyncIterator, Protocol
import json


class Severity(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class TimeRange:
    start: datetime
    end: datetime


@dataclass(frozen=True)
class Filter:
    time_range: TimeRange | None = None
    fields: dict[str, str] | None = None  # context-specific fields
    text_search: str | None = None
    severity: Severity | None = None
    limit: int = 1000


@dataclass
class LogEntry:
    timestamp: datetime
    severity: Severity
    message: str
    source: str
    metadata: dict[str, str]
    raw: str  # original JSON payload for detail view

    def to_json(self) -> str:
        return json.dumps({
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity.value,
            "message": self.message,
            "source": self.source,
            "metadata": self.metadata,
        })


@dataclass
class FilterField:
    name: str
    label: str
    required: bool = False
    options: list[str] | None = None  # if enumerable


class LogSource(Protocol):
    """Protocol that all log providers must implement."""

    @property
    def name(self) -> str:
        """Human-readable name for this source."""
        ...

    async def fetch(self, filter: Filter) -> AsyncIterator[LogEntry]:
        """Fetch logs matching the filter."""
        ...

    def validate_filter(self, filter: Filter) -> list[str]:
        """Return list of validation errors, empty if valid."""
        ...

    def available_filters(self) -> list[FilterField]:
        """Return list of filter fields this source supports."""
        ...
```

---

## Project Structure

```
logview/
├── src/
│   └── logview/
│       ├── __init__.py
│       ├── __main__.py           # Entry point
│       ├── app.py                # Main Textual application
│       ├── adapters/             # Log source implementations
│       │   ├── __init__.py
│       │   ├── base.py           # Protocol definitions
│       │   ├── gcp.py
│       │   ├── gke.py
│       │   ├── syslog.py
│       │   ├── logfile.py        # Generic log file adapter
│       │   ├── discovery.py      # Log file discovery service
│       │   └── mock.py           # For testing
│       ├── domain/               # Core business logic
│       │   ├── __init__.py
│       │   ├── models.py         # LogEntry, Filter, etc.
│       │   ├── filter.py         # Filter parsing/validation
│       │   └── context.py        # Context management
│       ├── ui/                   # TUI components
│       │   ├── __init__.py
│       │   ├── widgets/
│       │   │   ├── __init__.py
│       │   │   ├── log_list.py   # Main log list view
│       │   │   ├── status_bar.py
│       │   │   └── log_entry.py  # Single log row
│       │   ├── screens/
│       │   │   ├── __init__.py
│       │   │   ├── main.py       # Main screen
│       │   │   ├── context.py    # Context selector modal
│       │   │   ├── filter.py     # Filter editor modal
│       │   │   ├── detail.py     # Log detail modal
│       │   │   └── help.py       # Help modal
│       │   └── styles/
│       │       ├── __init__.py
│       │       └── theme.tcss    # Textual CSS
│       └── config/
│           ├── __init__.py
│           ├── loader.py         # JSON config loading
│           └── schema.py         # Pydantic models for config
├── tests/
│   ├── __init__.py
│   ├── conftest.py               # pytest fixtures
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_models.py
│   │   ├── test_filter.py
│   │   └── test_config.py
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_syslog.py
│   │   └── test_mock_adapter.py
│   └── ui/
│       ├── __init__.py
│       └── test_app.py           # Textual pilot tests
├── configs/
│   └── example.json              # Example configuration
├── pyproject.toml
├── README.md
├── CLAUDE.md
└── PLAN.md
```

---

## Iterative Development Phases

### Phase 1: Foundation (MVP) ✅ COMPLETE
**Goal:** Runnable TUI with mock data, establishing patterns for all future work.

**Deliverables:**
- [x] Project scaffolding (pyproject.toml, src layout)
- [x] Core domain models with Pydantic (LogEntry, Filter, Severity)
- [x] LogSource protocol definition
- [x] Mock adapter generating fake log data
- [x] Basic Textual app shell
- [x] Main list view displaying mock logs
- [x] Scrolling and basic navigation
- [x] Unit tests for domain types
- [x] Integration test for mock adapter

**Testing strategy:**
- Domain types: pytest with parametrized tests
- Mock adapter: Verify it implements protocol correctly
- UI: Textual's pilot testing framework

**Exit criteria:**
- `pytest` passes with >70% coverage on domain
- Running `python -m logview` displays scrollable fake logs
- Type checking passes (`mypy src/`)

**Completed:** 2024-12 - Initial commit with full project structure

---

### Phase 2: Local Log Source (Syslog) ✅ COMPLETE
**Goal:** First real log source, proving the adapter pattern works.

**Deliverables:**
- [x] Syslog adapter (file-based, reads standard syslog format)
- [x] Syslog line parser with timestamp extraction
- [x] Filter modal UI (time range, severity, text search)
- [x] Log detail modal (scrollable, formatted JSON, copy support)
- [x] Context selector modal (switch between available sources)
- [x] Wire up context switching in main app
- [x] Error handling (file access, parse errors, display in UI)
- [x] Load configuration from JSON file on startup

**Implementation approach:**
1. Focus on file-based syslog parsing only (not journalctl - different format)
2. Support common syslog formats (RFC 3164, RFC 5424)
3. Use sample log files for testing (don't require system access)
4. Graceful degradation when file not accessible

**Filter fields for syslog:**
- Time range (start, end) with quick presets (1h, 6h, 24h)
- Severity (minimum level)
- Text search (case-insensitive substring)
- Process/program name (optional)

**Security considerations:**
- Validate file paths (no path traversal)
- Handle permission denied gracefully
- Don't expose full file paths in error messages to UI
- Sanitize log content before display (no terminal escape sequences)

**Testing strategy:**
- Syslog parser: Unit tests with various log formats
- Syslog adapter: Integration tests with sample log files in tests/fixtures/
- Modal components: Textual pilot tests
- Filter parsing: Property-based tests with hypothesis
- Error handling: Tests for permission denied, file not found, malformed lines

**Exit criteria:**
- Can view entries from a syslog-format file
- Switching between mock and syslog contexts works
- Time and text filtering produce correct results
- Errors displayed gracefully without crashing

**Completed:** 2024-12 - Full implementation with 136 tests passing

---

### Phase 3: Application Logs ✅ COMPLETE
**Goal:** View any text-based log file with format auto-detection.

**Deliverables:**
- [x] Log discovery service (find readable logs in configured directories)
- [x] Generic file log adapter supporting multiple formats
- [x] Format parsers:
  - Plain text (line-based, no timestamp parsing)
  - JSON Lines (one JSON object per line)
  - Syslog (reuse existing parser for RFC 3164/5424)
- [x] Auto-detection of log format based on content sampling
- [x] Configuration for discovery paths and allowed directories
- [x] Automatic discovery on startup (configurable via discovery.paths)

**What this phase is NOT:**
- NOT automatic context creation on startup (too slow, clutters UI)
- NOT live file watching/tail -f (deferred to Phase 6)
- NOT Nginx/Apache specific parsers (deferred to Phase 7)
- NOT a replacement for syslog adapter (complements it)

**Log discovery behavior:**
- User triggers discovery via keybinding or menu
- Scans configured directories (default: /var/log) up to max depth
- Shows list of discovered files for user to select
- Selected files added as contexts to configuration
- Skips: binary files, compressed archives (.gz, .bz2, .xz), unreadable files

**Configuration:**
```json
{
  "contexts": [
    {
      "name": "my-app",
      "type": "logfile",
      "path": "/opt/myapp/logs/app.log",
      "format": "auto"
    },
    {
      "name": "api-logs",
      "type": "logfile",
      "path": "/var/log/myapi/server.log",
      "format": "jsonl"
    }
  ],
  "discovery": {
    "paths": ["/var/log", "/opt/logs"],
    "max_depth": 3,
    "allowed_directories": ["/var/log", "/opt", "/home"]
  }
}
```

**Supported log formats:**
- `auto` - Sample first 10 lines and detect format
- `plain` - Each line is a log entry, timestamp from file mtime
- `jsonl` - JSON Lines format, extracts timestamp/severity/message from JSON
- `syslog` - Delegates to existing syslog parser

**Format auto-detection logic:**
1. Try to parse first line as JSON → jsonl format
2. Try to match syslog pattern (RFC 3164/5424) → syslog format
3. Default to plain text

**JSON Lines field mapping:**
- timestamp: looks for `timestamp`, `time`, `ts`, `@timestamp`, `date`
- severity: looks for `level`, `severity`, `log_level`, `loglevel`
- message: looks for `message`, `msg`, `text`, `log`
- Remaining fields → metadata

**Security considerations:**
- Path validation against allowed_directories (reuse syslog security)
- No symlink following outside allowed paths
- Sanitize log content before display (reuse existing sanitization)

**Testing strategy:**
- Unit tests for format detection
- Unit tests for JSON Lines parser
- Integration tests with sample log files of each format
- Discovery service tests with mock filesystem

**Exit criteria:**
- Can discover log files in /var/log via UI action
- Can view plain text logs (each line = one entry)
- Can view JSON Lines formatted logs
- Format auto-detection works correctly
- All security validations in place

**Completed:** 2024-12 - Full implementation with 231 tests passing

---

### Phase 4: GCP Cloud Logging ✅ COMPLETE
**Goal:** Cloud integration with proper authentication.

**Deliverables:**
- [x] GCP adapter using google-cloud-logging library
- [x] Authentication via Application Default Credentials (ADC)
- [x] Graceful degradation when google-cloud-logging not installed
- [x] GCP-specific filters:
  - Project ID (required)
  - Log name (optional, e.g., `cloudaudit.googleapis.com%2Factivity`)
  - Resource type (optional, with common suggestions)
  - Severity (minimum level)
  - Time range
  - Text search (uses Cloud Logging filter syntax)
- [x] Batch processing for large result sets (memory-efficient)
- [x] Error handling:
  - Authentication errors (clear guidance to run `gcloud auth application-default login`)
  - Permission denied (project access)
  - Quota exceeded (rate limiting)
  - Project not found
- [x] Documentation for GCP setup and authentication
- [x] Application logging system (configurable rotating file handler)
- [x] Tree-based context switcher (configured vs discovered sources)

**What this phase is NOT:**
- NOT streaming/tail mode (deferred to Phase 6 - requires different API approach)
- NOT project discovery/listing (user must know project ID)
- NOT service account key file support (ADC only for security)

**Configuration:**
```json
{
  "contexts": [
    {
      "name": "prod-logs",
      "type": "gcp",
      "project": "my-project-id",
      "log_name": "cloudaudit.googleapis.com%2Factivity"
    },
    {
      "name": "all-gcp-logs",
      "type": "gcp",
      "project": "my-project-id"
    }
  ],
  "logging": {
    "level": "DEBUG",
    "file": "~/.config/logview/logview.log"
  }
}
```

**Common resource types (for documentation):**
- `gce_instance` - Compute Engine VMs
- `k8s_container` - GKE containers
- `cloud_function` - Cloud Functions
- `gae_app` - App Engine
- `cloud_run_revision` - Cloud Run

**Security considerations:**
- Use `gcloud auth application-default login` (no credential storage in app)
- Never log or display credentials
- Validate project IDs before API calls (alphanumeric, hyphens only)
- Handle quota errors gracefully with backoff

**Testing strategy:**
- Unit tests with mocked GCP client (no real credentials needed)
- Mock client simulates various responses (success, errors, pagination)
- Integration tests against real GCP (optional, skipped in CI by default)
- Mark integration tests with `@pytest.mark.gcp_integration`

**Exit criteria:**
- Can authenticate and fetch GCP logs with ADC
- Errors display helpful messages (not stack traces)
- Works without google-cloud-logging installed (shows "install gcp extra" message)
- All unit tests pass without GCP credentials

**Completed:** 2024-12 - Full implementation with 277 tests passing

---

### Phase 5: GKE Integration ✅ COMPLETE
**Goal:** Kubernetes-specific log viewing via Cloud Logging API.

**Key Insight:** GKE logs are stored in Cloud Logging, not the Kubernetes API. This phase
extends the GCP adapter with k8s-specific resource filters rather than direct k8s API access.

**Deliverables:**
- [x] GKE adapter using Cloud Logging API (extends GCP patterns)
- [x] k8s-specific filter building (`resource.type="k8s_container"`)
- [x] Namespace filtering via `resource.labels.namespace_name`
- [x] Pod/container filtering via `resource.labels.pod_name` and `container_name`
- [x] Label selector support via `labels.k8s-pod/<key>=<value>`
- [x] Location/zone filtering via `resource.labels.location`
- [x] Graceful degradation when google-cloud-logging not installed
- [x] Same batch processing patterns from Phase 4 (memory efficient)

**What this phase is NOT:**
- NOT streaming/tail mode (deferred to Phase 6)
- NOT cluster discovery via k8s API (user specifies cluster in config)
- NOT direct Kubernetes API access (Cloud Logging only)

**Filter fields for GKE:**
- Cluster name (required, from config)
- Namespace (optional, prefix match supported)
- Pod name (optional, prefix match supported)
- Container name (optional)
- Labels (key=value pairs)
- Location/zone (optional)
- Time range
- Severity
- Text search

**Cloud Logging filter syntax for GKE:**
```
resource.type="k8s_container"
resource.labels.project_id="my-project"
resource.labels.cluster_name="my-cluster"
resource.labels.namespace_name="default"
resource.labels.pod_name=~"api-server-.*"  -- regex for prefix
resource.labels.container_name="app"
labels."k8s-pod/app"="my-app"  -- pod labels
```

**Configuration:**
```json
{
  "contexts": [
    {
      "name": "prod-gke",
      "type": "gke",
      "project": "my-project-id",
      "cluster": "prod-cluster",
      "location": "us-central1-a",
      "default_namespace": "default"
    }
  ]
}
```

**Testing strategy:**
- Unit tests with mocked Cloud Logging client (reuse Phase 4 patterns)
- Mock responses for k8s_container resource type
- Test filter building for various k8s combinations
- Integration tests against real GKE (optional, skipped in CI)
- Mark integration tests with `@pytest.mark.gke_integration`

**Exit criteria:**
- Can fetch GKE logs using k8s resource filters
- Namespace and pod filtering produce correct results
- Label filtering works correctly
- Errors display helpful messages
- Works without google-cloud-logging installed (shows install message)

**Completed:** 2024-12 - Full implementation with 372 tests passing (58 GKE unit tests, 20 GKE integration tests)

---

### Phase 6: Enhanced UX ✅ COMPLETE
**Goal:** Polish and power-user features for daily use.

**Already Complete (from previous phases):**
- [x] Copy log entry to clipboard (DetailModal)
- [x] Color themes (light/dark via Textual, persisted to config)
- [x] Responsive layout (Textual built-in)
- [x] Mouse support (Textual built-in)

**Deliverables:**
- [x] Keyboard shortcut help modal (styled, comprehensive)
- [x] Search/filter within current results (/ key, filter matches)
- [x] Export visible logs to JSON/JSONL file
- [x] Filter presets UI (save current filter, load from list)
- [x] Settings modal with theme, timestamp format, message width, metadata toggle
- [x] Enhanced status bar (shows adapter type, active filters)
- [x] Custom theme support (12 built-in Textual themes)
- [x] Theme persistence from command palette and settings modal

**Implementation Order:**
1. **Help Modal** - Quick win, users need to discover keybindings
   - Styled modal with sections (Navigation, Actions, General)
   - Show current context and filter info
   - Dismiss with Escape or ?

2. **Search Within Results** - High value for large log sets
   - Input field appears at bottom when / pressed
   - Case-insensitive text search
   - Highlight matching entries in list
   - n/N to jump to next/previous match
   - Escape to clear search and close input

3. **Export Logs** - Share/analyze logs externally
   - `e` key opens export dialog
   - Export visible (filtered) logs to JSON or JSONL
   - Default filename with timestamp
   - Notify on success with path

4. **Filter Presets** - Power user efficiency
   - Save current filter as named preset
   - Load preset from list (integrate with filter modal)
   - Delete unused presets
   - Stored in config file (schema already exists)

5. **Status Bar** - Better awareness of current state
   - Show: context name, entry count, active filter summary
   - Indicate when filter is active vs showing all

**What this phase is NOT:**
- NOT live file watching/tail -f (deferred - requires different architecture)
- NOT syntax highlighting in log content (low value, high complexity)
- NOT custom keybinding configuration (deferred)

**Testing strategy:**
- Unit tests for export formatting
- UI tests with Textual pilot for modals and search
- Integration tests for preset save/load

**Exit criteria:**
- Help modal shows all keybindings with clear sections
- Search highlights and navigates within visible logs
- Export produces valid JSON/JSONL files
- Presets save to and load from config file
- Status bar shows context, count, and filter state

**Completed:** 2024-12 - Full implementation with 396 tests passing

---

### Phase 7: Context Detection
**Goal:** Automatic discovery of GCP projects and GKE clusters using Application Default Credentials.

**Deliverables:**
- [ ] Context detector module using GCP resource management APIs
- [ ] Project discovery via google-cloud-resourcemanager
- [ ] GKE cluster discovery via google-cloud-container
- [ ] Configuration options for auto-discovery behavior
- [ ] UI modal for reviewing and selecting discovered contexts
- [ ] Keyboard shortcut for manual discovery trigger
- [ ] Optional auto-discovery on application startup
- [ ] Intelligent merging (don't duplicate existing contexts)
- [ ] Progress indicators during discovery
- [ ] Comprehensive error handling and user guidance

**What this phase IS:**
- Automatic discovery of accessible GCP projects
- Automatic discovery of GKE clusters in each project
- User review and selection before adding contexts
- Respects existing manually-configured contexts
- Uses same ADC authentication as adapters

**What this phase is NOT:**
- NOT automatic context switching
- NOT continuous monitoring for new resources
- NOT namespace discovery within clusters (too granular)
- NOT modification of existing contexts (only adds new ones)
- NOT a replacement for manual configuration

**Discovery Workflow:**
1. User triggers discovery (keyboard shortcut `d` or auto on startup)
2. App shows "Discovering contexts..." progress indicator
3. List all accessible GCP projects using resourcemanager API
4. For each project, list GKE clusters using container API
5. Show modal with discovered contexts (project + cluster combinations)
6. User selects which contexts to add (checkboxes)
7. Selected contexts merged into config file
8. App switches to first newly-added context

**Configuration:**
```json
{
  "context_detection": {
    "enabled": true,
    "auto_on_startup": false,
    "project_filter": ["prod-*", "staging-*"],
    "skip_projects": ["test-*", "temp-*"],
    "include_gcp_contexts": true,
    "include_gke_contexts": true,
    "cache_ttl_seconds": 300
  }
}
```

**Configuration Options:**
- `enabled`: Master switch for context detection feature (default: true)
- `auto_on_startup`: Run discovery automatically when app starts (default: false)
- `project_filter`: Optional list of fnmatch-style patterns for project IDs to include (e.g., ["prod-*", "staging-*"])
- `skip_projects`: Optional list of fnmatch-style patterns for project IDs to exclude (e.g., ["test-*", "temp-*"])
- `include_gcp_contexts`: Create GCP contexts for each project (default: true)
- `include_gke_contexts`: Create GKE contexts for each cluster (default: true)
- `cache_ttl_seconds`: Cache discovered contexts for this many seconds to avoid repeated API calls (default: 300)

**Context Naming Convention:**
- GCP: `[detected] PROJECT_ID` (e.g., "[detected] my-prod-project")
- GKE: `[detected] CLUSTER_NAME (PROJECT_ID)` (e.g., "[detected] prod-cluster (my-project)")
- Prefix allows user to distinguish auto-detected from manual contexts
- Can be renamed by user after detection via config file edit

**Detected Context Details:**
- GKE contexts include cluster location (zone/region) automatically
- GCP contexts include no specific log_name or resource_type (show all logs)
- All contexts use the same ADC authentication as manual contexts
- Contexts can be customized after detection (add log_name, default_namespace, etc.)

**Required Dependencies:**
```python
google-cloud-resourcemanager>=1.12.0  # List projects
google-cloud-container>=2.42.0        # List GKE clusters
```

**API Usage:**
```python
# List projects
from google.cloud import resourcemanager_v3
projects_client = resourcemanager_v3.ProjectsClient()
projects = projects_client.search_projects()

# List clusters per project
from google.cloud import container_v1
clusters_client = container_v1.ClusterManagerClient()
clusters = clusters_client.list_clusters(parent=f"projects/{project_id}/locations/-")
```

**Discovery Modal UI:**
```
┌─ Discovered Contexts ─────────────────────────────┐
│                                                   │
│  Found 3 projects and 5 clusters:                │
│                                                   │
│  ☑ [GCP] my-prod-project                          │
│  ☑ [GKE] prod-cluster (my-prod-project)           │
│  ☑ [GKE] staging-cluster (my-prod-project)        │
│  ☐ [GCP] my-test-project                          │
│  ☐ [GKE] test-cluster (my-test-project)           │
│  ☑ [GCP] my-dev-project                           │
│  ☑ [GKE] dev-cluster-1 (my-dev-project)           │
│  ☑ [GKE] dev-cluster-2 (my-dev-project)           │
│                                                   │
│  [a] Select All  [n] Select None                  │
│  [Enter] Add Selected  [Esc] Cancel               │
└───────────────────────────────────────────────────┘
```

**Security Considerations:**
- Use ADC only (no credential storage)
- Validate all project IDs and cluster names before API calls
- Handle quota limits gracefully (discovery can be API-heavy)
- Log discovery activity for troubleshooting
- Never log credentials or sensitive resource details
- Rate limiting to avoid quota exhaustion

**Error Handling:**
- **Libraries not installed**: Show message with install command
- **Authentication failure**: Guide user to run `gcloud auth application-default login`
- **Permission denied**: Skip inaccessible projects, continue with others
- **API quota exceeded**: Show warning, offer to retry later
- **Network errors**: Retry with exponential backoff, inform user
- **Empty results**: Show "No accessible projects found" message

**Performance Considerations:**
- Discovery runs asynchronously (doesn't block UI)
- Project listing is usually fast (< 1s)
- Cluster listing can be slow for many projects (1-2s per project)
- Show progress: "Discovering... (2/5 projects checked)"
- Cache results for 5 minutes to avoid repeated API calls
- Timeout after 30s with partial results

**Merge Strategy:**
- Compare by context type + key identifiers:
  - GCP: type="gcp" + project
  - GKE: type="gke" + project + cluster
- Skip contexts that already exist (exact match)
- Detect similar contexts (same project/cluster, different name)
- Offer to update similar contexts vs. create new ones
- Preserve user customizations (log_name, default_namespace, etc.)

**Implementation Approach:**

**Step 1: Core detector module**
- Create `src/logview/adapters/context_detector.py`
- Implement `ContextDetector` class with project/cluster discovery
- Graceful degradation when libraries not installed
- Comprehensive error handling and logging

**Step 2: Configuration schema**
- Add `ContextDetectionSettings` to `src/logview/config/schema.py`
- Update `Config` model to include `context_detection` field
- Update example configuration file

**Step 3: Discovery logic**
- Implement project listing using resourcemanager_v3
- Implement cluster listing using container_v1
- Apply filtering (project_filter, skip_projects)
- Generate context configs from discovered resources
- Implement caching mechanism (in-memory, TTL-based)

**Step 4: Merge logic**
- Implement context comparison/deduplication
- Detect exact matches (skip)
- Detect similar contexts (same identifiers, different names)
- Preserve existing context customizations

**Step 5: UI modal**
- Create `src/logview/ui/screens/discovery.py`
- Show discovered contexts with checkboxes
- Implement select all/none functionality
- Show counts and status during discovery
- Handle empty results gracefully

**Step 6: App integration**
- Add keyboard binding `d` for discovery in main app
- Wire up optional auto-discovery on startup
- Save selected contexts to config file
- Switch to first newly-added context after save

**Step 7: Testing**
- Unit tests for detector with mocked clients
- Unit tests for filtering and merge logic
- UI tests for discovery modal
- Integration tests (optional, marked for skip in CI)

**Testing Strategy:**
- Unit tests with mocked GCP clients (no real credentials)
- Mock projects and clusters responses
- Test filtering logic (project_filter, skip_projects)
- Test merge logic (no duplicates)
- Integration tests against real GCP (optional, skipped in CI)
- Mark integration tests with `@pytest.mark.context_detection_integration`
- UI tests with Textual pilot for discovery modal

**Exit Criteria:**
- Can discover projects using ADC
- Can discover GKE clusters in each project
- Discovery modal shows results with selection UI
- Selected contexts are added to config without duplicates
- Works without libraries installed (shows install message)
- All unit tests pass without GCP credentials
- Error messages are actionable and helpful
- Discovery completes in reasonable time (< 30s for 10 projects)

---

### Phase 8: Productionization
**Goal:** Make LogView easy to install and distribute with professional packaging.

**Deliverables:**
- [ ] Wheel packaging configuration
  - Entry point for `logview` command
  - Package metadata (description, license, classifiers)
  - Include package data files
- [ ] curl-able install.sh script
  - Platform detection (Linux, macOS)
  - Python version check (3.11+)
  - pipx installation (isolated environment)
  - Fallback to pip if pipx unavailable
  - Config directory creation (~/.config/logview/)
  - Optional PATH modification
  - Verification step
- [ ] Installation documentation
  - Quick install (one-liner curl | bash)
  - Alternative methods (pip, pipx, from source)
  - System requirements
  - Troubleshooting guide
- [ ] Distribution preparation
  - Build script for wheel generation
  - Version management automation
  - Checksum generation for releases
- [ ] Uninstall documentation
  - Clean removal instructions
  - Config file cleanup guidance

**Installation Methods:**

**Method 1: Quick Install (Recommended)**
```bash
curl -fsSL https://raw.githubusercontent.com/agileguy/logview/main/install.sh | bash
```

**Method 2: pipx (Isolated)**
```bash
pipx install logview
```

**Method 3: pip (Global/Virtual Environment)**
```bash
pip install logview
# With GCP/GKE support
pip install logview[all]
```

**Method 4: From Source**
```bash
git clone https://github.com/agileguy/logview.git
cd logview
pip install -e ".[dev]"
```

**install.sh Script Features:**
- Detects OS and architecture
- Checks Python 3.11+ availability
- Prefers pipx for isolated installation
- Creates config directory structure
- Provides clear success/error messages
- Idempotent (safe to run multiple times)
- Supports flags:
  - `--with-gcp`: Install with GCP/GKE extras
  - `--method pip|pipx`: Force installation method
  - `--uninstall`: Remove LogView

**Wheel Package Configuration:**
- Proper entry points in pyproject.toml
- Package data inclusion (themes, example configs)
- Correct metadata (homepage, repository, documentation)
- License and classifiers for PyPI
- Minimal but complete dependencies

**Testing Strategy:**
- Test install.sh on Ubuntu, Debian, Fedora, macOS
- Verify wheel builds correctly
- Test installation in fresh virtualenv
- Verify entry point works after install
- Test uninstall leaves system clean

**Exit Criteria:**
- One-liner curl install works on Linux and macOS
- Wheel builds without errors
- `logview` command available after install
- Installation creates config directory
- Documentation covers all install methods
- Uninstall removes all traces

---

### Phase 9: Additional Sources (Future)
**Goal:** Extensibility proven with more sources.

**Potential adapters:**
- [ ] AWS CloudWatch Logs
- [ ] Azure Monitor Logs
- [ ] Elasticsearch
- [ ] Loki (Grafana)
- [ ] Local file (arbitrary log file)
- [ ] Docker container logs
- [ ] SSH remote syslog

Each adapter follows established patterns from Phases 2-5.

---

## UI Mockups

### Main View (List)
```
┌─ LogView ─────────────────────────────────────────────────────┐
│ Context: [GKE: prod-cluster/default]     [?] Help  [q] Quit   │
├───────────────────────────────────────────────────────────────┤
│ 2024-01-15 10:23:45 INFO  api-server-abc12  Request completed  │
│ 2024-01-15 10:23:44 WARN  api-server-abc12  High latency: 2.3s │
│ 2024-01-15 10:23:42 INFO  worker-def34      Job started: #1234 │
│ 2024-01-15 10:23:41 ERROR db-proxy-ghi56    Connection refused │
│ 2024-01-15 10:23:40 INFO  api-server-abc12  Health check OK    │
│ > 2024-01-15 10:23:39 DEBUG worker-def34    Processing item 42 │ ← selected
│ 2024-01-15 10:23:38 INFO  api-server-abc12  Request started    │
│ ...                                                            │
├───────────────────────────────────────────────────────────────┤
│ [c] Context  [f] Filter  [Enter] Detail  [/] Search           │
└───────────────────────────────────────────────────────────────┘
```

### Context Selector Modal
```
┌─ Select Context ──────────────────────┐
│                                       │
│   ○ Syslog (local)                    │
│   ● GKE: prod-cluster                 │  ← selected
│   ○ GKE: staging-cluster              │
│   ○ GCP: my-project                   │
│   ○ Mock (testing)                    │
│                                       │
│   [Enter] Select   [Esc] Cancel       │
└───────────────────────────────────────┘
```

### Filter Editor Modal
```
┌─ Filter Logs ─────────────────────────────────────────┐
│                                                       │
│  Time Range:                                          │
│    Start: [2024-01-15 10:00:00    ]                   │
│    End:   [2024-01-15 11:00:00    ]                   │
│    Quick: [Last 1h ▼]                                 │
│                                                       │
│  Namespace:   [default             ]                  │
│  Pod:         [api-server-*        ]                  │
│  Severity:    [WARN ▼] and above                      │
│  Text search: [connection          ]                  │
│                                                       │
│   [Enter] Apply   [Esc] Cancel   [Tab] Next field    │
└───────────────────────────────────────────────────────┘
```

### Log Detail Modal
```
┌─ Log Detail ──────────────────────────────────────────────────┐
│                                                               │
│  Timestamp:  2024-01-15 10:23:41.234 UTC                      │
│  Severity:   ERROR                                            │
│  Source:     db-proxy-ghi56                                   │
│                                                               │
│  Message:                                                     │
│  Connection refused to postgres-primary:5432                  │
│                                                               │
│  Metadata:                                                    │
│  {                                                            │
│    "cluster": "prod-cluster",                                 │
│    "namespace": "default",                                    │
│    "pod": "db-proxy-ghi56-abc123",                            │
│    "container": "proxy",                                      │
│    "attempt": 3,                                              │
│    "error_code": "ECONNREFUSED"                               │
│  }                                                            │
│                                                               │
│   [c] Copy JSON   [Esc] Close   [↑↓] Scroll                   │
└───────────────────────────────────────────────────────────────┘
```

---

## Configuration File Format

```json
{
  "$schema": "https://logview.dev/schema/config.json",
  "contexts": [
    {
      "name": "prod-gke",
      "type": "gke",
      "project": "my-gcp-project",
      "cluster": "prod-cluster",
      "default_namespace": "default"
    },
    {
      "name": "staging-gke",
      "type": "gke",
      "project": "my-gcp-project",
      "cluster": "staging-cluster"
    },
    {
      "name": "gcp-audit",
      "type": "gcp",
      "project": "my-gcp-project",
      "log_name": "cloudaudit.googleapis.com%2Factivity"
    },
    {
      "name": "local",
      "type": "syslog",
      "path": "/var/log/syslog"
    }
  ],
  "presets": [
    {
      "name": "errors-last-hour",
      "severity": "ERROR",
      "time_range_minutes": 60
    },
    {
      "name": "api-debug",
      "pod": "api-*",
      "severity": "DEBUG",
      "namespace": "default"
    }
  ],
  "ui": {
    "theme": "dark",
    "timestamp_format": "%Y-%m-%d %H:%M:%S",
    "max_message_width": 80,
    "show_metadata": false
  },
  "security": {
    "credential_helper": "gcloud"
  }
}
```

### Pydantic Config Schema

```python
from pydantic import BaseModel, Field
from typing import Literal


class GKEContext(BaseModel):
    name: str
    type: Literal["gke"]
    project: str
    cluster: str
    default_namespace: str | None = None


class GCPContext(BaseModel):
    name: str
    type: Literal["gcp"]
    project: str
    log_name: str | None = None


class SyslogContext(BaseModel):
    name: str
    type: Literal["syslog"]
    path: str = "/var/log/syslog"


class LogFileContext(BaseModel):
    name: str
    type: Literal["logfile"]
    path: str
    format: Literal["auto", "plain", "syslog", "jsonl"] = "auto"


class DiscoverySettings(BaseModel):
    paths: list[str] = Field(default_factory=lambda: ["/var/log"])
    max_depth: int = 3
    allowed_directories: list[str] = Field(default_factory=lambda: ["/var/log", "/opt", "/home"])


Context = GKEContext | GCPContext | SyslogContext | LogFileContext


class FilterPreset(BaseModel):
    name: str
    severity: str | None = None
    time_range_minutes: int | None = None
    namespace: str | None = None
    pod: str | None = None
    text_search: str | None = None


class UISettings(BaseModel):
    theme: str = "dark"  # Any Textual theme: dark, light, ansi, catppuccin-mocha, etc.
    timestamp_format: str = "%Y-%m-%d %H:%M:%S"
    max_message_width: int = 80
    show_metadata: bool = False


class SecuritySettings(BaseModel):
    credential_helper: Literal["gcloud", "env", "keyring"] = "gcloud"


class Config(BaseModel):
    contexts: list[Context] = Field(default_factory=list)
    presets: list[FilterPreset] = Field(default_factory=list)
    ui: UISettings = Field(default_factory=UISettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    discovery: DiscoverySettings = Field(default_factory=DiscoverySettings)
```

---

## Testing Strategy Details

### Unit Tests
- All domain types have comprehensive pytest tests
- Parametrized tests for filter parsing
- Adapters tested against Protocol

```python
# tests/unit/test_filter.py
import pytest
from hypothesis import given, strategies as st
from logview.domain.filter import parse_time_range

@pytest.mark.parametrize("input,expected", [
    ("1h", timedelta(hours=1)),
    ("30m", timedelta(minutes=30)),
    ("7d", timedelta(days=7)),
])
def test_parse_time_range(input, expected):
    assert parse_time_range(input) == expected

@given(st.integers(min_value=1, max_value=1000))
def test_time_range_always_positive(minutes):
    result = parse_time_range(f"{minutes}m")
    assert result.total_seconds() > 0
```

### Integration Tests
- Syslog: Read from fixture files
- GCP/GKE: Mock client or skip in CI
- UI: Textual pilot framework

```python
# tests/ui/test_app.py
import pytest
from textual.pilot import Pilot
from logview.app import LogViewApp

@pytest.mark.asyncio
async def test_app_starts():
    app = LogViewApp()
    async with app.run_test() as pilot:
        assert app.query_one("#log-list") is not None

@pytest.mark.asyncio
async def test_context_modal_opens():
    app = LogViewApp()
    async with app.run_test() as pilot:
        await pilot.press("c")
        assert app.query_one("#context-modal") is not None
```

### Property-Based Tests
- Filter construction never produces invalid queries
- Time range parsing handles edge cases
- JSON serialization round-trips correctly

### Security Tests
- No credentials in debug output
- Input sanitization prevents injection
- Rate limiting protects against accidental spam

### Manual Testing Checklist
- [ ] Terminal resize doesn't crash
- [ ] Large log volumes scroll smoothly
- [ ] Network failures show clear errors
- [ ] Authentication failures guide user

---

## Security Checklist

### Credential Handling
- [ ] Never prompt for or store raw credentials
- [ ] Use ADC for GCP (`gcloud auth application-default login`)
- [ ] Use kubeconfig for GKE
- [ ] Document authentication setup in README

### Input Validation
- [ ] Time range inputs parsed with strict format
- [ ] Text search escaped before API calls
- [ ] Project/cluster names validated against pattern
- [ ] No shell interpolation in any adapter

### Output Safety
- [ ] Application logs don't include credentials
- [ ] Error messages don't expose internal paths
- [ ] Debug mode explicitly disabled by default
- [ ] Clipboard operations don't include secrets

### Dependency Security
- [ ] Use `pip-audit` for vulnerability scanning
- [ ] Dependabot enabled
- [ ] Minimal dependency footprint
- [ ] Pin exact versions in pyproject.toml

---

## Success Metrics

### Phase 1
- 100% of domain types have tests
- TUI boots in < 500ms
- Mock adapter produces data in < 100ms
- Type checking passes with strict mode

### Phase 2
- Syslog queries return in < 1s for 10k lines
- Filter changes feel instant (< 200ms)
- Memory usage < 100MB for 50k log lines

### Phase 3
- Log discovery completes in < 3s for /var/log
- Format detection accuracy > 95% for plain/jsonl/syslog
- JSON Lines parsing handles 10k entries in < 1s

### Phase 4
- GCP authentication succeeds on first try (with ADC)
- Streaming updates appear within 2s
- Error messages are actionable

### Phase 5
- Pod logs stream in real-time
- Cluster switching takes < 3s
- Namespace list loads in < 1s

### Phase 6
- All operations have keyboard shortcuts
- Help is discoverable
- Theme switch is instant

---

## Open Questions

1. **Streaming architecture**: Should streaming be push (adapter sends) or pull (UI polls)?
   - *Recommendation*: Push via async generators, UI consumes

2. **Log retention**: Should we cache fetched logs locally?
   - *Recommendation*: In-memory only, configurable limit

3. **Multiple panes**: Should advanced users get split views?
   - *Recommendation*: Defer to Phase 6, keep single-pane for simplicity

4. **Plugin system**: Should adapters be dynamically loadable?
   - *Recommendation*: No, import-time only for security

---

## Getting Started

Project structure is complete. To set up development environment:

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Type check
mypy src/

# Lint
ruff check src/ tests/

# Run the application
python -m logview
```

## Changelog

### 2025-12 - Phase 6 Complete
- Help modal with keyboard shortcuts reference
- Search within results (/ key, n/N navigation)
- Export logs to JSON/JSONL files
- Filter presets (save, load, delete)
- Settings modal with theme, timestamp format, message width, metadata toggle
- Enhanced status bar showing adapter type and active filters
- Custom theme support (12 built-in Textual themes)
- Theme persistence from command palette and settings modal
- Fixed InvalidThemeError with proper prefix handling for custom themes
- 417 tests passing, 38 skipped (GCP/GKE integration)

### 2024-12 - Phase 5 Complete
- GKE adapter using Cloud Logging API
- Kubernetes-specific filters (namespace, pod, container, labels)
- Wildcard support for namespace and pod filters
- Location/zone filtering
- Batch processing for memory efficiency
- 372 tests passing, 58 GKE unit tests, 20 GKE integration tests

### 2024-12 - Phase 4 Complete
- GCP Cloud Logging adapter with ADC authentication
- Graceful degradation when google-cloud-logging not installed
- Comprehensive error handling with actionable messages
- Application logging system with rotating file handler
- Tree-based context switcher (configured vs discovered sources)
- Memory-optimized batch processing in fetch methods
- 277 tests passing, 17 skipped (GCP integration)

### 2024-12 - Phase 3 Complete
- Log discovery service for finding readable log files
- LogFileSource adapter with format auto-detection
- JSON Lines parser with flexible field extraction
- Plain text parser with severity detection
- Automatic discovery on startup (opt-in via config)
- Comprehensive security: path validation, symlink checks, TOCTOU prevention
- 231 tests passing

### 2024-12 - Phase 2 Complete
- Syslog adapter with RFC 3164 and RFC 5424 support
- Filter modal (time range, severity, text search)
- Detail modal (scrollable, copy to clipboard)
- Context selector modal (switch between sources)
- Theme persistence to config file
- Configuration loading on startup
- 136 tests passing

### 2024-12 - Phase 1 Complete
- Initial project structure created
- All domain models implemented (LogEntry, Filter, Severity, TimeRange)
- LogSource protocol defined with mock adapter
- Basic Textual app with log list widget
- JSON configuration schema with Pydantic
- Comprehensive test suite (unit, integration, UI)
- Project documentation (README.md, CLAUDE.md, PLAN.md)
