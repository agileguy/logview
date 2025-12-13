"""Log source adapters."""

from logview.adapters.base import LogSource
from logview.adapters.mock import MockLogSource

__all__ = ["LogSource", "MockLogSource"]
