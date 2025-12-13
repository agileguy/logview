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

## Allowed Tools (No Approval Required)

The following tools can be used freely without user approval:

- `gh` - GitHub CLI (repos, PRs, issues, auth)
- `git` - Version control operations
- `pytest` - Running tests
- `mypy` - Type checking
- `ruff` - Linting and formatting
- `WebSearch` - Web searches for documentation/solutions

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

## Testing & Quality Requirements (MANDATORY)

**Every code change MUST pass all quality checks before push/PR:**

### 1. Tests (MANDATORY)
- **New functionality MUST have tests** - no exceptions
- **All tests MUST pass** before pushing or creating PR
- Test locations:
  - Unit tests: `tests/unit/`
  - Integration tests: `tests/integration/`
  - UI tests: `tests/ui/`

```bash
# Run all tests (MUST pass)
pytest

# Run with coverage (target >70%)
pytest --cov=src/logview
```

### 2. Type Checking (MANDATORY)
- **mypy MUST pass** with no errors before push/PR
- All new code must have type hints

```bash
# Type check (MUST pass)
mypy src/
```

### 3. Linting (MANDATORY)
- **ruff MUST pass** with no errors before push/PR

```bash
# Lint check (MUST pass)
ruff check src/ tests/

# Auto-fix issues
ruff check --fix src/ tests/
```

### Pre-Push Checklist
Run this sequence before every push/PR:

```bash
# All three MUST pass
pytest && mypy src/ && ruff check src/ tests/
```

If any check fails, fix the issues before pushing.

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

**Before committing/pushing, verify:**
- [ ] New functionality has tests
- [ ] `pytest` passes (all tests)
- [ ] `mypy src/` passes (no type errors)
- [ ] `ruff check src/ tests/` passes (no lint errors)
- [ ] All affected documentation is updated
- [ ] PLAN.md phase checklist reflects current state
- [ ] README.md examples still work
- [ ] CLAUDE.md reflects actual project state

## Continuous Integration

GitHub Actions CI runs on all PRs targeting main:

- **Lint**: `ruff check src/ tests/`
- **Type Check**: `mypy src/`
- **Test**: `pytest` on Python 3.11 and 3.12
- **Coverage**: Must maintain >70% coverage

### Snapshot Testing

Snapshot tests use separate directories for CI vs local:
- Local: `tests/__snapshots__/` (tracked in git)
- CI: `tests/__snapshots_ci__/` (gitignored)

This prevents CI environment differences from causing false failures.

## Action Logging (MANDATORY)

**After completing significant work, append a summary to `ACTIONS.md`:**

- What was done (features, fixes, refactors)
- Files changed
- Tests added/modified
- Any issues encountered and how they were resolved

Format:
```markdown
## YYYY-MM-DD: Brief Title

**Changes:**
- Item 1
- Item 2

**Files:** `file1.py`, `file2.py`

**Tests:** Added X tests, all passing
```

## Current Phase

**Phase 2 (Syslog & Modals) - IN PROGRESS**

See ACTIONS.md for detailed progress log.

## File Locations

- Main app: `src/logview/app.py`
- Domain models: `src/logview/domain/models.py`
- Config schema: `src/logview/config/schema.py`
- Tests: `tests/`
- CI workflow: `.github/workflows/ci.yml`
