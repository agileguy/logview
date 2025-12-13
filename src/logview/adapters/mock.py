"""Mock log source adapter for testing."""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator
from datetime import datetime, timedelta

from logview.domain.models import Filter, FilterField, LogEntry, Severity


class MockLogSource:
    """A mock log source that generates fake log data for testing."""

    SAMPLE_SOURCES = [
        "api-server-abc12",
        "worker-def34",
        "db-proxy-ghi56",
        "auth-service-jkl78",
        "cache-mno90",
    ]

    SAMPLE_MESSAGES = [
        ("Request completed successfully", Severity.INFO),
        ("High latency detected: {latency}ms", Severity.WARN),
        ("Job started: #{job_id}", Severity.INFO),
        ("Connection refused to database", Severity.ERROR),
        ("Health check OK", Severity.INFO),
        ("Processing item {item_id}", Severity.DEBUG),
        ("Request started", Severity.INFO),
        ("Cache miss for key: {key}", Severity.DEBUG),
        ("Authentication failed for user", Severity.WARN),
        ("Memory usage above threshold: {percent}%", Severity.WARN),
        ("Unhandled exception in handler", Severity.ERROR),
        ("Configuration reloaded", Severity.INFO),
        ("Rate limit exceeded", Severity.WARN),
        ("Service started", Severity.INFO),
        ("Graceful shutdown initiated", Severity.INFO),
    ]

    def __init__(self, seed: int | None = None) -> None:
        """Initialize the mock log source.

        Args:
            seed: Optional random seed for reproducible output.
        """
        self._seed = seed
        self._rng = random.Random(seed)

    @property
    def name(self) -> str:
        """Human-readable name for this source."""
        return "Mock (testing)"

    async def fetch(self, log_filter: Filter) -> AsyncIterator[LogEntry]:
        """Generate fake log entries matching the filter.

        Args:
            log_filter: The filter to apply when generating logs.

        Yields:
            Generated LogEntry objects.
        """
        # Reset RNG for reproducibility if seeded
        if self._seed is not None:
            self._rng = random.Random(self._seed)

        count = 0
        now = datetime.now()
        cumulative_offset = 0.0

        while count < log_filter.limit:
            # Each entry is 0.1 to 5.0 seconds after the previous (going backwards)
            cumulative_offset += self._rng.uniform(0.1, 5.0)
            entry = self._generate_entry(now, cumulative_offset)

            if entry.matches_filter(log_filter):
                yield entry
                count += 1

            # Small delay to simulate network latency
            await asyncio.sleep(0.001)

    def validate_filter(self, log_filter: Filter) -> list[str]:
        """Validate a filter. Mock source accepts any valid filter.

        Args:
            log_filter: The filter to validate.

        Returns:
            Empty list (mock source has no special validation).
        """
        return []

    def available_filters(self) -> list[FilterField]:
        """Get available filter fields.

        Returns:
            List of filter fields supported by this source.
        """
        return [
            FilterField(name="severity", label="Severity", options=[s.value for s in Severity]),
            FilterField(name="source", label="Source", options=self.SAMPLE_SOURCES),
        ]

    def _generate_entry(self, base_time: datetime, offset_seconds: float) -> LogEntry:
        """Generate a single log entry.

        Args:
            base_time: The base timestamp to work back from.
            offset_seconds: Seconds to subtract from base_time for timestamp.

        Returns:
            A generated LogEntry.
        """
        # Generate timestamp going backwards from now
        timestamp = base_time - timedelta(seconds=offset_seconds)

        # Pick a random message template and severity
        template, severity = self._rng.choice(self.SAMPLE_MESSAGES)

        # Fill in template variables
        message = template.format(
            latency=self._rng.randint(100, 5000),
            job_id=self._rng.randint(1000, 9999),
            item_id=self._rng.randint(1, 100),
            key=f"user:{self._rng.randint(1, 1000)}",
            percent=self._rng.randint(80, 99),
        )

        source = self._rng.choice(self.SAMPLE_SOURCES)

        metadata = {
            "cluster": "mock-cluster",
            "namespace": self._rng.choice(["default", "production", "staging"]),
            "pod": f"{source}-{self._rng.randint(10000, 99999)}",
        }

        return LogEntry(
            timestamp=timestamp,
            severity=severity,
            message=message,
            source=source,
            metadata=metadata,
            raw="",
        )
