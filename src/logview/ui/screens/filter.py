"""Filter editor modal for configuring log filters."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select

from logview.domain.models import Filter, Severity, TimeRange

if TYPE_CHECKING:
    pass


# Quick time range presets (label, timedelta)
TIME_PRESETS = [
    ("No limit", None),
    ("Last 15 minutes", timedelta(minutes=15)),
    ("Last 1 hour", timedelta(hours=1)),
    ("Last 6 hours", timedelta(hours=6)),
    ("Last 24 hours", timedelta(hours=24)),
    ("Last 7 days", timedelta(days=7)),
]

# Severity options
SEVERITY_OPTIONS = [
    ("All", None),
    ("DEBUG+", Severity.DEBUG),
    ("INFO+", Severity.INFO),
    ("WARN+", Severity.WARN),
    ("ERROR+", Severity.ERROR),
    ("CRITICAL", Severity.CRITICAL),
]


class FilterModal(ModalScreen[Filter | None]):
    """Modal for editing log filters.

    Allows configuring time range, severity level, and text search.
    Returns a Filter object or None if cancelled.
    """

    DEFAULT_CSS = """
    FilterModal {
        align: center middle;
    }

    FilterModal > Vertical {
        width: 70;
        height: auto;
        max-height: 25;
        background: $surface;
        border: thick $primary;
        padding: 1;
    }

    FilterModal .filter-title {
        text-style: bold;
        padding-bottom: 1;
        border-bottom: solid $primary;
        margin-bottom: 1;
    }

    FilterModal .filter-section {
        margin-bottom: 1;
    }

    FilterModal .filter-label {
        text-style: bold;
        color: $text-muted;
        margin-bottom: 0;
    }

    FilterModal Select {
        width: 100%;
        margin-bottom: 1;
    }

    FilterModal Input {
        width: 100%;
        margin-bottom: 1;
    }

    FilterModal .button-bar {
        height: 3;
        align: center middle;
        padding-top: 1;
        border-top: solid $primary;
    }

    FilterModal Button {
        margin: 0 1;
    }

    FilterModal .limit-input {
        width: 20;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+enter", "apply", "Apply"),
    ]

    def __init__(self, current_filter: Filter | None = None) -> None:
        """Initialize the filter modal.

        Args:
            current_filter: The current filter to edit, or None for defaults.
        """
        super().__init__()
        self._current_filter = current_filter or Filter()

    def compose(self) -> ComposeResult:
        """Compose the modal content."""
        with Vertical():
            yield Label("Filter Logs", classes="filter-title")

            # Time range section
            yield Label("Time Range:", classes="filter-label")
            time_options = [(label, str(idx)) for idx, (label, _) in enumerate(TIME_PRESETS)]
            yield Select(time_options, id="time-select", value="0")

            # Severity section
            yield Label("Minimum Severity:", classes="filter-label")
            severity_options = [(label, str(idx)) for idx, (label, _) in enumerate(SEVERITY_OPTIONS)]
            yield Select(severity_options, id="severity-select", value="0")

            # Text search section
            yield Label("Text Search:", classes="filter-label")
            initial_search = self._current_filter.text_search or ""
            yield Input(
                placeholder="Search in log messages...",
                id="text-search",
                value=initial_search,
            )

            # Limit section
            yield Label("Result Limit:", classes="filter-label")
            with Horizontal():
                yield Input(
                    placeholder="1000",
                    id="limit-input",
                    value=str(self._current_filter.limit),
                    classes="limit-input",
                )

            # Button bar
            with Horizontal(classes="button-bar"):
                yield Button("Apply [Ctrl+Enter]", id="btn-apply", variant="primary")
                yield Button("Clear", id="btn-clear", variant="warning")
                yield Button("Cancel [Esc]", id="btn-cancel")

    def on_mount(self) -> None:
        """Handle mount event - pre-populate with current filter values."""
        # Set time range if present
        if self._current_filter.time_range:
            # Find closest preset
            current_duration = (
                self._current_filter.time_range.end - self._current_filter.time_range.start
            )
            for idx, (_, delta) in enumerate(TIME_PRESETS):
                if delta and abs(current_duration - delta) < timedelta(minutes=5):
                    self.query_one("#time-select", Select).value = str(idx)
                    break

        # Set severity if present
        if self._current_filter.severity:
            for idx, (_, sev) in enumerate(SEVERITY_OPTIONS):
                if sev == self._current_filter.severity:
                    self.query_one("#severity-select", Select).value = str(idx)
                    break

    def action_cancel(self) -> None:
        """Cancel and close the modal."""
        self.dismiss(None)

    def action_apply(self) -> None:
        """Apply the filter and close."""
        try:
            new_filter = self._build_filter()
            self.dismiss(new_filter)
        except ValueError as e:
            self.notify(str(e), severity="error")

    def _build_filter(self) -> Filter:
        """Build a Filter object from current form values.

        Returns:
            A new Filter object with the configured values.

        Raises:
            ValueError: If any value is invalid.
        """
        # Get time range
        time_select = self.query_one("#time-select", Select)
        time_range = None
        if time_select.value != Select.BLANK:
            time_idx = int(str(time_select.value))
            _, delta = TIME_PRESETS[time_idx]
            if delta:
                # Use local time (all log timestamps are naive local time)
                now = datetime.now()
                time_range = TimeRange(start=now - delta, end=now)

        # Get severity
        severity_select = self.query_one("#severity-select", Select)
        severity = None
        if severity_select.value != Select.BLANK:
            sev_idx = int(str(severity_select.value))
            _, severity = SEVERITY_OPTIONS[sev_idx]

        # Get text search
        text_input = self.query_one("#text-search", Input)
        text_search = text_input.value.strip() if text_input.value.strip() else None

        # Get limit
        limit_input = self.query_one("#limit-input", Input)
        try:
            limit = int(limit_input.value) if limit_input.value else 1000
            if limit < 1:
                raise ValueError("Limit must be at least 1")
            if limit > 10000:
                raise ValueError("Limit must not exceed 10000")
        except ValueError as e:
            if "invalid literal" in str(e):
                raise ValueError("Limit must be a number") from e
            raise

        return Filter(
            time_range=time_range,
            severity=severity,
            text_search=text_search,
            limit=limit,
        )

    def _clear_form(self) -> None:
        """Clear all form fields to defaults."""
        self.query_one("#time-select", Select).value = "0"
        self.query_one("#severity-select", Select).value = "0"
        self.query_one("#text-search", Input).value = ""
        self.query_one("#limit-input", Input).value = "1000"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-cancel":
            self.action_cancel()
        elif event.button.id == "btn-apply":
            self.action_apply()
        elif event.button.id == "btn-clear":
            self._clear_form()
