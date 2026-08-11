"""Functional tests for the AIMBAT Terminal User Interface.

Each test runs the Textual app in headless mode via ``App.run_test()``.
All TUI sub-modules that import ``engine`` at module level must be
monkeypatched to the test fixture's database:

- ``aimbat.db.engine`` — the canonical engine attribute
- ``aimbat._tui.app.engine`` — top-level import in the app module
- ``aimbat._tui._panels.engine`` — top-level import in the panels module
- ``aimbat._tui.modals.engine`` — top-level import in the modals module
- ``aimbat._tui._widgets.engine`` — top-level import in the widgets module
"""

import asyncio
import uuid
from typing import cast

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, select
from textual.widgets import DataTable, Static, TabbedContent, TabPane

import aimbat._tui._panels
import aimbat._tui._widgets
import aimbat._tui.app
import aimbat._tui.modals
import aimbat.db
from aimbat._tui.app import AimbatTUI
from aimbat._tui.modals import SnapshotDetailsModal
from aimbat.core import BoundICCS, create_snapshot
from aimbat.core import create_iccs_instance as _real_create_iccs_instance
from aimbat.models import AimbatEvent, AimbatSeismogram

_TUI_SIZE = (120, 40)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_engine(monkeypatch: pytest.MonkeyPatch, engine: Engine) -> None:
    """Patch the engine in all TUI modules that import it at module level."""
    monkeypatch.setattr(aimbat.db, "engine", engine)
    monkeypatch.setattr(aimbat._tui.app, "engine", engine)
    monkeypatch.setattr(aimbat._tui._panels, "engine", engine)
    monkeypatch.setattr(aimbat._tui.modals, "engine", engine)
    monkeypatch.setattr(aimbat._tui._widgets, "engine", engine)


async def _wait_for_iccs_worker(app: AimbatTUI) -> None:
    """Wait for the background ICCS-creation worker to actually finish.

    A fixed `pilot.pause(delay=...)` races against the worker thread, which
    on a successful retry does real seismogram I/O and can outlast a short
    sleep on slower CI runners (observed flaking on Windows). Waiting on the
    worker itself is deterministic regardless of how long it takes.
    """
    await app.workers.wait_for_complete()


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
# Startup — stale schema
# ===========================================================================


