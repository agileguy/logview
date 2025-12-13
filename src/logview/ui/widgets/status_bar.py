"""Status bar widget (placeholder)."""

from __future__ import annotations

from textual.widgets import Static


class StatusBar(Static):
    """A status bar showing current context and filter info."""

    def __init__(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        """Initialize the status bar."""
        super().__init__(**kwargs)
        self._context_name = "Mock (testing)"
        self._filter_summary = "No filter"

    def set_context(self, name: str) -> None:
        """Update the displayed context name."""
        self._context_name = name
        self._update_display()

    def set_filter_summary(self, summary: str) -> None:
        """Update the filter summary."""
        self._filter_summary = summary
        self._update_display()

    def _update_display(self) -> None:
        """Update the status bar text."""
        self.update(f"Context: [{self._context_name}]  Filter: [{self._filter_summary}]")
