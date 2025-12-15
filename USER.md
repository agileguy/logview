# LogView User Manual

**Version 0.6.0**

A comprehensive guide to using LogView, a terminal-based log viewer with support for multiple log sources including local files, syslog, GCP Cloud Logging, and Google Kubernetes Engine (GKE).

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Installation](#installation)
3. [Basic Usage](#basic-usage)
4. [Configuration](#configuration)
5. [Log Sources](#log-sources)
6. [Viewing Logs](#viewing-logs)
7. [Filtering Logs](#filtering-logs)
8. [Searching](#searching)
9. [Themes and Appearance](#themes-and-appearance)
10. [Exporting Logs](#exporting-logs)
11. [Keyboard Shortcuts](#keyboard-shortcuts)
12. [Advanced Features](#advanced-features)
13. [Troubleshooting](#troubleshooting)
14. [FAQ](#faq)

---

## Getting Started

### What is LogView?

LogView is a terminal user interface (TUI) application that lets you view and search logs from multiple sources in a single, unified interface. Whether you're debugging a local application, monitoring cloud services, or investigating Kubernetes pod logs, LogView provides a consistent, keyboard-driven experience.

### Key Features

- **Multiple log sources**: Local files, syslog, GCP Cloud Logging, GKE clusters
- **Smart format detection**: Automatically recognizes plain text, JSON Lines, and syslog formats
- **Powerful filtering**: Filter by time range, severity, text search, and source-specific fields
- **Search within results**: Find specific entries in already-loaded logs
- **Export capabilities**: Save filtered logs to JSON or JSONL files
- **Filter presets**: Save and reuse common filter configurations
- **Customizable themes**: Choose from 12 built-in color themes
- **Keyboard-first**: All features accessible via keyboard shortcuts

### Prerequisites

- Python 3.11 or higher
- Terminal emulator with 256 color support
- For GCP/GKE: Google Cloud SDK installed and authenticated

---

## Installation

### Using pip

```bash
# Basic installation
pip install -e .

# With GCP/GKE support
pip install -e ".[gcp]"

# With all optional dependencies
pip install -e ".[all]"

# For development (includes testing tools)
pip install -e ".[dev]"
```

### Using uv (recommended)

```bash
uv pip install -e .

# With GCP support
uv pip install -e ".[gcp]"
```

### Verify Installation

```bash
# Run LogView
logview

# Or as a module
python -m logview
```

You should see the LogView interface with a mock log source (used for testing).

---

## Basic Usage

### First Run

When you first run LogView without any configuration, you'll see:

1. **Header**: Shows "LogView" title
2. **Log List**: Central area displaying log entries (mock data initially)
3. **Footer**: Keyboard shortcuts for common actions

### Navigation Basics

- **↑/↓ Arrow keys**: Move up and down through log entries
- **Enter**: View detailed information about the selected log entry
- **q**: Quit the application
- **?**: Show help with all keyboard shortcuts

### Your First Workflow

1. **Press `?`** to see the help modal with all available commands
2. **Press `c`** to open the context switcher (log source selector)
3. **Press `f`** to open the filter editor
4. **Press `/`** to search within the currently displayed logs
5. **Press `s`** to open settings and customize your experience

---

## Configuration

### Configuration File Location

LogView looks for configuration at:

```
~/.config/logview/config.json
```

### Creating Your First Config

Create the config directory and file:

```bash
mkdir -p ~/.config/logview
nano ~/.config/logview/config.json
```

### Basic Configuration Example

```json
{
  "contexts": [
    {
      "name": "System Logs",
      "type": "syslog",
      "path": "/var/log/syslog"
    }
  ],
  "ui": {
    "theme": "dark",
    "timestamp_format": "%Y-%m-%d %H:%M:%S"
  }
}
```

### Full Configuration Example

See `configs/example.json` in the LogView repository for a comprehensive example showing all available options.

### Configuration Schema

The configuration file uses JSON format with the following top-level sections:

- **contexts**: Array of log sources
- **discovery**: Settings for automatic log file discovery
- **presets**: Saved filter configurations
- **ui**: Theme and display settings
- **security**: Authentication settings
- **logging**: Application logging configuration

---

## Log Sources

LogView supports multiple types of log sources, called "contexts."

### Syslog

View local syslog files in RFC 3164 or RFC 5424 format.

```json
{
  "name": "System Logs",
  "type": "syslog",
  "path": "/var/log/syslog"
}
```

**Permissions**: You may need to add your user to the `adm` group:

```bash
sudo usermod -aG adm $USER
# Log out and back in for changes to take effect
```

### Log Files (Generic)

View any text-based log file with automatic format detection.

```json
{
  "name": "Application Logs",
  "type": "logfile",
  "path": "/var/log/myapp/app.log",
  "format": "auto"
}
```

**Supported formats**:
- `auto`: Automatically detect format (recommended)
- `plain`: Plain text, one line per entry
- `jsonl`: JSON Lines (one JSON object per line)
- `syslog`: Syslog format (RFC 3164/5424)

**JSON Lines format**: LogView looks for common field names:
- **Timestamp**: `timestamp`, `time`, `ts`, `@timestamp`, `date`
- **Severity**: `level`, `severity`, `log_level`, `loglevel`
- **Message**: `message`, `msg`, `text`, `log`

Example JSON Lines log:
```json
{"timestamp": "2025-12-14T10:30:00Z", "level": "INFO", "message": "Server started"}
{"timestamp": "2025-12-14T10:30:05Z", "level": "WARN", "message": "High memory usage"}
```

### GCP Cloud Logging

View logs from Google Cloud Platform projects.

**Setup**:

1. Install GCP support:
   ```bash
   pip install -e ".[gcp]"
   ```

2. Authenticate with Google Cloud:
   ```bash
   gcloud auth application-default login
   ```

3. Add GCP context to config:
   ```json
   {
     "name": "Production GCP",
     "type": "gcp",
     "project": "my-project-id",
     "log_name": "cloudaudit.googleapis.com%2Factivity"
   }
   ```

**Optional fields**:
- `log_name`: Filter to specific log (e.g., audit logs)
- `resource_type`: Filter by resource (e.g., `gce_instance`, `k8s_container`)

**Permissions required**: `Logs Viewer` role on the GCP project

### GKE (Google Kubernetes Engine)

View logs from Kubernetes pods running in GKE.

**Setup**: Same as GCP Cloud Logging (GKE logs are stored in Cloud Logging)

**Configuration**:
```json
{
  "name": "Production Cluster",
  "type": "gke",
  "project": "my-project-id",
  "cluster": "prod-cluster",
  "location": "us-central1-a",
  "default_namespace": "default"
}
```

**Required fields**:
- `project`: GCP project ID
- `cluster`: GKE cluster name

**Optional fields**:
- `location`: Cluster zone or region
- `default_namespace`: Default namespace for filters

**GKE-specific filters** (available in filter modal):
- **Namespace**: Filter by Kubernetes namespace (supports wildcards: `kube-*`)
- **Pod**: Filter by pod name (supports wildcards: `api-server-*`)
- **Container**: Filter by container name within pod
- **Labels**: Filter by pod labels (`app=nginx,env=prod`)

### Mock (Testing)

Built-in test data source for trying out LogView.

```json
{
  "name": "Test Data",
  "type": "mock",
  "seed": 42
}
```

The `seed` parameter ensures reproducible random data.

---

## Viewing Logs

### The Log List

The main view shows a scrollable list of log entries with:

- **Timestamp**: When the log entry occurred
- **Severity**: Log level (DEBUG, INFO, WARN, ERROR, CRITICAL)
- **Source**: Where the log came from (pod name, file, etc.)
- **Message**: The log message content

**Example**:
```
2025-12-14 10:23:45 INFO  api-server-abc12  Request completed in 125ms
2025-12-14 10:23:44 WARN  db-proxy-xyz89    Connection pool at 90% capacity
2025-12-14 10:23:42 ERROR worker-def34      Task failed: timeout after 30s
```

### Navigating Logs

- **↑/↓**: Move selection up/down
- **Page Up/Page Down**: Scroll by page
- **Home/End**: Jump to first/last entry
- **Mouse scroll**: Scroll through entries (if mouse support enabled)

### Viewing Details

**Press `Enter`** on any log entry to open the detail modal showing:

1. **Full timestamp**: With timezone information
2. **Severity level**: Color-coded
3. **Source**: Full source identifier
4. **Message**: Complete message (may be truncated in list view)
5. **Metadata**: Additional fields as JSON (namespace, pod, labels, etc.)
6. **Raw**: Original log entry format

**In the detail modal**:
- **↑/↓**: Scroll content if it doesn't fit on screen
- **c**: Copy the entire entry as JSON to clipboard
- **Esc**: Close the modal

### Switching Log Sources

**Press `c`** to open the context switcher modal.

The context switcher shows:
- **Configured sources**: At the root level (from your config file)
- **Discovered logs**: In a collapsible "Discovered Logs" folder
- **Active source**: Marked with a bullet (●)

**Navigation**:
- **↑/↓**: Move selection
- **→/←**: Expand/collapse the discovered logs folder
- **Enter**: Switch to selected source
- **Esc**: Cancel and close modal

---

## Filtering Logs

Filtering lets you narrow down logs by time range, severity, text content, and source-specific criteria.

### Opening the Filter Modal

**Press `f`** to open the filter editor.

### Filter Options

#### Time Range

Select how far back to search:

- **All Time**: No time restriction
- **Last 5 minutes**: Recent logs only
- **Last 1 hour**
- **Last 6 hours**
- **Last 24 hours**
- **Last 7 days**

**Tip**: Start with a narrow time range for faster results, then expand if needed.

#### Severity

Filter by minimum log level:

- **DEBUG**: Show all logs (most verbose)
- **INFO**: Hide debug logs
- **WARN**: Show warnings, errors, and critical only
- **ERROR**: Show errors and critical only
- **CRITICAL**: Show only critical logs

**Example**: Selecting WARN shows WARN, ERROR, and CRITICAL entries, but hides DEBUG and INFO.

#### Text Search

Search for specific text in log messages:

- Case-insensitive
- Matches anywhere in the message
- Use with other filters for precise results

**Example**: Search for "connection" to find connection-related logs.

#### Result Limit

Limit the number of entries returned:

- **Default**: 1000 entries
- **Range**: 1 to 10,000
- **Tip**: Lower limits load faster

#### Source-Specific Filters

Additional fields appear based on your current log source:

**GKE sources**:
- **Namespace**: Kubernetes namespace (e.g., `default`, `kube-system`)
- **Pod**: Pod name (supports wildcards: `api-*`)
- **Container**: Container name within the pod
- **Labels**: Pod labels in `key=value,key2=value2` format

**Wildcard support** (GKE):
- Trailing wildcards only: `kube-*` ✓
- Internal wildcards not allowed: `*-system` ✗
- Wildcard-only not allowed: `*` ✗

### Applying Filters

1. **Tab/Shift+Tab**: Move between fields
2. **Enter**: Apply the filter and close modal
3. **Esc**: Cancel without applying

### Clearing Filters

In the filter modal, click the **Clear** button or press its shortcut to reset all filters to defaults.

### Filter Presets

**Save frequently-used filters** for quick access.

#### Saving a Preset

1. Configure your desired filter settings
2. In the filter modal, click **Save Preset**
3. Enter a name (e.g., "Errors Last Hour")
4. Press Enter to save

#### Loading a Preset

1. Open the filter modal (`f`)
2. Select a preset from the dropdown at the top
3. The filter fields will populate with saved values
4. Click Apply or modify as needed

#### Deleting a Preset

1. Open the filter modal
2. Select the preset you want to delete
3. Click **Delete** next to the preset dropdown

**Presets are saved** in your config file under the `presets` section.

### Example Filter Workflows

**Find errors in the last hour**:
1. Press `f`
2. Time Range: Last 1 hour
3. Severity: ERROR
4. Apply

**Find specific pod logs**:
1. Press `c` to switch to GKE context
2. Press `f`
3. Namespace: `default`
4. Pod: `api-server-*`
5. Apply

**Debug recent API issues**:
1. Press `f`
2. Time Range: Last 5 minutes
3. Text Search: `api`
4. Severity: DEBUG
5. Apply

---

## Searching

In addition to filtering, LogView provides **search within results** to find specific entries in already-loaded logs.

### Starting a Search

**Press `/`** to activate search mode.

A search bar appears at the bottom of the screen with:
- Input field for your search query
- Match counter showing `X/Y matches` (current/total)

### How Search Works

- **Case-insensitive**: Finds "error", "Error", and "ERROR"
- **Searches all fields**: Message, source, metadata
- **Real-time**: Results update as you type
- **Highlights matches**: Matching entries highlighted in the list

### Navigating Matches

- **n**: Jump to next match
- **N**: Jump to previous match
- **Esc**: Clear search and close search bar

### Search vs. Filter

**Search**:
- Works on currently displayed logs (fast)
- Real-time highlighting as you type
- Great for finding specific entries quickly
- Doesn't fetch new logs from source

**Filter**:
- Fetches fresh logs from the source (slower)
- Supports time range, severity, and source-specific filters
- Use when you need to load different data

**Best practice**: Use filtering to load the right set of logs, then use search to find specific entries within them.

### Example Search Workflow

1. **Press `f`**: Filter to last 1 hour, ERROR severity
2. **Press `/`**: Start search
3. **Type "timeout"**: Find all timeout errors
4. **Press `n`**: Jump through timeout errors one by one
5. **Press Enter**: View details of specific error
6. **Press `Esc`**: Clear search when done

---

## Themes and Appearance

### Available Themes

LogView includes 12 built-in color themes:

**Base themes**:
- **dark** (default): Dark background, light text
- **light**: Light background, dark text
- **ansi**: Classic terminal colors

**Custom themes**:
- **catppuccin-latte**: Warm, latte-inspired palette
- **catppuccin-mocha**: Dark, mocha-inspired palette
- **dracula**: Popular Dracula theme
- **flexoki**: Flexible color scheme
- **gruvbox**: Retro groove colors
- **monokai**: Sublime Text inspired
- **nord**: Arctic, north-bluish color palette
- **solarized-light**: Precision colors (light)
- **tokyo-night**: Tokyo Night theme

### Changing Themes

**Method 1: Settings Modal** (Recommended)

1. Press `s` to open settings
2. Select theme from dropdown
3. Click Save
4. Theme changes immediately and persists to config

**Method 2: Command Palette**

1. Press `Ctrl+P` to open command palette
2. Type "theme" to filter theme commands
3. Select your desired theme
4. Theme changes immediately and persists to config

**Method 3: Toggle Dark/Light**

- Press `Ctrl+T` to quickly toggle between dark and light themes

### Theme Persistence

All theme changes are **automatically saved** to your config file (`~/.config/logview/config.json`), so your preference is remembered across sessions.

### Other Appearance Settings

Press `s` to access the settings modal:

#### Timestamp Format

Choose from common presets or use a custom format string:

- **YYYY-MM-DD HH:MM:SS** (default): `2025-12-14 10:30:45`
- **ISO 8601**: `2025-12-14T10:30:45`
- **12-hour**: `2025-12-14 10:30:45 AM`
- **Date only**: `2025-12-14`
- **Time only**: `10:30:45`

Uses Python's `strftime` format. [Format codes reference](https://strftime.org/)

#### Max Message Width

Set the maximum width for log messages before wrapping:

- **Default**: 80 characters
- **Range**: 20-500 characters
- **Tip**: Increase for wide terminals, decrease for narrow ones

#### Show Metadata

Toggle whether to show metadata fields in the log list view:

- **Enabled**: Shows namespace, pod, labels inline
- **Disabled** (default): Cleaner view, metadata available in detail modal

---

## Exporting Logs

Export currently displayed logs to a file for sharing, archiving, or external analysis.

### Starting an Export

**Press `e`** to open the export dialog.

### Export Options

**Format**:
- **JSON**: Pretty-printed JSON array (human-readable)
- **JSONL**: JSON Lines (one object per line, machine-friendly)

**Filename**:
- Default: `logview-export-YYYY-MM-DD-HHMMSS.json`
- Customize as needed
- Path: Relative to current directory or absolute path

### What Gets Exported

The export includes:
- **All currently displayed logs** (respects active filters and search)
- **Full log entry data**: timestamp, severity, message, source, metadata
- **ISO 8601 timestamps** for portability

**Note**: Export captures the visible logs at the time you press `e`. If you have 1000 entries loaded but only 50 match your search, only those 50 are exported.

### Export Workflow Examples

**Export error logs from last hour**:
1. Press `f` → Last 1 hour, ERROR severity → Apply
2. Press `e` → Select JSON format
3. Enter filename: `errors-2025-12-14.json`
4. Export

**Export specific pod logs**:
1. Press `c` → Select GKE context
2. Press `f` → Namespace: `default`, Pod: `api-server-*` → Apply
3. Press `/` → Search for "timeout"
4. Press `e` → Select JSONL format
5. Export

### Using Exported Logs

**JSON format** (single file analysis):
```bash
# Pretty print
jq '.' errors-2025-12-14.json

# Count by severity
jq '[.[] | .severity] | group_by(.) | map({severity: .[0], count: length})' errors.json

# Filter in jq
jq '[.[] | select(.message | contains("timeout"))]' errors.json
```

**JSONL format** (streaming/line-by-line):
```bash
# Count lines
wc -l export.jsonl

# Grep for specific content
grep "timeout" export.jsonl

# Process with jq (one at a time)
cat export.jsonl | jq -c 'select(.severity == "ERROR")'
```

---

## Keyboard Shortcuts

### Navigation

| Shortcut | Action |
|----------|--------|
| `↑` / `k` | Move selection up |
| `↓` / `j` | Move selection down |
| `Page Up` | Scroll up one page |
| `Page Down` | Scroll down one page |
| `Home` | Jump to first entry |
| `End` | Jump to last entry |
| `Enter` | View log details |

### Actions

| Shortcut | Action |
|----------|--------|
| `c` | Change context (switch log source) |
| `f` | Open filter editor |
| `r` | Refresh logs |
| `/` | Search within results |
| `n` | Next search match |
| `N` | Previous search match |
| `e` | Export logs to file |
| `s` | Open settings |
| `?` | Show help |

### General

| Shortcut | Action |
|----------|--------|
| `Ctrl+T` | Toggle dark/light theme |
| `Ctrl+P` | Open command palette |
| `Esc` | Close modal / Cancel |
| `Tab` | Next field (in modals) |
| `Shift+Tab` | Previous field (in modals) |
| `q` | Quit application |

### In Detail Modal

| Shortcut | Action |
|----------|--------|
| `↑` / `↓` | Scroll content |
| `c` | Copy entry as JSON to clipboard |
| `Esc` | Close modal |

---

## Advanced Features

### Log Discovery

Automatically find log files in configured directories.

**Configuration**:
```json
{
  "discovery": {
    "paths": ["/var/log", "/opt/logs"],
    "max_depth": 3,
    "allowed_directories": ["/var/log", "/opt", "/home"]
  }
}
```

**How it works**:
- On startup, LogView scans `paths` for readable log files
- Found logs appear in the context switcher under "Discovered Logs"
- Select a discovered log to add it as a context

**Discovery behavior**:
- Recursively searches up to `max_depth` subdirectories
- Skips compressed files (`.gz`, `.bz2`, `.xz`)
- Skips hidden files and directories (starting with `.`)
- Skips binary files
- Respects `allowed_directories` for security

### Application Logging

LogView can log its own activity for debugging.

**Configuration**:
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

**Settings**:
- `level`: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: DEBUG)
- `file`: Log file path, `null` for default location
- `max_size_mb`: Max file size before rotation (default: 10)
- `backup_count`: Number of rotated files to keep (default: 3)

**Viewing application logs**:
```bash
tail -f ~/.config/logview/logview.log
```

**Use cases**:
- Debugging GCP authentication issues
- Investigating performance problems
- Reporting bugs (attach log file)

### Security Settings

**Directory Allowlist**:

LogView restricts file access to prevent unauthorized access:

```json
{
  "discovery": {
    "allowed_directories": ["/var/log", "/opt/myapp/logs"]
  }
}
```

**Default allowed directories**: `/var/log`, `/opt`, `/home`

**Security features**:
- Path traversal prevention (`../../../etc/passwd` blocked)
- Symlink escape prevention (symlinks outside allowlist rejected)
- No sensitive paths in error messages

**Cloud-only mode** (disable file access):
```json
{
  "discovery": {
    "allowed_directories": []
  }
}
```

### Credential Management

**GCP/GKE Authentication**:

LogView uses Application Default Credentials (ADC):

```bash
# Authenticate
gcloud auth application-default login

# Verify
gcloud auth application-default print-access-token
```

**Credential Helper** (future):
```json
{
  "security": {
    "credential_helper": "gcloud"
  }
}
```

Options: `gcloud`, `env`, `keyring`

**Security principles**:
- No plaintext credentials stored
- No service account key files
- Delegates to system tools (gcloud)
- No credentials in application logs

---

## Troubleshooting

### Common Issues

#### "Access denied" or "outside allowed directories"

**Problem**: File path not in `allowed_directories`

**Solution**:
1. Add parent directory to `allowed_directories` in config
2. Or move log files to an allowed location
3. Check file permissions: `ls -la /path/to/logfile`

#### "Log file not found"

**Problem**: File doesn't exist or path incorrect

**Solution**:
1. Verify path: `ls /path/to/logfile`
2. Check for typos in config file
3. Ensure path is absolute (starts with `/`)

#### "Permission denied" reading logs

**Problem**: User doesn't have read permission

**Solution** (for syslog on Ubuntu/Debian):
```bash
# Add user to adm group
sudo usermod -aG adm $USER

# Log out and back in
```

#### No logs appearing / empty list

**Problem**: Filter too restrictive

**Solution**:
1. Press `f` to open filter
2. Try "All Time" time range
3. Try "DEBUG" severity
4. Clear text search field
5. Apply and check results

#### Syslog timestamps showing wrong year

**Problem**: RFC 3164 format doesn't include year

**Solution**: Configure rsyslog to use RFC 5424 format:
```bash
# Edit /etc/rsyslog.conf
$ActionFileDefaultTemplate RSYSLOG_SyslogProtocol23Format
```

#### GCP authentication errors

**Problem**: No valid credentials or permissions

**Solution**:
1. Authenticate: `gcloud auth application-default login`
2. Verify project access: `gcloud projects list`
3. Check IAM roles: Need "Logs Viewer" role
4. Check application log: `~/.config/logview/logview.log`

#### GKE logs not appearing

**Problem**: Wrong cluster name, namespace, or permissions

**Solution**:
1. Verify cluster name: `gcloud container clusters list`
2. Check namespace: `kubectl get namespaces`
3. Verify project ID in config matches GCP project
4. Try broader filter (remove namespace/pod filters)

### Performance Issues

#### Slow log loading

**Causes**:
- Large time range (e.g., "All Time")
- Very high result limit (e.g., 10,000)
- GCP/GKE queries with broad filters

**Solutions**:
1. Narrow time range (try "Last 1 hour")
2. Lower result limit (try 100-1000)
3. Add text search or severity filter
4. Check network connectivity to GCP

#### High memory usage

**Causes**:
- Many logs loaded in memory
- Large result limit

**Solutions**:
1. Refresh with narrower filter
2. Lower result limit
3. Restart LogView periodically

#### Slow terminal rendering

**Causes**:
- Very long log messages
- Terminal emulator performance

**Solutions**:
1. Decrease `max_message_width` in settings
2. Use a faster terminal emulator (e.g., Alacritty, Kitty)
3. Disable metadata display in settings

### Getting Help

**Check application logs**:
```bash
tail -n 100 ~/.config/logview/logview.log
```

**Report issues**:
- GitHub Issues: https://github.com/agileguy/logview/issues
- Include: LogView version, OS, error messages, config (sanitized)
- Attach application log if relevant

**Version information**:
```bash
python -c "from logview import __version__; print(__version__)"
```

---

## FAQ

### General

**Q: Can LogView tail logs in real-time?**

A: Not in version 0.6.0. Live tailing is planned for a future release. Currently, press `r` to manually refresh.

**Q: Does LogView work on Windows?**

A: LogView is designed for Unix-like systems (Linux, macOS). Windows support via WSL may work but is not officially supported.

**Q: Can I add custom log sources?**

A: Currently, you need to modify the code to add new adapters. A plugin system is under consideration for future versions.

**Q: Does LogView store or transmit logs?**

A: No. LogView fetches logs on-demand and keeps them in memory only. Nothing is stored or sent anywhere except when you explicitly export to a file.

### Configuration

**Q: Where is the config file?**

A: `~/.config/logview/config.json` on Linux/macOS.

**Q: Can I use environment variables in config?**

A: Not currently. Use absolute paths or `~` for home directory.

**Q: How do I reset config to defaults?**

A: Delete or rename `~/.config/logview/config.json` and restart LogView.

**Q: Can I have multiple config files?**

A: Not currently, but you can swap config files manually or use symlinks.

### Log Sources

**Q: Can LogView read compressed logs (.gz)?**

A: Not directly. Decompress first: `gunzip file.log.gz`

**Q: Can LogView read from stdin?**

A: Not currently. Redirect to a file first: `command > /tmp/output.log`

**Q: Does LogView support AWS CloudWatch?**

A: Not yet. CloudWatch support is planned for Phase 7.

**Q: Can I read logs from a remote server?**

A: Via SSH tunnel or GCP/GKE cloud logging. Direct SSH support not yet implemented.

### GCP/GKE

**Q: Do I need to install gcloud CLI?**

A: Yes, for authentication via `gcloud auth application-default login`.

**Q: Can I use service account keys?**

A: Not recommended for security reasons. Use ADC (Application Default Credentials).

**Q: Which GCP roles do I need?**

A: `roles/logging.viewer` (Logs Viewer) is sufficient for read-only access.

**Q: Can I query multiple GCP projects at once?**

A: Not in a single view. Add separate contexts for each project.

**Q: Why don't I see all my GKE pods?**

A: Check namespace filter. Try leaving namespace empty to see all namespaces.

### Filtering and Search

**Q: Can I use regular expressions in search?**

A: Not currently. Text search is literal substring matching (case-insensitive).

**Q: Can I filter by multiple severities?**

A: No, the severity filter is "minimum level and above." Select DEBUG to see all.

**Q: How do I search for an exact phrase?**

A: Just type the phrase in text search. All searches are substring matches.

**Q: Can I save searches?**

A: Via filter presets. Save your filter configuration including text search.

### Exporting

**Q: Can I export to CSV?**

A: Not currently. Use JSON/JSONL and convert with tools like `jq` or Python.

**Q: Is there a size limit for exports?**

A: Limited by available memory and loaded log count. Export only what you need.

**Q: Can I export directly to cloud storage?**

A: Not currently. Export locally, then upload manually.

### Themes and Appearance

**Q: Can I create custom themes?**

A: Not via config. You can modify Textual CSS files in the source code.

**Q: Why doesn't my theme look right?**

A: Ensure your terminal supports 256 colors. Try `echo $TERM` (should be `xterm-256color` or similar).

**Q: Can I customize keybindings?**

A: Not in version 0.6.0. Keybinding customization is planned for future releases.

---

## Appendix A: Configuration Reference

### Full Config Schema

```json
{
  "contexts": [
    {
      "name": "string",
      "type": "syslog|logfile|gcp|gke|mock",
      // Type-specific fields below
    }
  ],
  "discovery": {
    "paths": ["string"],
    "max_depth": "number",
    "allowed_directories": ["string"]
  },
  "presets": [
    {
      "name": "string",
      "severity": "DEBUG|INFO|WARN|ERROR|CRITICAL",
      "time_range_minutes": "number",
      "namespace": "string",
      "pod": "string",
      "text_search": "string"
    }
  ],
  "ui": {
    "theme": "string",
    "timestamp_format": "string",
    "max_message_width": "number",
    "show_metadata": "boolean"
  },
  "security": {
    "credential_helper": "gcloud|env|keyring"
  },
  "logging": {
    "level": "DEBUG|INFO|WARNING|ERROR|CRITICAL",
    "file": "string|null",
    "max_size_mb": "number",
    "backup_count": "number"
  }
}
```

### Context Types

**Syslog**:
```json
{
  "name": "string",
  "type": "syslog",
  "path": "string (absolute path)"
}
```

**LogFile**:
```json
{
  "name": "string",
  "type": "logfile",
  "path": "string (absolute path)",
  "format": "auto|plain|syslog|jsonl"
}
```

**GCP**:
```json
{
  "name": "string",
  "type": "gcp",
  "project": "string (project ID)",
  "log_name": "string (optional)",
  "resource_type": "string (optional)"
}
```

**GKE**:
```json
{
  "name": "string",
  "type": "gke",
  "project": "string (project ID)",
  "cluster": "string (cluster name)",
  "location": "string (optional, e.g. us-central1-a)",
  "default_namespace": "string (optional)"
}
```

**Mock**:
```json
{
  "name": "string",
  "type": "mock",
  "seed": "number (optional)"
}
```

---

## Appendix B: Timestamp Format Codes

Common Python `strftime` format codes for timestamp customization:

| Code | Meaning | Example |
|------|---------|---------|
| `%Y` | 4-digit year | 2025 |
| `%m` | Month (01-12) | 12 |
| `%d` | Day of month (01-31) | 14 |
| `%H` | Hour 24-hour (00-23) | 15 |
| `%I` | Hour 12-hour (01-12) | 03 |
| `%M` | Minute (00-59) | 30 |
| `%S` | Second (00-59) | 45 |
| `%p` | AM/PM | PM |
| `%Z` | Timezone name | UTC |
| `%z` | Timezone offset | +0000 |

**Examples**:
- `%Y-%m-%d %H:%M:%S` → `2025-12-14 15:30:45`
- `%Y-%m-%dT%H:%M:%S` → `2025-12-14T15:30:45` (ISO 8601)
- `%m/%d/%Y %I:%M:%S %p` → `12/14/2025 03:30:45 PM`
- `%b %d, %Y` → `Dec 14, 2025`

Full reference: https://strftime.org/

---

## Appendix C: Filter Preset Examples

### Error Logs Last Hour
```json
{
  "name": "Errors Last Hour",
  "severity": "ERROR",
  "time_range_minutes": 60
}
```

### API Debug Logs
```json
{
  "name": "API Debug",
  "pod": "api-server-*",
  "severity": "DEBUG",
  "namespace": "default"
}
```

### Critical Alerts Today
```json
{
  "name": "Critical Today",
  "severity": "CRITICAL",
  "time_range_minutes": 1440
}
```

### Database Connection Issues
```json
{
  "name": "DB Connection",
  "text_search": "connection",
  "pod": "db-*",
  "severity": "WARN"
}
```

---

## Appendix D: Common Workflows

### Debugging a Production Incident

1. **Switch to production GKE cluster** (`c` → select prod cluster)
2. **Filter to incident timeframe** (`f` → Last 1 hour)
3. **Narrow to affected service** (Namespace: `api`, Pod: `checkout-*`)
4. **Look for errors** (Severity: ERROR)
5. **Search for specific errors** (`/` → "timeout")
6. **Export for team** (`e` → Save as JSON)
7. **Share export file** with team for analysis

### Daily Log Review

1. **Create saved presets** for common queries:
   - "Errors Last 24h"
   - "Critical Alerts"
   - "High Memory Usage"
2. **Each morning**:
   - Load "Errors Last 24h" preset
   - Review error count
   - Investigate unusual patterns
   - Export and archive if needed

### Investigating Performance Issues

1. **Filter to slow requests** (Text search: "slow", Severity: WARN)
2. **View details** for each entry to see duration
3. **Look for patterns** (specific pod, time of day)
4. **Expand time range** to see if issue is ongoing
5. **Export logs** for graphing/analysis tools

### Setting Up a New Log Source

1. **Add context to config file**
2. **Restart LogView**
3. **Switch to new context** (`c`)
4. **Test filter** (`f` → Last 5 minutes, DEBUG)
5. **Verify log format** (Check that timestamps, severity parse correctly)
6. **Save common filters** as presets

---

**End of User Manual**

*For technical documentation and development guides, see README.md and CLAUDE.md*

*For project roadmap and architecture, see PLAN.md*

*For detailed change history, see CHANGELOG.md*
