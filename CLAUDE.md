# LogView - Claude Code Instructions

## Project Overview

LogView is a Python TUI application for viewing logs from multiple sources (local log files, syslog, GCP, GKE). Built with Textual framework. Supports format auto-detection for plain text, JSON Lines, and syslog formats.

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

### Version Control & GitHub
- `git` - All git operations (`git:*`)
- `gh` - GitHub CLI (repos, PRs, issues, auth, runs, api)

### Python Development
- `.venv/bin/pytest:*` - Running tests
- `.venv/bin/mypy:*` - Type checking (e.g., `.venv/bin/mypy src/`)
- `.venv/bin/ruff:*` - Linting (e.g., `.venv/bin/ruff check src/ tests/`)
- `.venv/bin/python3:*` - Python execution
- `.venv/bin/pip:*` - Package management
- `source .venv/bin/activate` - Activate virtual environment
- `pip install:*` - Install packages
- `pip show:*` - Show package info
- `pytest:*` - Running tests (system pytest)
- `python -m pytest:*` - Running pytest as module
- `mypy:*` - Type checking (system mypy)
- `ruff check:*` - Linting and formatting
- `python:*` / `python3:*` - Python execution
- `coverage run:*` / `coverage report:*` - Coverage tools
- `timeout 3 python3:*` - Timeout-limited execution
- `pipx inject:*` - pipx package injection
- `find:*` - File finding

### Web
- `WebSearch` - Web searches for documentation/solutions

## Architecture

- `src/logview/adapters/` - Log source implementations (Protocol-based)
- `src/logview/domain/` - Core models (LogEntry, Filter, Severity)
- `src/logview/ui/` - Textual widgets and screens
- `src/logview/config/` - JSON configuration with Pydantic schemas
  - `schema.py` - Pydantic models including LoggingSettings
  - `loader.py` - Config file loading/saving
  - `logging.py` - Application logging setup (rotating file handler)

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

GitHub Actions CI runs on all PRs targeting main and on pushes to main:

- **Lint**: `ruff check src/ tests/`
- **Type Check**: `mypy src/`
- **Test**: `pytest` on Python 3.11 and 3.12
- **Coverage**: Must maintain >70% coverage

### CI Badge Behavior

The README.md CI status badge reflects the status of the most recent CI run on the `main` branch. The workflow is configured to run on:
- Pull requests targeting `main` (for pre-merge validation)
- Pushes to `main` (to update badge status after merges)

This ensures the badge accurately reflects the current state of the main branch rather than showing stale status from historical pushes.

### Snapshot Testing

Snapshot tests use separate directories for CI vs local:
- Local: `tests/__snapshots__/` (tracked in git)
- CI: `tests/__snapshots_ci__/` (gitignored)

This prevents CI environment differences from causing false failures.

## Pull Request Management (MANDATORY)

### Monitor Open PRs

**When a PR is open, you MUST:**

1. **Check CI status** after pushing:
   ```bash
   gh pr checks <PR_NUMBER>
   ```

2. **Fix any failing checks immediately** - do not leave PRs with red CI:
   - Read the failure logs: `gh run view <RUN_ID> --log-failed`
   - Fix the issue locally
   - Push the fix
   - Verify CI passes

3. **Do not consider work complete until all checks pass**

### Cursor Reviews (MANDATORY)

**When Cursor Bugbot reviews a PR, you MUST:**

1. **Check for ALL review comments** (not just the first few):
   ```bash
   gh api repos/{owner}/{repo}/pulls/{pr}/comments | jq '.[].body'
   ```

2. **Count the total number of issues** and track each one:
   ```bash
   gh api repos/{owner}/{repo}/pulls/{pr}/comments | jq 'length'
   ```

3. **Implement EVERY suggestion** from Cursor reviews:
   - Bug fixes (security, logic errors, resource leaks)
   - Code improvements
   - Missing edge cases
   - **Do not skip any comments** - address all of them

4. **Verify each fix** is in place before considering it done

5. **Push fixes and verify** the review issues are resolved