@pytest.mark.slow
class TestTUISchemaStalenessToast:
    """Tests for the startup toast warning about an out-of-date schema.

    `first_connect`-based `SchemaStaleWarning` (see `aimbat.db`) prints to
    stderr, which is invisible once Textual owns the terminal - this is the
    TUI-native equivalent, checked separately from the CLI-facing warning.
    """

    def test_toast_shown_for_legacy_unstamped_database(
        self, patched_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A pre-Alembic database (no `alembic_version` table) triggers a toast.

        Toast widgets aren't mounted as queryable DOM nodes in headless test
        mode, so `app._notifications` (the underlying collection `notify()`
        populates) is checked directly rather than querying `Toast` widgets.
        """
        _patch_engine(monkeypatch, patched_engine)
        with patched_engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE alembic_version")

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause()
                notifications = list(pilot.app._notifications)
                assert any(
                    "predates AIMBAT's schema versioning" in n.message
                    for n in notifications
                )
                assert all(n.severity == "warning" for n in notifications)

        asyncio.run(_run())

    def test_no_toast_when_up_to_date(
        self, patched_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A freshly created (and therefore immediately-stamped) project shows no toast."""
        _patch_engine(monkeypatch, patched_engine)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause()
                assert list(pilot.app._notifications) == []

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


# ===========================================================================
# ICCS staleness — one-shot retry after a failed creation
# ===========================================================================


@pytest.mark.slow
class TestICCSStalenessRetry:
    """A failed ICCS creation gets exactly one automatic retry, not a retry storm.

    See `AimbatTUI._check_iccs_staleness` / `_create_iccs`: a fresh (non-retry)
    failure sets `_iccs_retry_pending`, which the staleness poller consumes at
    most once before falling silent again until `event.last_modified` changes.
    """

    def test_retries_once_then_stops_on_persistent_failure(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Repeated polls after a persistent failure do not retry forever."""
        _patch_engine(monkeypatch, loaded_engine_from_file)

        call_count = 0

        def _always_fails(session: Session, event: AimbatEvent) -> BoundICCS:
            nonlocal call_count
            call_count += 1
            raise ValueError("simulated persistent failure")

        monkeypatch.setattr(aimbat._tui.app, "create_iccs_instance", _always_fails)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                with Session(loaded_engine_from_file) as session:
                    event = session.exec(select(AimbatEvent)).first()
                assert event is not None
                app = cast(AimbatTUI, pilot.app)
                app._current_event_id = event.id
                # Mirror what `_check_iccs_staleness` records before a fresh
                # attempt, so later polls see an unchanged `last_modified`.
                app._iccs_last_modified_seen = event.last_modified

                app._create_iccs()
                await _wait_for_iccs_worker(app)
                assert call_count == 1
                assert app._iccs_retry_pending is True
                assert app._bound_iccs is None

                # The poller consumes the pending retry exactly once.
                app._check_iccs_staleness()
                await _wait_for_iccs_worker(app)
                assert call_count == 2
                assert app._iccs_retry_pending is False
                assert app._bound_iccs is None

                # Further polls must not retry again — no infinite loop.
                app._check_iccs_staleness()
                await pilot.pause(delay=0.5)
                assert call_count == 2

        asyncio.run(_run())

    def test_retry_can_succeed_after_one_failure(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The one-shot retry can recover and bind a working ICCS instance."""
        _patch_engine(monkeypatch, loaded_engine_from_file)

        attempts = 0

        def _fail_once_then_succeed(session: Session, event: AimbatEvent) -> BoundICCS:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise ValueError("simulated transient failure")
            return _real_create_iccs_instance(session, event)

        monkeypatch.setattr(
            aimbat._tui.app, "create_iccs_instance", _fail_once_then_succeed
        )

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                with Session(loaded_engine_from_file) as session:
                    event = session.exec(select(AimbatEvent)).first()
                assert event is not None
                app = cast(AimbatTUI, pilot.app)
                app._current_event_id = event.id
                app._iccs_last_modified_seen = event.last_modified

                app._create_iccs()
                await _wait_for_iccs_worker(app)
                assert attempts == 1
                assert app._iccs_retry_pending is True
                assert app._bound_iccs is None

                app._check_iccs_staleness()
                await _wait_for_iccs_worker(app)
                assert attempts == 2
                assert app._iccs_retry_pending is False
                assert app._bound_iccs is not None

        asyncio.run(_run())


# ===========================================================================
# Row-action menu wiring — panel -> app message bubbling
# ===========================================================================


@pytest.mark.slow
class TestRowActionMenuWiring:
    """The row-select -> action-menu -> message -> handler path for each panel.

    `ProjectPanel`, `SeismogramPanel`, and `SnapshotPanel` each post a message
    (`RowActionChosen`/`ActionChosen`) that `AimbatTUI` handles via `@on`
    (see `_panels.py` and `app.py`). These tests drive real key presses
    through the actual `ActionMenuModal`/`SnapshotActionMenuModal` rather than
    constructing the messages directly, so a wrong message class, tab
    argument, or handler mismatch would actually fail here.
    """

    def test_project_event_action_toggles_completed(
        self, loaded_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Choosing 'Toggle completed' from an event's action menu flips its flag."""
        _patch_engine(monkeypatch, loaded_engine)

        async def _run() -> uuid.UUID:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause(delay=0.5)
                table = pilot.app.query_one("#project-event-table", DataTable)
                table.focus()
                await pilot.pause()
                row_id = table.ordered_rows[0].key.value
                assert row_id is not None
                await pilot.press("enter")  # open the row's action menu
                await pilot.pause()
                await pilot.press("j")  # "Select event" -> "Toggle completed"
                await pilot.press("enter")
                await pilot.pause(delay=0.3)
                return uuid.UUID(row_id)

        event_id = asyncio.run(_run())

        with Session(loaded_engine) as session:
            event = session.get(AimbatEvent, event_id)
            assert event is not None
            assert event.parameters.completed is True

    def test_seismogram_action_toggles_select(
        self, loaded_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Choosing 'Toggle select' from a seismogram's action menu flips its flag."""
        _patch_engine(monkeypatch, loaded_engine)

        with Session(loaded_engine) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            event_id = event.id

        async def _run() -> uuid.UUID:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause(delay=0.5)
                app = cast(AimbatTUI, pilot.app)
                app._current_event_id = event_id
                app.refresh_all()
                await pilot.pause(delay=0.5)
                await pilot.press("L")  # Project -> Live data
                await pilot.pause()
                table = pilot.app.query_one("#seismogram-table", DataTable)
                table.focus()
                await pilot.pause()
                row_id = table.ordered_rows[0].key.value
                assert row_id is not None
                await pilot.press("enter")  # open the row's action menu
                await pilot.pause()
                await pilot.press("enter")  # first action: "Toggle select"
                await pilot.pause(delay=0.3)
                return uuid.UUID(row_id)

        seismogram_id = asyncio.run(_run())

        with Session(loaded_engine) as session:
            seismogram = session.get(AimbatSeismogram, seismogram_id)
            assert seismogram is not None
            assert seismogram.parameters.select is False

    def test_snapshot_action_shows_details(
        self, loaded_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Choosing 'Show details' from a snapshot's action menu opens the details modal."""
        _patch_engine(monkeypatch, loaded_engine)

        with Session(loaded_engine) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            event_id = event.id
            create_snapshot(session, event, "wiring test snapshot")

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause(delay=0.5)
                app = cast(AimbatTUI, pilot.app)
                app._current_event_id = event_id
                app.refresh_all()
                await pilot.pause(delay=0.5)
                await pilot.press("L")  # Project -> Live data
                await pilot.press("L")  # Live data -> Snapshots
                await pilot.pause()
                table = pilot.app.query_one("#snapshot-table", DataTable)
                table.focus()
                await pilot.pause()
                await pilot.press("enter")  # open the row's action menu
                await pilot.pause()
                await pilot.press("enter")  # first action: "Show details"
                await pilot.pause(delay=0.3)
                assert isinstance(pilot.app.screen, SnapshotDetailsModal)

        asyncio.run(_run())
