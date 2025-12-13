# LogView

A testable, responsive log viewer TUI with pluggable log source contexts.

## Features

- **Multiple log sources**: GCP Cloud Logging, GKE, syslog, and more
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
      "name": "prod-gke",
      "type": "gke",
      "project": "my-project",
      "cluster": "prod-cluster"
    },
    {
      "name": "local",
      "type": "syslog",
      "path": "/var/log/syslog"
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
- [ ] Phase 2: Syslog adapter
- [ ] Phase 3: GCP Cloud Logging
- [ ] Phase 4: GKE integration
- [ ] Phase 5: Enhanced UX
- [ ] Phase 6: Additional sources

## License

MIT
