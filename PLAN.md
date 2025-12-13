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
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────┐ │
│  │     GCP     │ │     GKE     │ │   Syslog    │ │ Mock  │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────┘ │
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

### Phase 1: Foundation (MVP)
**Goal:** Runnable TUI with mock data, establishing patterns for all future work.

**Deliverables:**
- [ ] Project scaffolding (pyproject.toml, src layout)
- [ ] Core domain models with Pydantic (LogEntry, Filter, Severity)
- [ ] LogSource protocol definition
- [ ] Mock adapter generating fake log data
- [ ] Basic Textual app shell
- [ ] Main list view displaying mock logs
- [ ] Scrolling and basic navigation
- [ ] Unit tests for domain types
- [ ] Integration test for mock adapter

**Testing strategy:**
- Domain types: pytest with parametrized tests
- Mock adapter: Verify it implements protocol correctly
- UI: Textual's pilot testing framework

**Exit criteria:**
- `pytest` passes with >70% coverage on domain
- Running `python -m logview` displays scrollable fake logs
- Type checking passes (`mypy src/`)

---

### Phase 2: Local Log Source (Syslog)
**Goal:** First real log source, proving the adapter pattern works.

**Deliverables:**
- [ ] Syslog adapter (reads from /var/log/syslog or journalctl)
- [ ] Time range filtering
- [ ] Text search filtering (grep-like)
- [ ] Log detail modal (show full log entry as formatted JSON)
- [ ] Context selector modal (switch between mock/syslog)
- [ ] Error handling and display
- [ ] JSON configuration file support

**Filter fields for syslog:**
- Time range (start, end)
- Severity (minimum level)
- Text search
- Process name (optional)

**Testing strategy:**
- Syslog adapter: Integration tests with sample log files
- Modal components: Textual pilot tests
- Filter parsing: Property-based tests with hypothesis

**Exit criteria:**
- Can view real syslog entries
- Switching contexts works
- Time filtering produces correct results

---

### Phase 3: GCP Cloud Logging
**Goal:** Cloud integration with proper authentication.

**Deliverables:**
- [ ] GCP adapter using google-cloud-logging
- [ ] Authentication via Application Default Credentials
- [ ] Project selector (if multiple projects)
- [ ] GCP-specific filters:
  - Project ID
  - Log name
  - Resource type
  - Severity
- [ ] Streaming mode (tail -f equivalent)
- [ ] Rate limiting / pagination handling
- [ ] Secure credential handling documentation

**Security considerations:**
- Use `gcloud auth application-default login` (no credential storage)
- Validate project IDs before API calls
- Handle quota errors gracefully

**Testing strategy:**
- Unit tests with mocked GCP client
- Integration tests against real GCP (optional, CI skippable)
- Security review checklist

**Exit criteria:**
- Can authenticate and fetch GCP logs
- Streaming updates work
- No credentials in application logs

---

### Phase 4: GKE Integration
**Goal:** Kubernetes-specific log viewing with cluster awareness.

**Deliverables:**
- [ ] GKE adapter (extends GCP with k8s context)
- [ ] Cluster selector
- [ ] Namespace filtering
- [ ] Pod/container filtering
- [ ] Label selector support
- [ ] Follow pod logs (streaming)
- [ ] kubeconfig integration for authentication

**Filter fields for GKE:**
- Cluster name
- Namespace
- Pod name (prefix match)
- Container name
- Labels (key=value)
- Time range
- Severity

**Testing strategy:**
- Mock Kubernetes client for unit tests
- Integration tests against kind/minikube (CI optional)

**Exit criteria:**
- Can browse logs by cluster → namespace → pod
- Label filtering works correctly
- Following works for running pods

---

### Phase 5: Enhanced UX
**Goal:** Polish and power-user features.

**Deliverables:**
- [ ] Filter presets (save/load common filters)
- [ ] Search within current results (/ key)
- [ ] Copy log entry to clipboard
- [ ] Export visible logs to JSON file
- [ ] Keyboard shortcut help modal
- [ ] Color themes (light/dark via Textual CSS)
- [ ] Responsive layout (terminal resize handling)
- [ ] Mouse support (optional scrolling, clicking)

**Testing strategy:**
- End-to-end tests with Textual pilot
- Manual testing checklist for UX

**Exit criteria:**
- All keybindings documented and working
- Resize handling works without crashes
- Theme switching works

---

### Phase 6: Additional Sources (Future)
**Goal:** Extensibility proven with more sources.

**Potential adapters:**
- [ ] AWS CloudWatch Logs
- [ ] Azure Monitor Logs
- [ ] Elasticsearch
- [ ] Loki (Grafana)
- [ ] Local file (arbitrary log file)
- [ ] Docker container logs
- [ ] SSH remote syslog

Each adapter follows established patterns from Phases 2-4.

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


Context = GKEContext | GCPContext | SyslogContext


class FilterPreset(BaseModel):
    name: str
    severity: str | None = None
    time_range_minutes: int | None = None
    namespace: str | None = None
    pod: str | None = None
    text_search: str | None = None


class UISettings(BaseModel):
    theme: Literal["dark", "light"] = "dark"
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
- GCP authentication succeeds on first try (with ADC)
- Streaming updates appear within 2s
- Error messages are actionable

### Phase 4
- Pod logs stream in real-time
- Cluster switching takes < 3s
- Namespace list loads in < 1s

### Phase 5
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

After approval, Phase 1 begins with:

```bash
# Create project with uv (recommended) or pip
uv init logview
cd logview

# Add dependencies
uv add textual pydantic
uv add --dev pytest pytest-asyncio hypothesis mypy ruff

# Create directory structure
mkdir -p src/logview/{adapters,domain,ui/{widgets,screens,styles},config}
mkdir -p tests/{unit,integration,ui}

# Initialize packages
touch src/logview/__init__.py
touch src/logview/__main__.py

# Start with domain models
touch src/logview/domain/models.py
```

First PR: Domain models + Mock adapter + Basic list view
