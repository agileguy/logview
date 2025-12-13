"""Integration tests for syslog adapter (placeholder)."""

from __future__ import annotations

import pytest

from logview.adapters.syslog import SyslogSource


class TestSyslogSource:
    """Tests for SyslogSource (Phase 2 placeholder)."""

    def test_name_property(self) -> None:
        """Test the name property."""
        source = SyslogSource()
        assert "Syslog" in source.name
        assert "/var/log/syslog" in source.name

    def test_custom_path(self) -> None:
        """Test custom syslog path."""
        source = SyslogSource(path="/var/log/messages")
        assert "/var/log/messages" in source.name

    def test_available_filters(self) -> None:
        """Test available filters are returned."""
        source = SyslogSource()
        filters = source.available_filters()
        assert len(filters) > 0

        filter_names = [f.name for f in filters]
        assert "severity" in filter_names
        assert "process" in filter_names

    @pytest.mark.asyncio
    async def test_fetch_not_implemented(self) -> None:
        """Test that fetch raises NotImplementedError."""
        source = SyslogSource()
        from logview.domain.models import Filter

        with pytest.raises(NotImplementedError, match="Phase 2"):
            async for _ in source.fetch(Filter()):
                pass
