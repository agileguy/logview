"""Tests for filter presets functionality."""

from __future__ import annotations

import pytest

from logview.config.schema import FilterPreset
from logview.domain.models import Filter
from logview.ui.screens.filter import FilterModal


class TestFilterPresetsDisplay:
    """Tests for preset display in FilterModal."""

    @pytest.mark.asyncio
    async def test_no_presets_no_preset_section(self) -> None:
        """Test that preset section is hidden when no presets."""

        from logview.app import LogViewApp

        app = LogViewApp()
        async with app.run_test() as pilot:
            # Create modal without presets
            modal = FilterModal(Filter())
            app.push_screen(modal)
            await pilot.pause()

            # Preset select should not exist
            preset_selects = modal.query("#preset-select")
            assert len(preset_selects) == 0

    @pytest.mark.asyncio
    async def test_presets_shows_dropdown(self) -> None:
        """Test that preset dropdown shows when presets are provided."""
        from textual.widgets import Select

        from logview.app import LogViewApp

        presets = [
            FilterPreset(name="errors-only", severity="ERROR"),
            FilterPreset(name="last-hour", time_range_minutes=60),
        ]

        app = LogViewApp()
        async with app.run_test() as pilot:
            modal = FilterModal(Filter(), presets=presets)
            app.push_screen(modal)
            await pilot.pause()

            # Preset select should exist
            preset_select = modal.query_one("#preset-select", Select)
            assert preset_select is not None

    @pytest.mark.asyncio
    async def test_save_button_shows_with_callback(self) -> None:
        """Test that Save button shows when save callback is provided."""
        from textual.widgets import Button

        from logview.app import LogViewApp

        app = LogViewApp()
        async with app.run_test() as pilot:
            saved_presets: list[FilterPreset] = []

            def on_save(preset: FilterPreset) -> None:
                saved_presets.append(preset)

            modal = FilterModal(Filter(), on_save_preset=on_save)
            app.push_screen(modal)
            await pilot.pause()

            # Save button should exist
            save_btn = modal.query_one("#btn-save-preset", Button)
            assert save_btn is not None


class TestFilterPresetOperations:
    """Tests for filter preset save/load/delete operations."""

    def test_preset_schema_validation(self) -> None:
        """Test that FilterPreset validates correctly."""
        preset = FilterPreset(
            name="test-preset",
            severity="ERROR",
            time_range_minutes=60,
            text_search="error",
        )
        assert preset.name == "test-preset"
        assert preset.severity == "ERROR"
        assert preset.time_range_minutes == 60
        assert preset.text_search == "error"

    def test_preset_optional_fields(self) -> None:
        """Test that FilterPreset works with minimal fields."""
        preset = FilterPreset(name="minimal")
        assert preset.name == "minimal"
        assert preset.severity is None
        assert preset.time_range_minutes is None
        assert preset.text_search is None

    def test_preset_with_namespace_and_pod(self) -> None:
        """Test preset with GKE-specific fields."""
        preset = FilterPreset(
            name="gke-preset",
            namespace="default",
            pod="api-*",
        )
        assert preset.namespace == "default"
        assert preset.pod == "api-*"
