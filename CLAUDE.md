# LogView - Claude Code Instructions

## Project Overview

LogView is a Python TUI application for viewing logs from multiple sources (GCP, GKE, syslog). Built with Textual framework.

## Key Commands

```bash
# Run the app
python -m logview

# Run tests
pytest

# Type check
mypy src/

# Lint
ruff check src/ tests/
```

## Architecture

- `src/logview/adapters/` - Log source implementations (Protocol-based)
- `src/logview/domain/` - Core models (LogEntry, Filter, Severity)
- `src/logview/ui/` - Textual widgets and screens
- `src/logview/config/` - JSON configuration with Pydantic schemas

## Development Guidelines

1. **All log sources implement `LogSource` protocol** (`adapters/base.py`)
2. **Configuration is JSON** - never YAML
3. **Tests required** - pytest with >70% coverage target
4. **Type hints required** - mypy strict mode
5. **Security first** - no credential storage, delegate to gcloud/kubectl

## Current Phase

Phase 1 (Foundation) - Mock adapter working, basic TUI shell complete.

## File Locations

- Main app: `src/logview/app.py`
- Domain models: `src/logview/domain/models.py`
- Config schema: `src/logview/config/schema.py`
- Tests: `tests/`
