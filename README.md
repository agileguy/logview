# LogView

[![CI](https://github.com/agileguy/logview/actions/workflows/ci.yml/badge.svg)](https://github.com/agileguy/logview/actions/workflows/ci.yml)

A testable, responsive log viewer TUI with pluggable log source contexts.

## Features

- **Multiple log sources**: Local log files, syslog, GCP Cloud Logging, GKE, and more
- **Format auto-detection**: Automatically detects plain text, JSON Lines, and syslog formats
- **Log discovery**: Scan directories to find log files
- **Flexible filtering**: Time range, severity, text search, and source-specific fields
- **Keyboard-first**: Full functionality without mouse
- **Testable**: Interface-driven design with comprehensive test coverage

## Installation

```bash
# Using uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .

# With optional GCP/GKE support
pip install -e ".[all]"

# Development dependencies
pip install -e ".[dev]"
```

## Usage

```bash
# Run the TUI
logview

# Or as a module
python -m logview
```

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `↑/↓` | Navigate log entries |
| `Enter` | View log details |
| `c` | Change context |
| `f` | Open filter |
| `/` | Search |
| `?` | Help |
| `q` | Quit |

## Configuration

Create `~/.config/logview/config.json`:

```json
{
  "contexts": [
    {
      "name": "app-logs",
      "type": "logfile",
      "path": "/var/log/myapp/app.log",
      "format": "auto"
    },
    {
      "name": "local-syslog",
      "type": "syslog",
      "path": "/var/log/syslog"
    },
    {
      "name": "gcp-logs",
      "type": "gcp",
      "project": "my-project",
      "log_name": "cloudaudit.googleapis.com%2Factivity"
    },
    {
      "name": "prod-gke",
      "type": "gke",
      "project": "my-project",
      "cluster": "prod-cluster"
    }
  ],
  "ui": {
    "theme": "dark"
  }
}
```

See `configs/example.json` for a complete example.

### GCP Cloud Logging Setup

To use GCP Cloud Logging as a log source:

1. **Install with GCP support**:
   ```bash
   pip install -e ".[gcp]"
   ```

2. **Authenticate with GCP**:
   ```bash
   gcloud auth application-default login
   ```

3. **Add a GCP context to your config**:
   ```json
   {
     "name": "my-gcp-project",
     "type": "gcp",
     "project": "your-project-id",
     "log_name": "cloudaudit.googleapis.com%2Factivity"
   }
   ```

**Requirements**:
- The `google-cloud-logging` package (installed with `.[gcp]`)
- Valid Application Default Credentials (ADC)
- `Logs Viewer` role on the GCP project

**Optional fields**:
- `log_name`: Filter to specific log (e.g., `cloudaudit.googleapis.com%2Factivity`)
- `resource_type`: Filter by resource type (e.g., `gce_instance`, `k8s_container`)

## Security

### Directory Allowlist

LogView restricts file access to a configurable allowlist of directories. This prevents:

- **Path traversal attacks**: Malicious paths like `../../../etc/passwd` are blocked
- **Symlink escapes**: Symlinks pointing outside allowed directories are rejected
- **Unauthorized access**: Only explicitly permitted directories can be read

**Default allowed directories**: `/var/log`, `/opt`, `/home`

> **Security Note**: The default `/home` permission is permissive—it allows reading any user's files that the process has permission to access. For production or multi-user systems, consider restricting this:

```json
{
  "discovery": {
    "allowed_directories": ["/var/log", "/opt/myapp/logs"]
  }
}
```

To disable all file access (cloud-only mode), set an empty list:

```json
{
  "discovery": {
    "allowed_directories": []
  }
}
```

### Timestamps and Timezones

- **Syslog (RFC 3164)**: Timestamps without timezone are interpreted as local time
- **Syslog (RFC 5424/ISO 8601)**: Full timezone support (e.g., `2025-12-07T00:00:05-07:00`)
- **JSON Lines**: ISO 8601 timestamps are parsed and displayed in local time

## Troubleshooting

### Common Issues

**"Access denied" or "outside allowed directories"**
- The file path is not within the configured `allowed_directories`
- Solution: Add the parent directory to `allowed_directories` in config, or move logs to an allowed location

**"Log file not found"**
- The file doesn't exist or the path is incorrect
- Solution: Verify the path with `ls -la /path/to/file`

**"Permission denied" when reading logs**
- The user running LogView doesn't have read permission
- Solution: Add your user to the appropriate group (e.g., `sudo usermod -aG adm $USER` for syslog on Ubuntu)

**No logs appearing / empty list**
- Filter may be too restrictive (wrong time range or severity)
- Solution: Press `f` to open filter, try "All Time" and "DEBUG" severity

**Syslog timestamps showing wrong year**
- RFC 3164 syslog format doesn't include year; the current year is assumed
- For accurate timestamps, configure rsyslog to use RFC 5424 format

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=src/logview

# Type checking
mypy src/

# Linting
ruff check src/ tests/
```

## Project Status

This project is under active development. See [PLAN.md](PLAN.md) for the roadmap.

- [x] Phase 1: Foundation (MVP)
- [x] Phase 2: Syslog & Modals
- [x] Phase 3: Application Logs (logfile adapter with format auto-detection)
- [x] Phase 4: GCP Cloud Logging
- [ ] Phase 5: GKE integration
- [ ] Phase 6: File watching & Enhanced UX
- [ ] Phase 7: Extended format support

## License

MIT
