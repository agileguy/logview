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
- [ ] Phase 2: Syslog & Modals
- [ ] Phase 3: Application Logs (logfile adapter with format auto-detection)
- [ ] Phase 4: GCP Cloud Logging
- [ ] Phase 5: GKE integration
- [ ] Phase 6: File watching & Enhanced UX
- [ ] Phase 7: Extended format support

## License

MIT