6. **REPEAT the commit-review cycle until no new comments**:
   - After pushing fixes, Cursor will review again and may add new comments
   - **ALWAYS** re-check the PR for new review comments after each push
   - If new comments appear, fix them and push again
   - **Continue this cycle until a push yields ZERO new comments**
   - This is MANDATORY - do not stop until the cycle completes with no comments

7. **Only mark PR as ready** after:
   - All CI checks pass
   - **ALL** Cursor review suggestions implemented (not just some)
   - **The commit-review cycle completed with no new comments**

### PR Checklist

Before considering a PR complete:
- [ ] All CI checks pass (green)
- [ ] Cursor review suggestions implemented
- [ ] Commit-review cycle repeated until no new comments appear
- [ ] ACTIONS.md updated with changes
- [ ] Version bumped if releasing (VERSION, CHANGELOG.md)

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

## Semantic Versioning (MANDATORY)

This project follows [Semantic Versioning](https://semver.org/) (MAJOR.MINOR.PATCH):

- **MAJOR**: Breaking changes (incompatible API changes)
- **MINOR**: New features (backwards compatible)
- **PATCH**: Bug fixes (backwards compatible)

### Version Files (MUST update together)

| File | Purpose |
|------|---------|
| `VERSION` | **Single source of truth** - contains version string only |
| `CHANGELOG.md` | Human-readable history of changes per version |

### When to Update Version

**Bump PATCH (0.0.X)** for:
- Bug fixes
- Security patches
- Documentation fixes

**Bump MINOR (0.X.0)** for:
- New features
- New adapters or modals
- New configuration options
- Deprecations (with backwards compatibility)

**Bump MAJOR (X.0.0)** for:
- Breaking API changes
- Removed features
- Incompatible configuration changes

### Version Update Process (MANDATORY)

When releasing changes:

1. **Update `VERSION`** file with new version number
2. **Update `CHANGELOG.md`**:
   - Move items from `[Unreleased]` to new version section
   - Add release date
   - Update comparison links at bottom
3. **Commit** with message: `chore: bump version to X.Y.Z`
4. **Tag** the release: `git tag vX.Y.Z`

```bash
# Example version bump workflow
echo "0.3.0" > VERSION
# Edit CHANGELOG.md to move [Unreleased] to [0.3.0]
git add VERSION CHANGELOG.md
git commit -m "chore: bump version to 0.3.0"
git tag v0.3.0
```

### Accessing Version in Code

```python
from logview import __version__
print(__version__)  # e.g., "0.2.0"
```

## Current Phase

**Phase 6 (Enhanced UX) - COMPLETE**

All phases 1-6 complete. Project ready for Phase 7 (Additional Sources) or production use.

Key achievements:
- Help modal, search within results, export logs, filter presets
- Settings modal with full theme support (12 built-in Textual themes)
- Enhanced status bar showing adapter and filter information
- Theme persistence from command palette and settings modal

See ACTIONS.md for detailed progress log.

## File Locations

- Main app: `src/logview/app.py`
- Domain models: `src/logview/domain/models.py`
- Config: `src/logview/config/`
  - `schema.py` - Pydantic models (Config, LoggingSettings, contexts)
  - `loader.py` - Config file loading/saving
  - `logging.py` - Application logging setup
- Log adapters: `src/logview/adapters/`
  - `gcp.py` - GCP Cloud Logging adapter (batch processing)
  - `logfile.py` - Generic log file adapter (heap-based top-N)
  - `syslog.py` - Syslog file adapter
  - `jsonl_parser.py` - JSON Lines format parser
  - `plaintext_parser.py` - Plain text log parser
  - `discovery.py` - Log file discovery service
- UI screens: `src/logview/ui/screens/`
  - `context.py` - Tree-based context switcher modal
  - `filter.py` - Filter editor modal
  - `detail.py` - Log detail modal
- Tests: `tests/`
- CI workflow: `.github/workflows/ci.yml`
- Version: `VERSION`
- Changelog: `CHANGELOG.md`
- Action log: `ACTIONS.md`
- Application log: `~/.config/logview/logview.log` (runtime)
