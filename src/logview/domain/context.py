"""Context management for log sources."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from logview.adapters.base import LogSource


@dataclass
class ContextManager:
    """Manages available log source contexts."""

    sources: dict[str, LogSource]
    active_source_name: str | None = None

    @property
    def active_source(self) -> LogSource | None:
        """Get the currently active log source."""
        if self.active_source_name is None:
            return None
        return self.sources.get(self.active_source_name)

    def set_active(self, name: str) -> None:
        """Set the active log source by name."""
        if name not in self.sources:
            raise ValueError(f"Unknown log source: {name}")
        self.active_source_name = name

    def list_sources(self) -> list[str]:
        """List all available source names."""
        return list(self.sources.keys())

    def register(self, source: LogSource) -> None:
        """Register a new log source."""
        self.sources[source.name] = source
