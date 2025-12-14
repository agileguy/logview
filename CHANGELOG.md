# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/agileguy/logview/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/agileguy/logview/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/agileguy/logview/releases/tag/v0.1.0
