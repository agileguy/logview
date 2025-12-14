"""Export modal for saving logs to file."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, RadioButton, RadioSet

if TYPE_CHECKING:
    from logview.domain.models import LogEntry


class ExportModal(ModalScreen[Path | None]):
    """Modal for exporting logs to a file.

    Allows selecting JSON or JSONL format and specifying output path.
    Returns the path where logs were exported, or None if cancelled.
    """

    DEFAULT_CSS = """
    ExportModal {
        align: center middle;
    }

    ExportModal > Vertical {
        width: 70;
        height: auto;
        max-height: 20;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    ExportModal .export-title {
        text-style: bold;
        text-align: center;
        padding-bottom: 1;
        border-bottom: solid $primary;
        margin-bottom: 1;
        color: $text;
    }

    ExportModal .export-label {
        text-style: bold;
        color: $text-muted;
        margin-bottom: 0;
    }

    ExportModal .export-info {
        color: $text-muted;
        margin-bottom: 1;
    }

    ExportModal RadioSet {
        margin-bottom: 1;
    }

    ExportModal Input {
        width: 100%;
        margin-bottom: 1;
    }

    ExportModal .button-row {
        margin-top: 1;
        padding-top: 1;
        border-top: solid $primary;
        align: center middle;
        height: auto;
    }

    ExportModal Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, entries: list[LogEntry], source_name: str) -> None:
        """Initialize the export modal.

        Args:
            entries: The log entries to export.
            source_name: Name of the log source for default filename.
        """
        super().__init__()
        self._entries = entries
        self._source_name = source_name

    def compose(self) -> ComposeResult:
        """Compose the modal content."""
        # Generate default filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = self._source_name.replace(" ", "_").replace("/", "_")
        default_filename = f"logs_{safe_name}_{timestamp}.json"

        with Vertical():
            yield Label("Export Logs", classes="export-title")
            yield Label(f"Exporting {len(self._entries)} entries", classes="export-info")

            yield Label("Format:", classes="export-label")
            with RadioSet(id="format-select"):
                yield RadioButton("JSON (pretty-printed)", id="json", value=True)
                yield RadioButton("JSONL (one entry per line)", id="jsonl")

            yield Label("Output File:", classes="export-label")
            yield Input(value=default_filename, id="filename-input")

            with Horizontal(classes="button-row"):
                yield Button("Export", variant="primary", id="btn-export")
                yield Button("Cancel", id="btn-cancel")

    def action_cancel(self) -> None:
        """Cancel and close the modal."""
        self.dismiss(None)

    def _get_selected_format(self) -> str:
        """Get the currently selected format.

        Returns:
            'json' or 'jsonl'.
        """
        radio_set = self.query_one("#format-select", RadioSet)
        if radio_set.pressed_button and radio_set.pressed_button.id == "jsonl":
            return "jsonl"
        return "json"

    def _export_logs(self) -> Path | None:
        """Export logs to file.

        Returns:
            Path to exported file, or None on error.
        """
        filename_input = self.query_one("#filename-input", Input)
        filename = filename_input.value.strip()

        if not filename:
            self.notify("Please enter a filename", severity="error")
            return None

        # Ensure path is relative (security: don't allow absolute paths)
        path = Path(filename)
        if path.is_absolute():
            self.notify("Please use a relative filename", severity="error")
            return None

        # Use current working directory
        output_path = Path.cwd() / path

        try:
            format_type = self._get_selected_format()

            if format_type == "json":
                self._write_json(output_path)
            else:
                self._write_jsonl(output_path)

            return output_path

        except PermissionError:
            self.notify("Permission denied writing to file", severity="error")
            return None
        except OSError as e:
            self.notify(f"Error writing file: {e}", severity="error")
            return None

    def _write_json(self, path: Path) -> None:
        """Write entries as pretty-printed JSON array.

        Args:
            path: Output file path.
        """
        data = [
            {
                "timestamp": entry.timestamp.isoformat(),
                "severity": entry.severity.value,
                "message": entry.message,
                "source": entry.source,
                "metadata": entry.metadata,
            }
            for entry in self._entries
        ]

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _write_jsonl(self, path: Path) -> None:
        """Write entries as JSON Lines (one JSON object per line).

        Args:
            path: Output file path.
        """
        with open(path, "w", encoding="utf-8") as f:
            for entry in self._entries:
                data = {
                    "timestamp": entry.timestamp.isoformat(),
                    "severity": entry.severity.value,
                    "message": entry.message,
                    "source": entry.source,
                    "metadata": entry.metadata,
                }
                f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "btn-cancel":
            self.action_cancel()
        elif event.button.id == "btn-export":
            result = self._export_logs()
            if result:
                self.dismiss(result)
