"""Tests for the context selector modal."""

from __future__ import annotations

import pytest

from logview.app import LogViewApp
from logview.ui.screens.context import ContextModal


class MockSourceForTest:
    """Simple mock source for testing."""

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name


@pytest.fixture
def configured_sources() -> list[MockSourceForTest]:
    """Create mock configured sources for testing."""
    return [
        MockSourceForTest("System Log"),
        MockSourceForTest("GCP Logs"),
    ]


@pytest.fixture
def discovered_sources() -> list[MockSourceForTest]:
    """Create mock discovered sources for testing."""
    return [
        MockSourceForTest("auth.log"),
        MockSourceForTest("kern.log"),
        MockSourceForTest("dpkg.log"),
    ]


class TestContextModal:
    """Tests for ContextModal."""

    @pytest.mark.asyncio
    async def test_modal_opens(
        self, configured_sources: list[MockSourceForTest]
    ) -> None:
        """Test that the context modal opens correctly."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(
                ContextModal(
                    configured_sources=configured_sources,  # type: ignore[arg-type]
                    discovered_sources=[],
                )
            )
            await pilot.pause()

            assert app.screen.__class__.__name__ == "ContextModal"

    @pytest.mark.asyncio
    async def test_modal_has_tree(
        self, configured_sources: list[MockSourceForTest]
    ) -> None:
        """Test that the modal has a tree widget."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(
                ContextModal(
                    configured_sources=configured_sources,  # type: ignore[arg-type]
                    discovered_sources=[],
                )
            )
            await pilot.pause()

            trees = app.screen.query("Tree")
            assert len(list(trees)) == 1

    @pytest.mark.asyncio
    async def test_modal_shows_configured_sources(
        self,
        configured_sources: list[MockSourceForTest],
    ) -> None:
        """Test that the modal shows configured sources organized by type."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(
                ContextModal(
                    configured_sources=configured_sources,  # type: ignore[arg-type]
                    discovered_sources=[],
                )
            )
            await pilot.pause()

            from textual.widgets import Tree

            tree = app.screen.query_one(Tree)
            # Root should have 1 child: "Local Logs (2)" since mock sources have no source_type
            assert len(tree.root.children) == 1
            local_node = tree.root.children[0]
            assert "Local Logs" in str(local_node.label)
            # The Local Logs node should have 2 children
            assert len(local_node.children) == 2

    @pytest.mark.asyncio
    async def test_modal_shows_discovered_sources_in_folder(
        self,
        configured_sources: list[MockSourceForTest],
        discovered_sources: list[MockSourceForTest],
    ) -> None:
        """Test that discovered sources are in a collapsible folder."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(
                ContextModal(
                    configured_sources=configured_sources,  # type: ignore[arg-type]
                    discovered_sources=discovered_sources,  # type: ignore[arg-type]
                )
            )
            await pilot.pause()

            from textual.widgets import Tree

            tree = app.screen.query_one(Tree)
            # Root should have 2 children: "Local Logs (2)" + "Discovered Logs (3)"
            assert len(tree.root.children) == 2

            # The last one should be the discovered folder
            discovered_node = tree.root.children[-1]
            assert "Discovered Logs" in str(discovered_node.label)
            # It should have 3 children (discovered sources)
            assert len(discovered_node.children) == 3

    @pytest.mark.asyncio
    async def test_modal_closes_on_escape(
        self, configured_sources: list[MockSourceForTest]
    ) -> None:
        """Test that pressing Escape closes the modal."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(
                ContextModal(
                    configured_sources=configured_sources,  # type: ignore[arg-type]
                    discovered_sources=[],
                )
            )
            await pilot.pause()

            assert app.screen.__class__.__name__ == "ContextModal"

            await pilot.press("escape")
            await pilot.pause()

            assert app.screen.__class__.__name__ != "ContextModal"

    @pytest.mark.asyncio
    async def test_modal_has_select_button(
        self, configured_sources: list[MockSourceForTest]
    ) -> None:
        """Test that the modal has a select button."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(
                ContextModal(
                    configured_sources=configured_sources,  # type: ignore[arg-type]
                    discovered_sources=[],
                )
            )
            await pilot.pause()

            buttons = app.screen.query("Button")
            select_button = any("Select" in str(b.label) for b in buttons)
            assert select_button

    @pytest.mark.asyncio
    async def test_modal_has_cancel_button(
        self, configured_sources: list[MockSourceForTest]
    ) -> None:
        """Test that the modal has a cancel button."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(
                ContextModal(
                    configured_sources=configured_sources,  # type: ignore[arg-type]
                    discovered_sources=[],
                )
            )
            await pilot.pause()

            buttons = app.screen.query("Button")
            cancel_button = any("Cancel" in str(b.label) for b in buttons)
            assert cancel_button

    @pytest.mark.asyncio
    async def test_modal_stores_sources(
        self,
        configured_sources: list[MockSourceForTest],
        discovered_sources: list[MockSourceForTest],
    ) -> None:
        """Test that the modal stores the sources correctly."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            modal = ContextModal(
                configured_sources=configured_sources,  # type: ignore[arg-type]
                discovered_sources=discovered_sources,  # type: ignore[arg-type]
            )
            app.push_screen(modal)
            await pilot.pause()

            assert modal._configured_sources == configured_sources
            assert modal._discovered_sources == discovered_sources
            assert len(modal._configured_sources) == 2
            assert len(modal._discovered_sources) == 3

    @pytest.mark.asyncio
    async def test_modal_highlights_active_configured_source(
        self, configured_sources: list[MockSourceForTest]
    ) -> None:
        """Test that the active configured source is marked."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            modal = ContextModal(
                configured_sources=configured_sources,  # type: ignore[arg-type]
                discovered_sources=[],
                active_configured_index=1,  # "GCP Logs" is at index 1
            )
            app.push_screen(modal)
            await pilot.pause()
            await pilot.pause()

            from textual.widgets import Tree

            tree = app.screen.query_one(Tree)
            # Navigate: root -> "Local Logs" -> second child (index 1)
            local_logs_node = tree.root.children[0]
            assert "Local Logs" in str(local_logs_node.label)
            # Check that the second source has the active marker
            active_source_node = local_logs_node.children[1]
            assert "●" in str(active_source_node.label)


class TestContextModalSelection:
    """Tests for context selection behavior."""

    @pytest.mark.asyncio
    async def test_modal_returns_none_on_cancel(
        self, configured_sources: list[MockSourceForTest]
    ) -> None:
        """Test that cancelling returns None."""
        app = LogViewApp()
        result = "not_set"

        def capture_result(value: tuple[str, int] | None) -> None:
            nonlocal result
            result = value  # type: ignore[assignment]

        async with app.run_test() as pilot:
            app.push_screen(
                ContextModal(
                    configured_sources=configured_sources,  # type: ignore[arg-type]
                    discovered_sources=[],
                ),
                capture_result,
            )
            await pilot.pause()

            await pilot.press("escape")
            await pilot.pause()

        assert result is None


class TestContextModalEmpty:
    """Tests for context modal with edge cases."""

    @pytest.mark.asyncio
    async def test_modal_handles_empty_sources(self) -> None:
        """Test that the modal handles empty source lists."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(
                ContextModal(
                    configured_sources=[],
                    discovered_sources=[],
                )
            )
            await pilot.pause()

            # Should not crash
            assert app.screen.__class__.__name__ == "ContextModal"

            from textual.widgets import Tree

            tree = app.screen.query_one(Tree)
            # Root should have no children
            assert len(tree.root.children) == 0

    @pytest.mark.asyncio
    async def test_modal_handles_no_active_source(
        self, configured_sources: list[MockSourceForTest]
    ) -> None:
        """Test that the modal handles no active source."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            modal = ContextModal(
                configured_sources=configured_sources,  # type: ignore[arg-type]
                discovered_sources=[],
                active_configured_index=None,
                active_discovered_index=None,
            )
            app.push_screen(modal)
            await pilot.pause()

            # Should not crash
            assert app.screen.__class__.__name__ == "ContextModal"

    @pytest.mark.asyncio
    async def test_discovered_folder_collapsed_by_default(
        self,
        configured_sources: list[MockSourceForTest],
        discovered_sources: list[MockSourceForTest],
    ) -> None:
        """Test that the discovered logs folder is collapsed by default."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(
                ContextModal(
                    configured_sources=configured_sources,  # type: ignore[arg-type]
                    discovered_sources=discovered_sources,  # type: ignore[arg-type]
                )
            )
            await pilot.pause()

            from textual.widgets import Tree

            tree = app.screen.query_one(Tree)
            discovered_node = tree.root.children[-1]
            # Should be collapsed (not expanded)
            assert not discovered_node.is_expanded

    @pytest.mark.asyncio
    async def test_discovered_folder_expands_if_active(
        self,
        configured_sources: list[MockSourceForTest],
        discovered_sources: list[MockSourceForTest],
    ) -> None:
        """Test that the discovered folder expands if active source is in it."""
        app = LogViewApp()
        async with app.run_test() as pilot:
            app.push_screen(
                ContextModal(
                    configured_sources=configured_sources,  # type: ignore[arg-type]
                    discovered_sources=discovered_sources,  # type: ignore[arg-type]
                    active_discovered_index=1,  # "kern.log" is active
                )
            )
            await pilot.pause()

            from textual.widgets import Tree

            tree = app.screen.query_one(Tree)
            discovered_node = tree.root.children[-1]
            # Should be expanded because active source is inside
            assert discovered_node.is_expanded
