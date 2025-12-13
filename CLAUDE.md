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

## Documentation Requirements (MANDATORY)

**Every code change that affects functionality MUST include documentation updates:**

1. **PLAN.md** - Update when:
   - Completing phase deliverables (check off items)
   - Changing project scope or architecture
   - Adding/removing planned features
   - Modifying phase timelines or dependencies

2. **README.md** - Update when:
   - Adding new features or commands
   - Changing installation steps
   - Modifying keyboard shortcuts
   - Updating configuration options
   - Changing usage examples

3. **CLAUDE.md** - Update when:
   - Changing architecture or file locations
   - Adding new development commands
   - Modifying development guidelines
   - Updating current phase status

4. **configs/example.json** - Update when:
   - Adding new configuration options
   - Changing config schema
   - Adding new context types

5. **Docstrings/Comments** - Update when:
   - Changing function signatures
   - Modifying class behavior
   - Altering public APIs

**Before committing, verify:**
- [ ] All affected documentation is updated
- [ ] PLAN.md phase checklist reflects current state
- [ ] README.md examples still work
- [ ] CLAUDE.md reflects actual project state

## Current Phase

**Phase 1 (Foundation) - COMPLETE** ✅

Ready for Phase 2 (Syslog adapter, modals, config file support).

## File Locations

- Main app: `src/logview/app.py`
- Domain models: `src/logview/domain/models.py`
- Config schema: `src/logview/config/schema.py`
- Tests: `tests/`
