"""Integration tests for the mock adapter."""

from __future__ import annotations

import pytest

from logview.adapters.mock import MockLogSource
from logview.domain.models import Filter, Severity


class TestMockLogSource:
    """Integration tests for MockLogSource."""

    @pytest.mark.asyncio
    async def test_fetch_returns_entries(self, mock_source: MockLogSource) -> None:
        """Test that fetch returns log entries."""
        log_filter = Filter(limit=10)
        entries = []

        async for entry in mock_source.fetch(log_filter):
            entries.append(entry)

        assert len(entries) == 10
        for entry in entries:
            assert entry.timestamp is not None
            assert entry.severity is not None
            assert entry.message is not None
            assert entry.source is not None

    @pytest.mark.asyncio
    async def test_fetch_respects_limit(self, mock_source: MockLogSource) -> None:
        """Test that fetch respects the limit parameter."""
        for limit in [1, 5, 50, 100]:
            log_filter = Filter(limit=limit)
            count = 0
            async for _ in mock_source.fetch(log_filter):
                count += 1
            assert count == limit

    @pytest.mark.asyncio
    async def test_fetch_is_reproducible_with_seed(self) -> None:
        """Test that seeded sources produce reproducible output."""
        source1 = MockLogSource(seed=42)
        source2 = MockLogSource(seed=42)

        log_filter = Filter(limit=10)

        entries1 = [e async for e in source1.fetch(log_filter)]
        entries2 = [e async for e in source2.fetch(log_filter)]

        assert len(entries1) == len(entries2)
        for e1, e2 in zip(entries1, entries2, strict=True):
            assert e1.message == e2.message
            assert e1.severity == e2.severity
            assert e1.source == e2.source

    @pytest.mark.asyncio
    async def test_fetch_different_seeds_differ(self) -> None:
        """Test that different seeds produce different output."""
        source1 = MockLogSource(seed=42)
        source2 = MockLogSource(seed=123)

        log_filter = Filter(limit=10)

        entries1 = [e async for e in source1.fetch(log_filter)]
        entries2 = [e async for e in source2.fetch(log_filter)]

        # At least some entries should differ
        differences = sum(
            1 for e1, e2 in zip(entries1, entries2, strict=True) if e1.message != e2.message
        )
        assert differences > 0

    def test_name_property(self, mock_source: MockLogSource) -> None:
        """Test the name property."""
        assert mock_source.name == "Mock (testing)"

    def test_validate_filter_always_valid(self, mock_source: MockLogSource) -> None:
        """Test that mock source accepts any filter."""
        log_filter = Filter(
            severity=Severity.ERROR,
            text_search="test",
            limit=100,
        )
        errors = mock_source.validate_filter(log_filter)
        assert errors == []

    def test_available_filters(self, mock_source: MockLogSource) -> None:
        """Test available filters are returned."""
        filters = mock_source.available_filters()
        assert len(filters) > 0

        filter_names = [f.name for f in filters]
        assert "severity" in filter_names
        assert "source" in filter_names

    @pytest.mark.asyncio
    async def test_entries_have_valid_metadata(
        self, mock_source: MockLogSource
    ) -> None:
        """Test that generated entries have valid metadata."""
        log_filter = Filter(limit=10)

        async for entry in mock_source.fetch(log_filter):
            assert "cluster" in entry.metadata
            assert "namespace" in entry.metadata
            assert "pod" in entry.metadata
            assert entry.metadata["namespace"] in ["default", "production", "staging"]

    @pytest.mark.asyncio
    async def test_timestamps_are_descending(self, mock_source: MockLogSource) -> None:
        """Test that timestamps are in descending order (most recent first)."""
        log_filter = Filter(limit=20)
        entries = [e async for e in mock_source.fetch(log_filter)]

        for i in range(len(entries) - 1):
            assert entries[i].timestamp >= entries[i + 1].timestamp


class TestMockLogSourceFiltering:
    """Tests for filter application in MockLogSource."""

    @pytest.mark.asyncio
    async def test_severity_filter(self) -> None:
        """Test filtering by severity."""
        source = MockLogSource(seed=42)
        log_filter = Filter(severity=Severity.ERROR, limit=50)

        entries = [e async for e in source.fetch(log_filter)]

        # All returned entries should be ERROR or higher
        for entry in entries:
            assert entry.severity >= Severity.ERROR

    @pytest.mark.asyncio
    async def test_text_search_filter(self) -> None:
        """Test filtering by text search."""
        source = MockLogSource(seed=42)

        # Find a message substring to search for
        search_term = "Request"  # Common in mock messages
        log_filter = Filter(text_search=search_term, limit=50)
        filtered_entries = [e async for e in source.fetch(log_filter)]

        # All returned entries should contain the search term
        for entry in filtered_entries:
            assert search_term.lower() in entry.message.lower()
