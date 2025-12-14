# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.0] - 2025-12-14

### Added
- **Help Modal**: Styled keyboard shortcuts reference (`?` key)
  - Three sections: Navigation, Actions, General
  - Scrollable content, close with Escape or Close button
- **Search Within Results**: Filter already-loaded entries (`/` key)
  - Case-insensitive text search
  - Real-time filtering as you type
  - Match count display (e.g., "3/10 matches")
  - Navigate matches with `n` (next) and `N` (previous)
- **Export Logs**: Save visible entries to file (`e` key)
  - JSON (pretty-printed) or JSONL format
  - Default filename with timestamp
  - Exports filtered entries if search is active
- **Filter Presets**: Save and load filter configurations
  - Save current filter settings as named preset
  - Load preset from dropdown in filter modal
  - Delete unused presets
  - Presets persist in config.json

## [0.4.0] - 2025-12-14

### Added
- **GKE (Google Kubernetes Engine) Adapter**: Query GKE logs via Cloud Logging API
  - Uses k8s_container resource type for Kubernetes-specific queries
  - Filter by namespace, pod name, container name (with wildcard support)
  - Label selector support (`app=nginx,env=prod`)
  - Location/zone filtering
  - Reuses GCP adapter's batch processing for memory efficiency
  - Cluster and namespace name validation
  - Graceful degradation when google-cloud-logging not installed
- **GCP Cloud Logging Adapter**: Query logs from Google Cloud Logging
  - Application Default Credentials (ADC) authentication
  - Graceful degradation when google-cloud-logging not installed
  - Filter by project, log name, resource type, severity, time range, text search
  - Comprehensive error handling (auth, permission, quota, project not found)
  - Project ID format validation
  - Protocol-based design for easy testing
- **Application Logging**: Configurable logging for debugging
  - Log level configuration (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  - Rotating file handler with configurable size and backup count
  - Default log location: `~/.config/logview/logview.log`
  - Logging throughout all adapters (GCP, GKE, syslog, logfile, discovery)
- **Tree-Based Context Switcher**: Redesigned source selection
  - Configured sources (syslog, GCP, GKE) displayed at root level
  - Discovered sources in collapsible "Discovered Logs" folder
  - Active source highlighted with "●" marker
- Integration tests for GCP and GKE adapters (skipped in CI)

### Security
- **GKE Wildcard Validation**: Strict validation for wildcard patterns
  - Only trailing wildcards allowed (`kube-*` ✓, `*-system` ✗, `kube-*-system` ✗)
  - Wildcard-only patterns rejected (`*` ✗)
  - Invalid patterns raise `GKEInvalidFilterError` with clear error messages
  - `validate_filter` now validates wildcards before `fetch` (fail-fast)
- **Quote Escaping**: All filter values properly escaped for Cloud Logging syntax
  - Namespace, pod, container, labels, and text search values escaped
  - Prevents filter syntax errors from special characters

### Changed
- **Performance**: Memory-optimized fetch operations
  - GCP adapter: Batch processing (100 entries at a time) instead of loading all at once
  - LogFile adapter: Heap-based top-N selection instead of full sort

### Fixed
- GCP adapter now uses `resource_names` parameter (API compatibility with google-cloud-logging 3.x)
- GCP adapter handles unified `payload` property for message extraction
- GCP JSON payloads now display correctly (supports `message`, `msg`, `textPayload` fields)
- Context modal cursor positioning with `move_cursor` instead of `select_node`

## [0.3.0] - 2024-12-14

### Added
- **Log Discovery Service**: Automatically find readable log files in configured directories
- **LogFile Adapter**: Generic log file adapter with format auto-detection
- **JSON Lines Parser**: Parse JSONL format with flexible field extraction (timestamp, severity, message)
- **Plain Text Parser**: Parse plain text logs with severity detection from content
- **Automatic Discovery**: Opt-in startup discovery via `discovery.paths` config
- **RFC 5424 Support**: Syslog parser now supports ISO 8601 timestamps with timezone

### Fixed
- JSONL timestamp edge cases and overflow errors (boundary values, invalid timestamps)
- Syslog allowlist now respects configured `allowed_directories`
- Tilde expansion in syslog allowlist paths
- JSONL raw field preserves original whitespace
- Duplicate source contexts warn user instead of silently dropping
- Async discovery scheduling errors handled gracefully
- Symlink TOCTOU vulnerability in discovery and LogFile adapter
- Path leakage in error messages prevented
- Empty allowlist correctly disables file access (no silent fallback)

### Security
- Path validation against configurable allowed_directories
- Symlink escape prevention (resolved paths checked against allowlist)
- TOCTOU attack prevention (re-validate paths on fetch)
- No sensitive paths exposed in error messages

## [0.2.0] - 2024-12-13

### Added
- **Syslog Adapter**: File-based syslog parsing with RFC 3164 support
  - Path validation with allowed directory whitelist (security)
  - ANSI escape sequence sanitization (security)
  - Graceful handling of malformed lines
  - Hostname, program, PID extraction to metadata
- **Detail Modal**: Full log entry view with copy to clipboard
- **Context Modal**: Switch between log sources with keyboard navigation
- **Filter Modal**: Configure time range, severity, text search, result limit
- **Theme Persistence**: Save theme preference when toggled via command palette
- **Config Loading**: Load contexts and UI settings from config file on startup

### Fixed
- Symlink path resolution in allowed directories check (macOS compatibility)
- Subprocess zombie prevention in clipboard fallback

### Security
- Path traversal prevention in syslog adapter
- No full paths exposed in error messages
- Terminal escape sequence sanitization

## [0.1.0] - 2024-12-13

### Added
- Initial project structure with Textual framework
- Mock log source adapter for testing
- Core domain models (LogEntry, Filter, Severity, TimeRange)
- Basic TUI with log list, header, footer
- Configuration schema with Pydantic
- GitHub Actions CI pipeline
- Comprehensive test suite (pytest, mypy, ruff)

[Unreleased]: https://github.com/agileguy/logview/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/agileguy/logview/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/agileguy/logview/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/agileguy/logview/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/agileguy/logview/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/agileguy/logview/releases/tag/v0.1.0
