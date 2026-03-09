"""Functional tests for the AIMBAT Terminal User Interface.

Each test runs the Textual app in headless mode via ``App.run_test()``.
Because ``aimbat._tui.app`` imports ``engine`` at module level, both
``aimbat.db.engine`` and ``aimbat._tui.app.engine`` must be monkeypatched
to the test fixture's database.
"""

import asyncio
from typing import cast

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, select
from textual.widgets import DataTable, Static, TabbedContent, TabPane

import aimbat._tui.app
import aimbat.db
from aimbat._tui.app import AimbatTUI
from aimbat.models import AimbatEvent

_TUI_SIZE = (120, 40)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_engine(monkeypatch: pytest.MonkeyPatch, engine: Engine) -> None:
    """Patch the engine in both the db module and the TUI app module."""
    monkeypatch.setattr(aimbat.db, "engine", engine)
    monkeypatch.setattr(aimbat._tui.app, "engine", engine)


# ===========================================================================
# Startup — empty database
# ===========================================================================


@pytest.mark.slow
class TestTUIEmptyDatabase:
    """TUI smoke tests against a project with no data."""

    def test_starts_without_error(
        self, patched_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """App mounts without raising an exception."""
        _patch_engine(monkeypatch, patched_engine)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause()

        asyncio.run(_run())

    def test_three_tabs_present(
        self, patched_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The three expected tab panes are mounted."""
        _patch_engine(monkeypatch, patched_engine)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause()
                tab_ids = {pane.id for pane in pilot.app.query(TabPane)}
                for expected in (
                    "tab-project",
                    "tab-seismograms",
                    "tab-snapshots",
                ):
                    assert expected in tab_ids

        asyncio.run(_run())

    def test_event_bar_shows_no_data_message(
        self, patched_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Event bar indicates that no data exists when the DB has no events."""
        _patch_engine(monkeypatch, patched_engine)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause()
                bar = pilot.app.query_one("#event-bar", Static)
                assert "No data" in str(bar.render())

        asyncio.run(_run())

    def test_seismogram_table_empty(
        self, patched_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Seismogram table has no rows when the project has no data."""
        _patch_engine(monkeypatch, patched_engine)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause()
                table = pilot.app.query_one("#seismogram-table", DataTable)
                assert table.row_count == 0

        asyncio.run(_run())

    def test_quit_action_exits(
        self, patched_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pressing 'q' exits the application."""
        _patch_engine(monkeypatch, patched_engine)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause()
                await pilot.press("q")

        asyncio.run(_run())


# ===========================================================================
# Startup — loaded database
# ===========================================================================


@pytest.mark.slow
class TestTUIWithData:
    """TUI tests against a project pre-populated with multi-event data."""

    def test_starts_without_error(
        self, loaded_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """App mounts without raising an exception when data is present."""
        _patch_engine(monkeypatch, loaded_engine)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause(delay=0.5)

        asyncio.run(_run())

    def test_seismogram_table_populated(
        self, loaded_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Seismogram table has rows once an event is selected."""
        _patch_engine(monkeypatch, loaded_engine)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                with Session(loaded_engine) as session:
                    event = session.exec(select(AimbatEvent)).first()
                assert event is not None
                app = cast(AimbatTUI, pilot.app)
                app._current_event_id = event.id
                app.refresh_all()
                await pilot.pause(delay=0.5)
                table = pilot.app.query_one("#seismogram-table", DataTable)
                assert table.row_count > 0

        asyncio.run(_run())

    def test_snapshot_table_empty_initially(
        self, loaded_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Snapshot table starts empty before any snapshot is created."""
        _patch_engine(monkeypatch, loaded_engine)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause(delay=0.5)
                table = pilot.app.query_one("#snapshot-table", DataTable)
                assert table.row_count == 0

        asyncio.run(_run())


# ===========================================================================
# Tab navigation
# ===========================================================================


@pytest.mark.slow
class TestTUITabNavigation:
    """Tests for keyboard-driven tab switching."""

    def test_vim_right_advances_tab(
        self, patched_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pressing 'L' switches to the next tab."""
        _patch_engine(monkeypatch, patched_engine)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause()
                tc = pilot.app.query_one(TabbedContent)
                initial_tab = tc.active
                await pilot.press("L")
                await pilot.pause()
                assert tc.active != initial_tab

        asyncio.run(_run())

    def test_vim_left_wraps_or_stays(
        self, patched_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pressing 'H' on the first tab does not crash."""
        _patch_engine(monkeypatch, patched_engine)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause()
                await pilot.press("H")
                await pilot.pause()
                # App still responsive
                tc = pilot.app.query_one(TabbedContent)
                assert tc.active is not None

        asyncio.run(_run())

    def test_full_tab_cycle(
        self, patched_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cycling through all four tabs and back arrives at a known state."""
        _patch_engine(monkeypatch, patched_engine)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause()
                tc = pilot.app.query_one(TabbedContent)
                visited: list[str] = [tc.active]
                for _ in range(2):
                    await pilot.press("L")
                    await pilot.pause()
                    visited.append(tc.active)
                assert len(set(visited)) == 3, (
                    f"Expected 3 distinct tabs, got {visited}"
                )

        asyncio.run(_run())
