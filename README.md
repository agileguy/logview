# LogView

[![CI](https://github.com/agileguy/logview/actions/workflows/ci.yml/badge.svg)](https://github.com/agileguy/logview/actions/workflows/ci.yml)

A testable, responsive log viewer TUI with pluggable log source contexts.

## Features

- **Multiple log sources**: Local log files, syslog, GCP Cloud Logging, GKE, and more
- **Format auto-detection**: Automatically detects plain text, JSON Lines, and syslog formats
- **Log discovery**: Scan directories to find log files
- **Tree-based context switcher**: Organized view with configured sources at root, discovered logs in collapsible folder
- **Flexible filtering**: Time range, severity, text search, and source-specific fields
- **Memory efficient**: Batch processing and heap-based selection for large log files
- **Application logging**: Configurable rotating file handler for debugging
- **Keyboard-first**: Full functionality without mouse
- **Testable**: Interface-driven design with comprehensive test coverage

## Installation

### Quick Install (Recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/agileguy/logview/main/install.sh | bash
```

This will:
- Check Python 3.11+ is installed
- Install LogView using pipx (isolated environment) or pip
- Create config directory at `~/.config/logview/`
- Verify the installation

### Alternative Methods

#### Using pipx (Isolated Environment)

```bash
pipx install logview

# With GCP/GKE support
pipx install logview[all]
```

#### Using pip

```bash
pip install logview

# With GCP/GKE support
pip install logview[all]
```

#### From Source (Development)

```bash
git clone https://github.com/agileguy/logview.git
cd logview
pip install -e ".[dev]"
```

### System Requirements

- **Python**: 3.11 or higher
- **Operating System**: Linux or macOS
- **Optional**: pipx (recommended for isolated installation)

### Uninstall

```bash
# Via the install script
curl -fsSL https://raw.githubusercontent.com/agileguy/logview/main/install.sh | bash -s -- --uninstall

# Or manually
pipx uninstall logview  # if installed with pipx
pip uninstall logview   # if installed with pip

# Remove configuration (optional)
rm -rf ~/.config/logview
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

### Application Logging

LogView logs its own activity to help with debugging. Configure logging in your config file:

```json
{
  "logging": {
    "level": "DEBUG",
    "file": "~/.config/logview/logview.log",
    "max_size_mb": 10,
    "backup_count": 3
  }
}
```

| Option | Default | Description |
|--------|---------|-------------|
| `level` | `DEBUG` | Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `file` | `~/.config/logview/logview.log` | Log file path (null for default) |
| `max_size_mb` | `10` | Max log file size before rotation |
| `backup_count` | `3` | Number of rotated log files to keep |

To view logs while running:
```bash
tail -f ~/.config/logview/logview.log
```

### GCP Cloud Logging Setup

To use GCP Cloud Logging as a log source:

1. **Install with GCP support**:
   ```bash
   pipx install logview[all]  # or pip install logview[all]
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

### GKE (Google Kubernetes Engine) Setup

GKE logs are stored in Cloud Logging, so LogView queries them via the Cloud Logging API
with Kubernetes-specific resource filters.

1. **Install with GCP support** (same as GCP Cloud Logging):
   ```bash
   pipx install logview[all]  # or pip install logview[all]
   ```

2. **Authenticate with GCP**:
   ```bash
   gcloud auth application-default login
   ```

3. **Add a GKE context to your config**:
   ```json
   {
     "name": "prod-cluster",
     "type": "gke",
     "project": "your-project-id",
     "cluster": "your-cluster-name",
     "location": "us-central1-a",
     "default_namespace": "default"
   }
   ```

**Required fields**:
- `project`: GCP project ID containing the cluster
- `cluster`: GKE cluster name

**Optional fields**:
- `location`: Cluster zone or region (e.g., `us-central1-a`)
- `default_namespace`: Default namespace filter

**Filter fields** (available in filter modal):
- `namespace`: Kubernetes namespace (supports wildcards: `kube-*`)
- `pod`: Pod name (supports wildcards: `api-server-*`)
- `container`: Container name
- `labels`: Pod labels in `key=value,key2=value2` format

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
- [x] Phase 5: GKE Integration
- [x] Phase 6: Enhanced UX (search, export, themes, help modal)
- [x] Phase 7: Productionization (install.sh, wheel packaging)
- [ ] Phase 8: Additional Sources (AWS CloudWatch, Azure Monitor, Elasticsearch, etc.)

## License

MIT
