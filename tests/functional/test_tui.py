"""Functional tests for the AIMBAT Terminal User Interface.

Each test runs the Textual app in headless mode via ``App.run_test()``.
All TUI sub-modules that import ``engine`` at module level must be
monkeypatched to the test fixture's database:

- ``aimbat.db.engine`` — the canonical engine attribute
- ``aimbat._tui.app.engine`` — top-level import in the app module
- ``aimbat._tui._iccs_lifecycle.engine`` — top-level import in the ICCS
  lifecycle module
- ``aimbat._tui._panels.engine`` — top-level import in the panels module
- ``aimbat._tui.modals.engine`` — top-level import in the modals module
- ``aimbat._tui._widgets.engine`` — top-level import in the widgets module
"""

import asyncio
import threading
import uuid
from collections.abc import Callable, Generator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import cast

import pytest
from pandas import Timedelta, Timestamp
from sqlalchemy import Engine
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, select
from textual.binding import Binding
from textual.widgets import DataTable, Static, TabbedContent, TabPane
from textual.worker import WorkerCancelled
from textual_fspicker import FileOpen

import aimbat._tui._iccs_lifecycle
import aimbat._tui._panels
import aimbat._tui._tools
import aimbat._tui._widgets
import aimbat._tui.app
import aimbat._tui.modals
import aimbat.db
from aimbat._tui._panels import ProjectPanel, SeismogramPanel, SnapshotPanel
from aimbat._tui.app import AimbatTUI
from aimbat._tui.modals import (
    ActionMenuModal,
    AlignModal,
    InteractiveToolsModal,
    ParametersModal,
    PhaseSelectModal,
    SchemaStaleModal,
    SnapshotDetailsModal,
    ToolLaunchResult,
)
from aimbat.actions import prepare_iccs
from aimbat.core import (
    BoundICCS,
    IccsLifecycle,
    RunSummary,
    create_snapshot,
    current_instance_digest,
    default_phase_parameters,
    get_current_revision,
    store_picks,
)
from aimbat.core import create_iccs_instance as _real_create_iccs_instance
from aimbat.io import DataType, SourcePick
from aimbat.models import (
    AimbatEvent,
    AimbatPhase,
    AimbatSeismogram,
    AimbatSnapshot,
)
from aimbat.types import SeismogramParameter

_TUI_SIZE = (120, 40)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_engine(monkeypatch: pytest.MonkeyPatch, engine: Engine) -> None:
    """Patch the engine in all TUI modules that import it at module level."""
    monkeypatch.setattr(aimbat.db, "engine", engine)
    monkeypatch.setattr(aimbat._tui.app, "engine", engine)
    monkeypatch.setattr(aimbat._tui._iccs_lifecycle, "engine", engine)
    monkeypatch.setattr(aimbat._tui._panels, "engine", engine)
    monkeypatch.setattr(aimbat._tui.modals, "engine", engine)
    monkeypatch.setattr(aimbat._tui._widgets, "engine", engine)


async def _wait_for_iccs_worker(app: AimbatTUI) -> None:
    """Wait until no worker is running, including workers started meanwhile.

    A fixed `pilot.pause(delay=...)` races against the worker thread, which
    on a successful retry does real seismogram I/O and can outlast a short
    sleep on slower CI runners (observed flaking on Windows). Waiting on the
    worker itself is deterministic regardless of how long it takes.

    `wait_for_complete()` waits only for the workers present when it is
    called. A finished build can start another (`_assign_iccs` discards an
    instance for a phase that is no longer current and builds again), so
    wait until none is left.
    """
    while any(not worker.is_finished for worker in app.workers):
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
        """Event bar indicates that no data exist when the DB has no events."""
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
class TestTUISchemaStalenessModal:
    """Tests for the blocking modal shown on startup for an out-of-date schema.

    A stale schema used to only produce a toast (see git history), which let
    the TUI proceed into panels that could query columns the live schema
    doesn't have - crashing with a raw `sqlalchemy.exc.OperationalError` from
    whichever panel happened to touch the drifted table first, sometimes
    before the toast even had a chance to render. `on_mount` now blocks
    entirely on a modal instead, mirroring `NoProjectModal` - see
    `aimbat.db`'s module docstring for the full reasoning.
    """

    def test_modal_shown_for_unstamped_database(
        self, patched_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A database with no `alembic_version` table blocks on a modal that
        offers no upgrade.
        """
        _patch_engine(monkeypatch, patched_engine)
        with patched_engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE alembic_version")

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause()
                modal = pilot.app.screen
                assert isinstance(modal, SchemaStaleModal)
                assert "earlier development version of AIMBAT" in modal._message
                assert not modal._upgradeable

        asyncio.run(_run())

    def test_no_modal_when_up_to_date(
        self, patched_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A freshly created (and therefore immediately-stamped) project shows no modal."""
        _patch_engine(monkeypatch, patched_engine)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause()
                assert not isinstance(pilot.app.screen, SchemaStaleModal)

        asyncio.run(_run())

    def test_upgrade_action_upgrades_and_proceeds(
        self, patched_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pressing 'u' runs the upgrade and enters the main UI.

        A stale database that can be upgraded cannot be built while AIMBAT
        has only a baseline revision, so the staleness check is stubbed.
        """
        from aimbat.core._migrations import SchemaStaleWarning

        _patch_engine(monkeypatch, patched_engine)
        monkeypatch.setattr(
            aimbat._tui.app,
            "_build_staleness_warning",
            lambda _: SchemaStaleWarning("stale", "old", "new", upgradeable=True),
        )
        upgraded: list[Engine] = []
        monkeypatch.setattr(aimbat._tui.app, "upgrade_project", upgraded.append)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause()
                assert isinstance(pilot.app.screen, SchemaStaleModal)

                await pilot.press("u")
                await pilot.pause()

                assert not isinstance(pilot.app.screen, SchemaStaleModal)

        asyncio.run(_run())
        assert upgraded == [patched_engine]

    def test_upgrade_action_is_inert_when_not_upgradeable(
        self, patched_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pressing 'u' on a database that cannot be upgraded leaves the modal up."""
        _patch_engine(monkeypatch, patched_engine)
        with patched_engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE alembic_version")

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause()
                await pilot.press("u")
                await pilot.pause()
                assert isinstance(pilot.app.screen, SchemaStaleModal)

        asyncio.run(_run())
        assert get_current_revision(patched_engine) is None

    def test_quit_action_declines_upgrade_and_exits(
        self, patched_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pressing 'q' leaves the database untouched and exits the app."""
        _patch_engine(monkeypatch, patched_engine)
        with patched_engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE alembic_version")

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause()
                await pilot.press("q")

        asyncio.run(_run())
        assert get_current_revision(patched_engine) is None

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
        """App mounts without raising an exception when data are present."""
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


class TestSeismogramPlotDebounce:
    """Regression test for tui L6: fast row-highlight scrolling coalesces.

    `SeismogramPanel` used to re-render `SeismogramPlotWidget` on every
    `RowHighlighted` event, so fast arrow-key scrolling through a large
    seismogram list replotted on every keystroke. It now debounces behind a
    0.1s cancel-and-reschedule `Timer`.
    """

    def test_rapid_row_highlights_coalesce_into_one_render(
        self, loaded_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Three quick highlights produce one render, not three."""
        _patch_engine(monkeypatch, loaded_engine)

        calls: list[str | None] = []
        original = aimbat._tui._panels.SeismogramPanel._update_seismogram_plot

        def _tracking_update(
            self: aimbat._tui._panels.SeismogramPanel, item_id: str | None
        ) -> None:
            calls.append(item_id)
            original(self, item_id)

        monkeypatch.setattr(
            aimbat._tui._panels.SeismogramPanel,
            "_update_seismogram_plot",
            _tracking_update,
        )

        with Session(loaded_engine) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            event_id = event.id

        async def _run() -> None:
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
                assert table.row_count >= 3, "need several rows to scroll through"
                calls.clear()  # drop the settle-triggered call from focusing

                # Move the cursor three times back-to-back with no `await` in
                # between, so all three `RowHighlighted` handlers run before
                # any real time passes - unlike `pilot.press()`, whose own
                # per-call overhead in headless test mode can itself exceed
                # the 0.1s debounce window and defeat the point of this test.
                table.move_cursor(row=1)
                table.move_cursor(row=2)
                table.move_cursor(row=0)
                # No "nothing rendered yet" assertion: a slow runner can exceed
                # the 0.1s debounce window before the first pause returns.
                await pilot.pause(delay=0.2)  # past the 0.1s debounce window
                assert len(calls) == 1, (
                    "three quick highlights should coalesce into one render"
                )

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
    failure sets `IccsLifecycle.retry_pending`, which the staleness poller
    consumes at most once before falling silent again until the event's
    instance digest changes.
    """

    def test_retries_once_then_stops_on_persistent_failure(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Repeated polls after a persistent failure do not retry forever."""
        _patch_engine(monkeypatch, loaded_engine_from_file)

        call_count = 0

        def _always_fails(phase_id: uuid.UUID) -> BoundICCS:
            nonlocal call_count
            call_count += 1
            raise ValueError("simulated persistent failure")

        monkeypatch.setattr(aimbat._tui._iccs_lifecycle, "prepare_iccs", _always_fails)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                # `on_mount` already kicked off its own `_create_iccs()` for
                # this event-bearing fixture, with no event selected yet. Drain
                # it first: otherwise it can still be in flight below, and the
                # `IccsLifecycle.start_creating` guard silently skips the call this test
                # actually wants to observe.
                await _wait_for_iccs_worker(app)

                with Session(loaded_engine_from_file) as session:
                    event = session.exec(select(AimbatEvent)).first()
                assert event is not None
                app._current_event_id = event.id
                # Mirror what `_check_iccs_staleness` records before a fresh
                # attempt, so later polls see an unchanged instance digest.
                with Session(loaded_engine_from_file) as session:
                    phase_id = session.get_one(AimbatEvent, event.id).phases[0].id
                    app._iccs_lifecycle.note_checked(
                        current_instance_digest(session, phase_id)
                    )

                app._create_iccs()
                await _wait_for_iccs_worker(app)
                assert call_count == 1
                assert app._iccs_lifecycle.retry_pending is True
                assert app._iccs_lifecycle.bound is None

                # The poller consumes the pending retry exactly once.
                app._check_iccs_staleness()
                await _wait_for_iccs_worker(app)
                assert call_count == 2
                assert app._iccs_lifecycle.retry_pending is False
                assert app._iccs_lifecycle.bound is None

                # Further polls must not retry again — no infinite loop.
                app._check_iccs_staleness()
                await pilot.pause(delay=0.5)
                assert call_count == 2

        asyncio.run(_run())

    def test_not_ready_phase_warns(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A phase with blocking readiness items is refused with a warning."""
        _patch_engine(monkeypatch, loaded_engine_from_file)
        with Session(loaded_engine_from_file) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            event_id = event.id
            row = event.phases[0].seismogram_parameters[0]
            store_picks(
                session,
                [SourcePick(row.initial_pick + Timedelta(seconds=5), "extra")],
                source_name="extra.json",
                source_type=DataType.SAC,
                source_seismogram=row.seismogram,
            )
            session.commit()

        notifications: list[tuple[str, str]] = []

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)
                monkeypatch.setattr(
                    app,
                    "notify",
                    lambda message, *, severity="information", **kwargs: (
                        notifications.append((message, severity))
                    ),
                )
                app._current_event_id = event_id

                app._create_iccs()
                await _wait_for_iccs_worker(app)
                assert app._iccs_lifecycle.bound is None

        asyncio.run(_run())

        assert len(notifications) == 1
        message, severity = notifications[0]
        assert "not ready for processing" in message
        assert severity == "warning"

    def test_retry_can_succeed_after_one_failure(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The one-shot retry can recover and bind a working ICCS instance."""
        _patch_engine(monkeypatch, loaded_engine_from_file)

        attempts = 0

        def _fail_once_then_succeed(phase_id: uuid.UUID) -> BoundICCS:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise ValueError("simulated transient failure")
            return prepare_iccs(phase_id)

        monkeypatch.setattr(
            aimbat._tui._iccs_lifecycle, "prepare_iccs", _fail_once_then_succeed
        )

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                # See the equivalent comment in
                # test_retries_once_then_stops_on_persistent_failure: drain
                # `on_mount`'s own startup `_create_iccs()` call first, or it
                # can still be in flight and make the call below a silent
                # no-op via the `IccsLifecycle.start_creating` guard.
                await _wait_for_iccs_worker(app)

                with Session(loaded_engine_from_file) as session:
                    event = session.exec(select(AimbatEvent)).first()
                assert event is not None
                app._current_event_id = event.id
                with Session(loaded_engine_from_file) as session:
                    phase_id = session.get_one(AimbatEvent, event.id).phases[0].id
                    app._iccs_lifecycle.note_checked(
                        current_instance_digest(session, phase_id)
                    )

                app._create_iccs()
                await _wait_for_iccs_worker(app)
                assert attempts == 1
                assert app._iccs_lifecycle.retry_pending is True
                assert app._iccs_lifecycle.bound is None

                app._check_iccs_staleness()
                await _wait_for_iccs_worker(app)
                assert attempts == 2
                assert app._iccs_lifecycle.retry_pending is False
                assert app._iccs_lifecycle.bound is not None

        asyncio.run(_run())

    def test_create_iccs_does_not_get_stuck_on_note_checked_failure(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unexpected error recording `note_checked` must not wedge creation.

        Regression test: `_create_iccs` calls `IccsLifecycle.note_checked`
        (a second, independent event lookup) purely as bookkeeping before
        starting the worker. If that raises something other than
        `NoResultFound`/`RuntimeError` (e.g. a transient DB error), the
        worker must still run — it alone resets the `start_creating()` guard
        on failure, so skipping it would leave ICCS creation permanently
        disabled for the rest of the session.
        """
        _patch_engine(monkeypatch, loaded_engine_from_file)

        class _SimulatedError(Exception):
            pass

        def _always_raises(self: IccsLifecycle, instance_digest: object) -> None:
            raise _SimulatedError("simulated failure recording note_checked")

        monkeypatch.setattr(IccsLifecycle, "note_checked", _always_raises)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)

                with Session(loaded_engine_from_file) as session:
                    event = session.exec(select(AimbatEvent)).first()
                assert event is not None
                app._current_event_id = event.id

                app._create_iccs()
                await _wait_for_iccs_worker(app)

                assert app._iccs_lifecycle._creating is False

                # A further call must not be silently skipped as "already
                # in progress" — the guard must have been released.
                app._create_iccs()
                await _wait_for_iccs_worker(app)
                assert app._iccs_lifecycle._creating is False

        asyncio.run(_run())


@pytest.mark.slow
class TestICCSEmptyEvent:
    """Selecting an event with no seismograms must not crash the TUI.

    Regression test: `create_iccs_instance` cached a half-built instance
    before the stats write that raises for a seismogram-less event, so the
    one-shot retry handed that broken instance to the panels, where
    `cc_stats` blew up with `ValueError: Cannot create stack`.
    """

    def test_select_empty_event_does_not_crash(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, loaded_engine_from_file)

        with Session(loaded_engine_from_file) as session:
            empty = AimbatEvent(
                time=Timestamp("2011-03-11T05:46:24", tz="UTC"),
                latitude=38.30,
                longitude=142.37,
                depth=29.0,
            )
            session.add(empty)
            session.commit()
            empty_id = empty.id

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)

                app._select_event(str(empty_id))
                await _wait_for_iccs_worker(app)

                assert app._iccs_lifecycle.bound is None
                assert app._iccs_lifecycle.retry_pending is False

                # The staleness poller must not resurrect a broken instance
                # or start a retry storm.
                app._check_iccs_staleness()
                await _wait_for_iccs_worker(app)
                app._check_iccs_staleness()
                await pilot.pause(delay=0.3)

                assert app._iccs_lifecycle.bound is None
                assert app.is_running
                bar = app.query_one("#event-bar", Static)
                assert "no ICCS" in str(bar.render())

        asyncio.run(_run())


@pytest.mark.slow
class TestStalenessUIRefresh:
    """An external non-stack parameter change repaints the panels without
    rebuilding the ICCS instance. See `_IccsLifecycleMixin._check_iccs_staleness`.
    """

    def test_mccc_param_change_refreshes_ui_without_rebuilding_iccs(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, loaded_engine_from_file)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)

                with Session(loaded_engine_from_file) as session:
                    event = session.exec(select(AimbatEvent)).first()
                assert event is not None
                app._current_event_id = event.id
                app._create_iccs()
                await _wait_for_iccs_worker(app)
                bound_before = app._iccs_lifecycle.bound
                assert bound_before is not None

                refreshes: list[str] = []
                monkeypatch.setattr(
                    AimbatTUI, "refresh_all", lambda self: refreshes.append("r")
                )
                rebuilds: list[str] = []
                monkeypatch.setattr(
                    AimbatTUI,
                    "_create_iccs",
                    lambda self, *, is_retry=False: rebuilds.append("c"),
                )

                # Another process bumps an MCCC-only parameter.
                with Session(loaded_engine_from_file) as session:
                    ev = session.get(AimbatEvent, event.id)
                    assert ev is not None
                    ev.phases[0].parameters.mccc_damp = (
                        ev.phases[0].parameters.mccc_damp + 0.5
                    )
                    session.add(ev.phases[0].parameters)
                    session.commit()

                app._check_iccs_staleness()
                await pilot.pause()

                assert refreshes == ["r"]
                assert rebuilds == []
                assert app._iccs_lifecycle.bound is bound_before

        asyncio.run(_run())


class TestIccsAssignmentRace:
    """A worker completing for an event that is no longer current is discarded.

    See `_IccsLifecycleMixin._assign_iccs`: if the selected event changes
    (e.g. the bound event was deleted and a different one selected) while a
    `_worker_create_iccs` call is still in flight, its result must not be
    bound as if it were current — otherwise the app could end up "ready"
    with an ICCS instance for the wrong (or deleted) event.
    """

    def test_stale_worker_result_is_discarded_and_current_event_retried(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A stale `_assign_iccs` call is dropped and the current event is (re)built."""
        _patch_engine(monkeypatch, loaded_engine_from_file)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)

                with Session(loaded_engine_from_file) as session:
                    events = session.exec(select(AimbatEvent)).all()
                assert len(events) >= 2
                stale_event, current_event = events[0], events[1]

                with Session(loaded_engine_from_file) as session:
                    stale_event_reloaded = session.get(AimbatEvent, stale_event.id)
                    assert stale_event_reloaded is not None
                    stale_bound = _real_create_iccs_instance(
                        session, stale_event_reloaded.phases[0].id
                    )

                # Simulate the user having switched to a different event
                # while `stale_bound` was still being built in the
                # background for `stale_event`.
                app._current_event_id = current_event.id

                app._assign_iccs(stale_bound)
                assert app._iccs_lifecycle.bound is None

                await _wait_for_iccs_worker(app)
                assert app._iccs_lifecycle.bound is not None
                with Session(loaded_engine_from_file) as session:
                    current = session.get_one(AimbatEvent, current_event.id)
                    assert app._iccs_lifecycle.bound.phase_id == current.phases[0].id

        asyncio.run(_run())

    def test_result_for_another_phase_of_the_event_is_discarded(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A build for P that ends after a switch to PKP is dropped, and PKP is built."""
        _patch_engine(monkeypatch, loaded_engine_from_file)
        with Session(loaded_engine_from_file) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            p_phase_id = event.phases[0].id
            pkp = AimbatPhase(name="PKP", parameters=default_phase_parameters("PKP"))
            event.phases.append(pkp)
            session.commit()
            event_id, pkp_id = event.id, pkp.id

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)

                with Session(loaded_engine_from_file) as session:
                    stale_bound = _real_create_iccs_instance(session, p_phase_id)

                started: list[uuid.UUID] = []
                monkeypatch.setattr(
                    AimbatTUI,
                    "_worker_create_iccs",
                    lambda self, phase_id, is_retry=False: started.append(phase_id),
                )
                app._current_event_id = event_id
                app._current_phase_name = "PKP"

                app._assign_iccs(stale_bound)

                assert app._iccs_lifecycle.bound is None
                assert started == [pkp_id]

        asyncio.run(_run())

    def test_request_dropped_during_a_build_is_replayed(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A request made while a build runs is replayed if that build yields nothing."""
        _patch_engine(monkeypatch, loaded_engine_from_file)
        with Session(loaded_engine_from_file) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            event_id, phase_id = event.id, event.phases[0].id

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)

                started: list[uuid.UUID] = []
                monkeypatch.setattr(
                    AimbatTUI,
                    "_worker_create_iccs",
                    lambda self, phase_id, is_retry=False: started.append(phase_id),
                )
                app._current_event_id = event_id
                assert app._iccs_lifecycle.start_creating()  # a build in flight

                app._create_iccs()
                assert started == []

                app._end_creation_without_instance(None)  # that build aborts
                assert started == [phase_id]

        asyncio.run(_run())

    def test_request_during_a_successful_build_is_replayed(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A rebuild asked for during a build follows it, since it may predate a change."""
        _patch_engine(monkeypatch, loaded_engine_from_file)
        with Session(loaded_engine_from_file) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            event_id, phase_id = event.id, event.phases[0].id

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)
                with Session(loaded_engine_from_file) as session:
                    built = _real_create_iccs_instance(session, phase_id)

                started: list[uuid.UUID] = []
                monkeypatch.setattr(
                    AimbatTUI,
                    "_worker_create_iccs",
                    lambda self, phase_id, is_retry=False: started.append(phase_id),
                )
                app._current_event_id = event_id
                assert app._iccs_lifecycle.start_creating()
                app._create_iccs()  # e.g. the Parameters modal closed with changes

                app._assign_iccs(built)

                assert started == [phase_id]

        asyncio.run(_run())

    def test_stale_worker_result_for_deleted_event_is_discarded(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A stale result is dropped and no retry is armed when nothing is selected."""
        _patch_engine(monkeypatch, loaded_engine_from_file)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)

                with Session(loaded_engine_from_file) as session:
                    event = session.exec(select(AimbatEvent)).first()
                assert event is not None

                with Session(loaded_engine_from_file) as session:
                    event_reloaded = session.get(AimbatEvent, event.id)
                    assert event_reloaded is not None
                    stale_bound = _real_create_iccs_instance(
                        session, event_reloaded.phases[0].id
                    )

                # Simulate the event having been deleted (and none selected)
                # while `stale_bound` was still being built.
                app._current_event_id = None

                app._assign_iccs(stale_bound)
                await pilot.pause(delay=0.2)

                assert app._iccs_lifecycle.bound is None
                assert app._iccs_lifecycle.retry_pending is False

        asyncio.run(_run())


# ===========================================================================
# _require_iccs — contextual "not ready" notification
# ===========================================================================


@pytest.mark.slow
class TestRequireIccs:
    """`_require_iccs` picks its warning based on whether an event is selected.

    See `_IccsLifecycleMixin._require_iccs`: with no current event it points
    the user at the Project tab; with an event selected but no bound ICCS
    instance yet, it points at the phase parameters instead.
    """

    def test_no_event_selected(
        self, patched_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With no current event, the notification directs to the Project tab."""
        _patch_engine(monkeypatch, patched_engine)

        notifications: list[tuple[str, str]] = []

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause()
                app = cast(AimbatTUI, pilot.app)
                monkeypatch.setattr(
                    app,
                    "notify",
                    lambda message, *, severity="information", **kwargs: (
                        notifications.append((message, severity))
                    ),
                )
                assert app._current_event_id is None

                assert app._require_iccs() is False

        asyncio.run(_run())

        assert len(notifications) == 1
        message, severity = notifications[0]
        assert "no event selected" in message.lower()
        assert "project" in message.lower()
        assert severity == "warning"

    def test_event_selected_but_iccs_not_ready(
        self, loaded_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With an event selected but no bound ICCS yet, it points at Parameters."""
        _patch_engine(monkeypatch, loaded_engine)

        notifications: list[tuple[str, str]] = []

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause()
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)
                monkeypatch.setattr(
                    app,
                    "notify",
                    lambda message, *, severity="information", **kwargs: (
                        notifications.append((message, severity))
                    ),
                )

                with Session(loaded_engine) as session:
                    event = session.exec(select(AimbatEvent)).first()
                assert event is not None
                app._current_event_id = event.id
                assert app._iccs_lifecycle.ready is False

                assert app._require_iccs() is False

        asyncio.run(_run())

        assert len(notifications) == 1
        message, severity = notifications[0]
        assert "iccs not ready" in message.lower()
        assert "parameters" in message.lower()
        assert severity == "warning"


class TestParametersOnSeveralPhases:
    """Opening the parameters of an event with several phases warns."""

    def test_names_the_phases(
        self, loaded_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, loaded_engine)
        with Session(loaded_engine) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            event.phases.append(
                AimbatPhase(name="PKP", parameters=default_phase_parameters("PKP"))
            )
            session.commit()
            event_id = event.id

        notifications: list[tuple[str, str]] = []

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)
                monkeypatch.setattr(
                    app,
                    "notify",
                    lambda message, *, severity="information", **kwargs: (
                        notifications.append((message, severity))
                    ),
                )
                app._current_event_id = event_id

                app.action_open_parameters()

                assert not isinstance(app.screen, ParametersModal)

        asyncio.run(_run())

        assert len(notifications) == 1
        message, severity = notifications[0]
        assert "This event has phases P, PKP" in message
        assert "Press p to select one" in message
        assert severity == "warning"

    def test_selecting_opens_the_picker_and_escape_leaves_no_phase(
        self, loaded_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, loaded_engine)
        with Session(loaded_engine) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            event.phases.append(
                AimbatPhase(name="PKP", parameters=default_phase_parameters("PKP"))
            )
            session.commit()
            event_id = event.id

        notifications: list[tuple[str, str]] = []

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)
                monkeypatch.setattr(
                    app,
                    "notify",
                    lambda message, *, severity="information", **kwargs: (
                        notifications.append((message, severity))
                    ),
                )

                app._select_event(str(event_id))
                await pilot.pause()
                assert isinstance(app.screen, PhaseSelectModal)
                await pilot.press("escape")
                await _wait_for_iccs_worker(app)

                assert app._current_phase_name is None
                assert not app._iccs_lifecycle.ready
                bar = app.query_one("#event-bar", Static)
                assert "select a phase (p)" in str(bar.render())
                app.action_open_align()

        asyncio.run(_run())

        notices = [m for m, s in notifications if s == "warning"]
        assert notices == ["This event has phases P, PKP. Press p to select one."]

    def test_choosing_a_phase_filters_the_tabs(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, loaded_engine_from_file)
        with Session(loaded_engine_from_file) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            event.phases.append(
                AimbatPhase(name="PKP", parameters=default_phase_parameters("PKP"))
            )
            session.commit()
            event_id = event.id
            p_phase = next(p for p in event.phases if p.name == "P")
            p_rows = len(p_phase.seismogram_parameters)
            create_snapshot(session, p_phase.id, "P snapshot")
            session.commit()
        assert p_rows > 0

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)

                app._select_event(str(event_id))
                await pilot.pause()
                assert isinstance(app.screen, PhaseSelectModal)
                await pilot.press("enter")  # cursor starts on P, the first
                await _wait_for_iccs_worker(app)
                await pilot.pause()

                assert app._current_phase_name == "P"
                assert app._iccs_lifecycle.ready
                table = app.query_one("#seismogram-table", DataTable)
                snapshots = app.query_one("#snapshot-table", DataTable)
                assert table.row_count == p_rows
                assert snapshots.row_count == 1
                assert "|  P " in str(app.query_one("#event-bar", Static).render())

                # PKP has no seismograms or snapshots, so its tabs are empty.
                await pilot.press("p")
                await pilot.pause()
                assert isinstance(app.screen, PhaseSelectModal)
                await pilot.press("down", "enter")
                await _wait_for_iccs_worker(app)
                await pilot.pause()
                assert app._current_phase_name == "PKP"
                assert table.row_count == 0
                assert snapshots.row_count == 0
                assert "|  PKP " in str(app.query_one("#event-bar", Static).render())

        asyncio.run(_run())

    def test_a_deleted_event_clears_the_phase(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, loaded_engine_from_file)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)
                app._current_event_id = uuid.uuid4()
                app._current_phase_name = "P"

                with Session(loaded_engine_from_file) as session:
                    with pytest.raises(NoResultFound):
                        app._get_current_event(session)

                assert app._current_event_id is None
                assert app._current_phase_name is None

        asyncio.run(_run())

    def test_phase_key_on_an_event_without_phases_opens_nothing(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, loaded_engine_from_file)
        with Session(loaded_engine_from_file) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            event_id = event.id
            for phase in list(event.phases):
                session.delete(phase)
            session.commit()

        notifications: list[tuple[str, str]] = []

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)
                monkeypatch.setattr(
                    app,
                    "notify",
                    lambda message, *, severity="information", **kwargs: (
                        notifications.append((message, severity))
                    ),
                )
                app._current_event_id = event_id
                app.action_select_phase()
                await pilot.pause()
                assert not isinstance(app.screen, PhaseSelectModal)

        asyncio.run(_run())

        assert ("The event has no phases.", "warning") in notifications

    def test_poll_clears_a_phase_the_event_no_longer_has(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, loaded_engine_from_file)
        with Session(loaded_engine_from_file) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            event_id = event.id

        notifications: list[tuple[str, str]] = []

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)
                monkeypatch.setattr(
                    app,
                    "notify",
                    lambda message, *, severity="information", **kwargs: (
                        notifications.append((message, severity))
                    ),
                )
                # As if PKP was selected, then renamed from the CLI.
                app._current_event_id = event_id
                app._current_phase_name = "PKP"

                app._check_iccs_staleness()
                await _wait_for_iccs_worker(app)

                assert app._current_phase_name is None
                assert app._iccs_lifecycle.ready

        asyncio.run(_run())

        assert ("The event has no phase PKP any more", "warning") in [
            (m.split(".")[0], s) for m, s in notifications
        ]

    def test_only_phase_carries_to_an_event_with_several(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, loaded_engine_from_file)
        with Session(loaded_engine_from_file) as session:
            first, second = session.exec(select(AimbatEvent)).all()[:2]
            second.phases.append(
                AimbatPhase(name="PKP", parameters=default_phase_parameters("PKP"))
            )
            session.commit()
            first_id, second_id = first.id, second.id

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)

                app._select_event(str(first_id))  # P only, no name chosen
                await _wait_for_iccs_worker(app)
                app._select_event(str(second_id))
                await _wait_for_iccs_worker(app)
                await pilot.pause()

                assert not isinstance(app.screen, PhaseSelectModal)
                assert app._current_phase_name == "P"

        asyncio.run(_run())

    def test_choosing_the_current_phase_keeps_the_instance(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, loaded_engine_from_file)
        with Session(loaded_engine_from_file) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            event_id = event.id

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)
                app._select_event(str(event_id))
                await _wait_for_iccs_worker(app)
                bound = app._iccs_lifecycle.bound
                assert bound is not None

                app._on_phase_chosen("P")
                await _wait_for_iccs_worker(app)

                assert app._iccs_lifecycle.bound is bound

        asyncio.run(_run())

    def test_phase_key_is_off_while_a_dialog_is_open(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, loaded_engine_from_file)
        with Session(loaded_engine_from_file) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            event_id = event.id

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)
                app._select_event(str(event_id))
                await _wait_for_iccs_worker(app)
                assert app.check_action("select_phase", ()) is True

                app.action_select_phase()
                await pilot.pause()
                assert isinstance(app.screen, PhaseSelectModal)
                assert app.check_action("select_phase", ()) is False
                await pilot.press("p")
                await pilot.pause()
                assert len(app.screen_stack) == 2

        asyncio.run(_run())

    def test_processing_clears_a_phase_the_event_no_longer_has(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, loaded_engine_from_file)
        with Session(loaded_engine_from_file) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            event_id = event.id

        notifications: list[str] = []

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)
                monkeypatch.setattr(
                    app,
                    "notify",
                    lambda message, **kwargs: notifications.append(message),
                )
                app._current_event_id = event_id
                app._current_phase_name = "PKP"  # renamed from the CLI since

                assert app._require_iccs() is False

                assert app._current_phase_name is None
                await _wait_for_iccs_worker(app)

        asyncio.run(_run())

        assert notifications == [
            "The event has no phase PKP any more. The phase selection is cleared."
        ]

    def test_phase_name_carries_to_an_event_that_has_it(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, loaded_engine_from_file)
        with Session(loaded_engine_from_file) as session:
            first, second = session.exec(select(AimbatEvent)).all()[:2]
            first.phases.append(
                AimbatPhase(name="PKP", parameters=default_phase_parameters("PKP"))
            )
            session.commit()
            first_id, second_id = first.id, second.id

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)

                app._current_phase_name = "P"
                app._select_event(str(first_id))
                await pilot.pause()
                assert not isinstance(app.screen, PhaseSelectModal)
                assert app._current_phase_name == "P"

                app._current_phase_name = "PKP"
                app._select_event(str(second_id))
                await pilot.pause()
                assert not isinstance(app.screen, PhaseSelectModal)
                assert app._current_phase_name is None
                await _wait_for_iccs_worker(app)
                assert app._iccs_lifecycle.ready

        asyncio.run(_run())


class _FakeAlignResult:
    summary = RunSummary("Alignment complete", warning=False)


@pytest.mark.slow
class TestAlignGuard:
    """While an alignment runs, the main thread leaves its ICCS instance alone.

    See `IccsLifecycle.aligning`: the align worker changes the instance in
    place, so the poll, panel refreshes, rebuilds and row actions that write
    must not touch it until the worker stops.
    """

    def test_nothing_reads_or_replaces_the_instance(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, loaded_engine_from_file)
        with Session(loaded_engine_from_file) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            event_id, seismogram_id = event.id, event.seismograms[0].id

        notifications: list[tuple[str, str]] = []

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)
                app._select_event(str(event_id))
                await _wait_for_iccs_worker(app)
                bound = app._iccs_lifecycle.bound
                assert bound is not None
                selects = [s.select for s in bound.iccs.seismograms]

                monkeypatch.setattr(
                    app,
                    "notify",
                    lambda message, *, severity="information", **kwargs: (
                        notifications.append((message, severity))
                    ),
                )
                handed: list[BoundICCS | None] = []
                monkeypatch.setattr(
                    SeismogramPanel,
                    "refresh_data",
                    lambda self, session, event_id, phase_name, bound_iccs: (
                        handed.append(bound_iccs)
                    ),
                )
                started: list[uuid.UUID] = []
                monkeypatch.setattr(
                    AimbatTUI,
                    "_worker_create_iccs",
                    lambda self, phase_id, is_retry=False: started.append(phase_id),
                )

                assert app._iccs_lifecycle.start_aligning()
                app._check_iccs_staleness()
                app._create_iccs()
                app.refresh_all()
                app._handle_row_action(
                    "tab-seismograms", str(seismogram_id), "toggle_select"
                )

                assert started == []
                assert handed == [None]
                assert app._iccs_lifecycle.bound is bound
                assert [s.select for s in bound.iccs.seismograms] == selects
                for action in (
                    "open_align",
                    "open_interactive_tools",
                    "open_parameters",
                    "select_phase",
                ):
                    assert app.check_action(action, ()) is False
                bar = app.query_one("#event-bar", Static)
                assert "aligning" in str(bar.render())

        asyncio.run(_run())

        assert ("Alignment running: wait for it to finish", "warning") in notifications

    @pytest.mark.parametrize("fails", [False, True])
    def test_worker_end_clears_the_guard(
        self,
        fails: bool,
        loaded_engine_from_file: Engine,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch_engine(monkeypatch, loaded_engine_from_file)

        def _fake_run_iccs(phase_id: uuid.UUID, **kwargs: bool) -> _FakeAlignResult:
            if fails:
                raise RuntimeError("simulated alignment failure")
            return _FakeAlignResult()

        monkeypatch.setattr("aimbat.actions.run_iccs", _fake_run_iccs)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)

                assert app._iccs_lifecycle.start_aligning()
                app._run_align_tool(uuid.uuid4(), "iccs", False, False, False)
                await app.workers.wait_for_complete()
                await pilot.pause()

                assert app._iccs_lifecycle.aligning is False

        asyncio.run(_run())

    def test_cancelled_worker_keeps_the_guard_until_its_thread_ends(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Textual marks a cancelled thread worker CANCELLED while it still runs."""
        _patch_engine(monkeypatch, loaded_engine_from_file)
        release = threading.Event()
        running = threading.Event()

        def _blocking_run_iccs(phase_id: uuid.UUID, **kwargs: bool) -> _FakeAlignResult:
            running.set()
            release.wait(timeout=10)
            return _FakeAlignResult()

        monkeypatch.setattr("aimbat.actions.run_iccs", _blocking_run_iccs)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)

                assert app._iccs_lifecycle.start_aligning()
                worker = app._run_align_tool(uuid.uuid4(), "iccs", False, False, False)
                assert await asyncio.to_thread(running.wait, 5)
                worker.cancel()
                with suppress(WorkerCancelled):
                    await app.workers.wait_for_complete()
                await pilot.pause()
                assert app._iccs_lifecycle.aligning is True

                release.set()
                for _ in range(100):
                    if not app._iccs_lifecycle.aligning:
                        break
                    await pilot.pause(delay=0.05)
                assert app._iccs_lifecycle.aligning is False

        asyncio.run(_run())


@pytest.mark.slow
class TestAlignModalLosesIccsWhileOpen:
    """The align menu re-checks the ICCS instance when the modal closes.

    `action_open_align` gates on `_require_iccs()` before pushing the modal,
    but the modal is async: the staleness poll can rebuild the instance while
    it is open, leaving `bound` as `None`. Handing that `None` to the worker
    surfaced as `'NoneType' object has no attribute 'iccs'`.
    """

    def test_cleared_instance_notifies_instead_of_running(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Clearing `bound` while the modal is open must not reach the worker."""
        _patch_engine(monkeypatch, loaded_engine_from_file)

        notifications: list[tuple[str, str]] = []
        align_calls: list[object] = []
        callbacks: list[Callable[[object], object]] = []

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause()
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)

                with Session(loaded_engine_from_file) as session:
                    event = session.exec(select(AimbatEvent)).first()
                    assert event is not None
                    app._current_event_id = event.id
                    app._iccs_lifecycle.assign(
                        _real_create_iccs_instance(session, event.phases[0].id)
                    )
                assert app._iccs_lifecycle.ready is True

                real_push_screen = app.push_screen

                def fake_push_screen(
                    screen: object,
                    callback: Callable[[object], object] | None = None,
                    **kwargs: object,
                ) -> object:
                    if isinstance(screen, AlignModal):
                        assert callback is not None
                        callbacks.append(callback)
                        return None
                    return real_push_screen(screen, callback, **kwargs)  # type: ignore[call-overload]

                monkeypatch.setattr(app, "push_screen", fake_push_screen)
                monkeypatch.setattr(
                    app,
                    "notify",
                    lambda message, *, severity="information", **kwargs: (
                        notifications.append((message, severity))
                    ),
                )
                monkeypatch.setattr(
                    app, "_run_align_tool", lambda *args: align_calls.append(args)
                )

                app.action_open_align()
                assert len(callbacks) == 1

                # What the staleness poll does via `start_creating()`.
                app._iccs_lifecycle.bound = None
                callbacks[0](("iccs", False, False, False))

        asyncio.run(_run())

        assert align_calls == []
        assert len(notifications) == 1
        message, severity = notifications[0]
        assert "iccs not ready" in message.lower()
        assert severity == "warning"


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
            assert event.phases[0].parameters.completed is True

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
            assert seismogram.phase_rows[0].select is False

    def test_snapshot_action_shows_details(
        self, loaded_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Choosing 'Show details' from a snapshot's action menu opens the details modal."""
        _patch_engine(monkeypatch, loaded_engine)

        with Session(loaded_engine) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            event_id = event.id
            create_snapshot(session, event.phases[0].id, "wiring test snapshot")
            session.commit()

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


# ===========================================================================
# Row-action footer hotkeys — table-aware footer (bypassing the Enter menu)
# ===========================================================================


@pytest.mark.slow
class TestRowActionFooterHotkeys:
    """Row actions are reachable directly as footer hotkeys when their table
    has keyboard focus, not just via Enter -> menu (see `_RowActionTable` in
    `_panels.py`).
    """

    def test_seismogram_hotkey_toggles_select(
        self, loaded_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pressing 's' directly on a focused seismogram row toggles select,
        with no Enter/menu navigation, and produces the same result the
        Enter -> menu path does.
        """
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
                await pilot.press("s")  # direct hotkey, no menu
                await pilot.pause(delay=0.3)
                return uuid.UUID(row_id)

        seismogram_id = asyncio.run(_run())

        with Session(loaded_engine) as session:
            seismogram = session.get(AimbatSeismogram, seismogram_id)
            assert seismogram is not None
            assert seismogram.phase_rows[0].select is False

    def test_footer_shows_row_action_only_for_focused_table(
        self, loaded_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An events-table-only hotkey appears only while that table (not the
        stations table) has keyboard focus.
        """
        _patch_engine(monkeypatch, loaded_engine)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause(delay=0.5)
                event_table = pilot.app.query_one("#project-event-table", DataTable)
                event_table.focus()
                await pilot.pause()
                # "m" = toggle_completed, an events-table-only row action.
                assert "m" in pilot.app.screen.active_bindings

                station_table = pilot.app.query_one("#project-station-table", DataTable)
                station_table.focus()
                await pilot.pause()
                assert "m" not in pilot.app.screen.active_bindings

        asyncio.run(_run())

    def test_footer_hides_row_action_when_table_empty(
        self, patched_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Row-action hotkeys are absent from the footer when their table has no rows."""
        _patch_engine(monkeypatch, patched_engine)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause()
                table = pilot.app.query_one("#project-event-table", DataTable)
                assert table.row_count == 0
                table.focus()
                await pilot.pause()
                assert "m" not in pilot.app.screen.active_bindings

        asyncio.run(_run())


# ===========================================================================
# Hotkey scoping — add_data/tools/align/new_snapshot/parameters
# ===========================================================================


@pytest.mark.slow
class TestHotkeyScoping:
    """Top-level hotkeys are scoped to the tab (and, for parameters, the
    table) they make sense on, via `AimbatTUI.check_action`.
    """

    def test_add_data_key_is_i_not_d(self) -> None:
        """`add_data` is bound to 'i'; 'd' is no longer bound to it anywhere
        in the app-level BINDINGS (it is now the per-table delete hotkey).
        """
        keys_to_actions = {
            b.key: b.action for b in AimbatTUI.BINDINGS if isinstance(b, Binding)
        }
        assert keys_to_actions.get("i") == "add_data"
        assert "d" not in keys_to_actions

    def test_add_data_hidden_outside_project_tab(
        self, patched_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, patched_engine)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause()
                app = cast(AimbatTUI, pilot.app)
                assert app.check_action("add_data", ()) is True
                await pilot.press("L")  # Project -> Live data
                await pilot.pause()
                assert app.check_action("add_data", ()) is False
                assert "i" not in pilot.app.screen.active_bindings

        asyncio.run(_run())

    def test_new_snapshot_only_on_seismograms_tab(
        self, loaded_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, loaded_engine)

        with Session(loaded_engine) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            event_id = event.id

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause(delay=0.5)
                app = cast(AimbatTUI, pilot.app)
                app._current_event_id = event_id
                app.refresh_all()
                await pilot.pause(delay=0.5)
                assert app.check_action("new_snapshot", ()) is False  # tab-project

                await pilot.press("L")  # -> tab-seismograms
                await pilot.pause()
                assert app.check_action("new_snapshot", ()) is True

                await pilot.press("L")  # -> tab-snapshots
                await pilot.pause()
                assert app.check_action("new_snapshot", ()) is False

        asyncio.run(_run())

    def test_tools_and_align_hidden_outside_seismograms_tab(
        self, loaded_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, loaded_engine)

        with Session(loaded_engine) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            event_id = event.id

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause(delay=0.5)
                app = cast(AimbatTUI, pilot.app)
                app._current_event_id = event_id
                app.refresh_all()
                await pilot.pause(delay=0.5)
                for action in ("open_interactive_tools", "open_align"):
                    assert app.check_action(action, ()) is False  # tab-project

                await pilot.press("L")  # -> tab-seismograms
                await pilot.pause()
                for action in ("open_interactive_tools", "open_align"):
                    assert app.check_action(action, ()) is True
                assert "t" in pilot.app.screen.active_bindings
                assert "a" in pilot.app.screen.active_bindings

                await pilot.press("L")  # -> tab-snapshots
                await pilot.pause()
                for action in ("open_interactive_tools", "open_align"):
                    assert app.check_action(action, ()) is False

        asyncio.run(_run())

    def test_parameters_visible_on_events_table_not_stations_table(
        self, loaded_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, loaded_engine)

        with Session(loaded_engine) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            event_id = event.id

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause(delay=0.5)
                app = cast(AimbatTUI, pilot.app)
                app._current_event_id = event_id
                app.refresh_all()
                await pilot.pause(delay=0.5)

                event_table = pilot.app.query_one("#project-event-table", DataTable)
                event_table.focus()
                await pilot.pause()
                assert app.check_action("open_parameters", ()) is True
                assert "P" in pilot.app.screen.active_bindings

                station_table = pilot.app.query_one("#project-station-table", DataTable)
                station_table.focus()
                await pilot.pause()
                assert app.check_action("open_parameters", ()) is False
                assert "P" not in pilot.app.screen.active_bindings

        asyncio.run(_run())

    def test_parameters_visible_on_seismograms_tab(
        self, loaded_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, loaded_engine)

        with Session(loaded_engine) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            event_id = event.id

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause(delay=0.5)
                app = cast(AimbatTUI, pilot.app)
                app._current_event_id = event_id
                app.refresh_all()
                await pilot.pause(delay=0.5)

                # Leave focus on the stations table (where 'P' is hidden),
                # then switch tabs — the seismograms-tab branch must not
                # inherit that restriction.
                station_table = pilot.app.query_one("#project-station-table", DataTable)
                station_table.focus()
                await pilot.pause()
                await pilot.press("L")  # -> tab-seismograms
                await pilot.pause()
                assert app.check_action("open_parameters", ()) is True
                assert "P" in pilot.app.screen.active_bindings

        asyncio.run(_run())

    def test_parameters_hidden_on_snapshots_tab(
        self, loaded_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, loaded_engine)

        with Session(loaded_engine) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            event_id = event.id

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause(delay=0.5)
                app = cast(AimbatTUI, pilot.app)
                app._current_event_id = event_id
                app.refresh_all()
                await pilot.pause(delay=0.5)
                await pilot.press("L")  # -> tab-seismograms
                await pilot.press("L")  # -> tab-snapshots
                await pilot.pause()
                assert app.check_action("open_parameters", ()) is False
                assert "P" not in pilot.app.screen.active_bindings

        asyncio.run(_run())


# ===========================================================================
# Event-switcher retirement
# ===========================================================================


@pytest.mark.slow
class TestEventSwitcherRetirement:
    """The global 'e' hotkey and `EventSwitcherModal` are gone; event
    selection only happens via the Project tab's event table.
    """

    def test_e_key_is_not_bound(self) -> None:
        keys = {b.key for b in AimbatTUI.BINDINGS if isinstance(b, Binding)}
        assert "e" not in keys

    def test_e_key_press_does_nothing(
        self, patched_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, patched_engine)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause()
                depth_before = len(pilot.app.screen_stack)
                await pilot.press("e")
                await pilot.pause()
                # No modal was pushed in response to the unbound key.
                assert len(pilot.app.screen_stack) == depth_before

        asyncio.run(_run())

    def test_event_bar_hint_no_longer_mentions_e(
        self, loaded_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With an event selected, the bar's dimmed hint points at the
        Project tab instead of the retired 'e' hotkey.
        """
        _patch_engine(monkeypatch, loaded_engine)

        with Session(loaded_engine) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            event_id = event.id

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause(delay=0.5)
                app = cast(AimbatTUI, pilot.app)
                app._current_event_id = event_id
                app.refresh_all()
                await pilot.pause(delay=0.5)
                bar = pilot.app.query_one("#event-bar", Static)
                text = str(bar.render())
                assert "e = switch event" not in text
                assert "press e" not in text
                assert "Project tab" in text

        asyncio.run(_run())


# ===========================================================================
# Causal/zero-phase toggle — InteractiveToolsModal + _run_tool dispatch
# ===========================================================================


@pytest.mark.slow
class TestCausalZeroPhaseToggle:
    """The interactive-tools modal's zero-phase toggle, and its wiring
    through `ToolLaunchResult`/`_run_tool` into the causal-aware tools.
    """

    def test_causal_toggle_hidden_for_non_causal_tool(
        self, patched_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, patched_engine)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause()
                modal = InteractiveToolsModal()
                pilot.app.push_screen(modal)
                await pilot.pause()
                table = modal.query_one("#tools-table", DataTable)
                # _TOOLS[3] == "bandpass", a non-causal tool.
                table.move_cursor(row=3)
                await pilot.pause()
                assert "zero-phase" not in str(
                    modal.query_one("#tools-options", Static).render()
                )

        asyncio.run(_run())

    def test_causal_toggle_defaults_per_tool(
        self, patched_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, patched_engine)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause()
                modal = InteractiveToolsModal()
                pilot.app.push_screen(modal)
                await pilot.pause()
                # _TOOLS[0] == "pick", causal default True.
                assert modal._causal is True
                table = modal.query_one("#tools-table", DataTable)
                # _TOOLS[1] == "window", causal default False.
                table.move_cursor(row=1)
                await pilot.pause()
                assert modal._causal is False

        asyncio.run(_run())

    def test_run_tool_passes_causal_through(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A non-default causal toggle reaches `update_pick`, not just the
        registry dispatch — the actual regression the ToolLaunchResult /
        mixed-arity-registry design in decision 7 is guarding against.
        """
        _patch_engine(monkeypatch, loaded_engine_from_file)

        @contextmanager
        def _noop_suspend(self: AimbatTUI, label: str | None = None) -> Generator[None]:
            yield

        monkeypatch.setattr(AimbatTUI, "_suspend", _noop_suspend)

        captured: dict[str, object] = {}

        def _fake_update_pick(
            iccs: object,
            context: object,
            *,
            all_seismograms: object,
            use_matrix_image: object,
            causal: object,
            return_fig: object,
        ) -> dict[object, object]:
            captured["causal"] = causal
            return {}

        monkeypatch.setattr(aimbat._tui._tools, "update_pick", _fake_update_pick)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)
                with Session(loaded_engine_from_file) as session:
                    event = session.exec(select(AimbatEvent)).first()
                assert event is not None
                app._current_event_id = event.id
                app._create_iccs()
                await _wait_for_iccs_worker(app)
                assert app._iccs_lifecycle.bound is not None

                # "pick"'s causal default is True; pass the non-default
                # value through explicitly.
                app._run_tool("pick", True, False, False)
                await pilot.pause()

        asyncio.run(_run())
        assert captured["causal"] is False

    def test_run_tool_ignores_causal_for_non_causal_tools(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A non-causal tool's registry function is never called with a
        `causal` argument, even though `_run_tool` receives one.
        """
        _patch_engine(monkeypatch, loaded_engine_from_file)

        @contextmanager
        def _noop_suspend(self: AimbatTUI, label: str | None = None) -> Generator[None]:
            yield

        monkeypatch.setattr(AimbatTUI, "_suspend", _noop_suspend)

        calls: list[dict[str, object]] = []

        def _fake_update_bandpass(
            *args: object, **kwargs: object
        ) -> dict[object, object]:
            calls.append(kwargs)
            return {}

        monkeypatch.setattr(
            aimbat._tui._tools, "update_bandpass", _fake_update_bandpass
        )

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)
                with Session(loaded_engine_from_file) as session:
                    event = session.exec(select(AimbatEvent)).first()
                assert event is not None
                app._current_event_id = event.id
                app._create_iccs()
                await _wait_for_iccs_worker(app)
                assert app._iccs_lifecycle.bound is not None

                app._run_tool("bandpass", True, False, None)
                await pilot.pause()

        asyncio.run(_run())
        assert len(calls) == 1
        assert "causal" not in calls[0]

    def test_tool_launch_result_causal_is_none_for_non_causal_tools(
        self, patched_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, patched_engine)

        results: list[ToolLaunchResult | None] = []

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause()
                modal = InteractiveToolsModal()
                pilot.app.push_screen(modal, results.append)
                await pilot.pause()
                table = modal.query_one("#tools-table", DataTable)
                table.move_cursor(row=3)  # "bandpass"
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()

        asyncio.run(_run())
        assert len(results) == 1
        result = results[0]
        assert result is not None
        assert result.tool == "bandpass"
        assert result.causal is None


# ===========================================================================
# _run_tool: rebuild ICCS after a parameter-changing tool
# ===========================================================================


@contextmanager
def _noop_suspend(self: AimbatTUI, label: str | None = None) -> Generator[None]:
    yield


@pytest.mark.slow
class TestRunToolRebuildsIccs:
    """A parameter/pick-changing tool rebuilds ICCS (re-persisting iccs_cc);
    a view-only tool (stack/image) leaves the instance untouched.
    """

    def _prepare(self, monkeypatch: pytest.MonkeyPatch, engine: Engine) -> list[str]:
        _patch_engine(monkeypatch, engine)
        monkeypatch.setattr(AimbatTUI, "_suspend", _noop_suspend)
        monkeypatch.setattr(aimbat._tui._tools, "update_bandpass", lambda *a, **k: {})
        monkeypatch.setattr(aimbat._tui._tools, "plot_stack", lambda *a, **k: None)
        return []

    def _run_with_tool(
        self,
        engine: Engine,
        monkeypatch: pytest.MonkeyPatch,
        tool: str,
        calls: list[str],
    ) -> None:
        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)
                with Session(engine) as session:
                    event = session.exec(select(AimbatEvent)).first()
                assert event is not None
                app._current_event_id = event.id
                app._create_iccs()
                await _wait_for_iccs_worker(app)
                assert app._iccs_lifecycle.bound is not None
                monkeypatch.setattr(
                    AimbatTUI,
                    "_create_iccs",
                    lambda self, **kw: calls.append("rebuild"),
                )
                app._run_tool(tool, True, False, None)
                await pilot.pause()

        asyncio.run(_run())

    def test_param_changing_tool_rebuilds(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = self._prepare(monkeypatch, loaded_engine_from_file)
        self._run_with_tool(loaded_engine_from_file, monkeypatch, "bandpass", calls)
        assert calls == ["rebuild"]

    def test_view_only_tool_does_not_rebuild(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = self._prepare(monkeypatch, loaded_engine_from_file)
        self._run_with_tool(loaded_engine_from_file, monkeypatch, "stack", calls)
        assert calls == []

    def test_view_only_tool_leaves_the_instance_digest_untouched(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Updating the digest after a view-only tool would mask an external
        commit made while the plot window was open, defeating the staleness
        poller.
        """
        self._prepare(monkeypatch, loaded_engine_from_file)

        async def _run() -> tuple[object, object]:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)
                with Session(loaded_engine_from_file) as session:
                    event = session.exec(select(AimbatEvent)).first()
                assert event is not None
                app._current_event_id = event.id
                app._create_iccs()
                await _wait_for_iccs_worker(app)
                bound = app._iccs_lifecycle.bound
                assert bound is not None
                # A value no recomputation produces, so any update shows.
                bound.instance_digest = "sentinel"
                app._run_tool("stack", True, False, None)
                await pilot.pause()
                return "sentinel", bound.instance_digest

        before, after = asyncio.run(_run())
        assert before == after


@pytest.mark.slow
class TestToggleSeismogramBoolRefresh:
    """Toggling select/flip invalidates event-wide quality via triggers, so
    every panel must refresh - not just the Live data table (findings-tui M3).
    """

    def test_toggle_select_triggers_full_refresh(
        self, loaded_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, loaded_engine)

        with Session(loaded_engine) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            event_id = event.id
            seis = session.exec(
                select(AimbatSeismogram).where(AimbatSeismogram.event_id == event_id)
            ).first()
            assert seis is not None
            seis_id = seis.id

        calls: list[str] = []

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await pilot.pause(delay=0.5)
                app._current_event_id = event_id
                monkeypatch.setattr(
                    AimbatTUI,
                    "refresh_all",
                    lambda self: calls.append("refresh_all"),
                )
                app._toggle_seismogram_bool(str(seis_id), SeismogramParameter.SELECT)
                await pilot.pause()

        asyncio.run(_run())

        assert calls == ["refresh_all"]
        with Session(loaded_engine) as session:
            refetched = session.get(AimbatSeismogram, seis_id)
            assert refetched is not None
            assert refetched.phase_rows[0].select is False


# ===========================================================================
# refresh_all reads through a single session
# ===========================================================================


class TestRefreshAllSharesOneSession:
    """Every panel in a refresh reads through the same session, so the work
    cached on it (the shortener's id pool) is done once per refresh rather
    than once per panel (findings-tui L1).
    """

    def test_panels_receive_the_same_session(
        self, loaded_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, loaded_engine)

        seen: list[Session] = []

        def _record(panel: type[object]) -> None:
            original = panel.refresh_data  # type: ignore[attr-defined]

            def wrapper(self: object, session: Session, *args: object) -> None:
                seen.append(session)
                original(self, session, *args)

            monkeypatch.setattr(panel, "refresh_data", wrapper)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await pilot.pause(delay=0.5)
                for panel in (ProjectPanel, SeismogramPanel, SnapshotPanel):
                    _record(panel)
                app.refresh_all()
                await pilot.pause()

        asyncio.run(_run())

        assert len(seen) == 3, "every panel should have been refreshed"
        assert all(isinstance(session, Session) for session in seen)
        assert all(session is seen[0] for session in seen)


# ===========================================================================
# NoteWidget auto-save is crash-safe
# ===========================================================================


@pytest.mark.slow
class TestNoteWidgetAutoSave:
    """A failing note save must be surfaced, not propagated out of the handler."""

    def test_auto_save_swallows_write_error(
        self, loaded_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, loaded_engine)

        from aimbat._tui._widgets import NoteWidget, _NoteTextArea

        def _boom(*args: object, **kwargs: object) -> None:
            raise RuntimeError("database is locked")

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await pilot.pause()
                with Session(loaded_engine) as session:
                    event = session.exec(select(AimbatEvent)).first()
                assert event is not None

                note = app.query_one("#project-note", NoteWidget)
                note.set_entity("event", event.id)
                await pilot.pause()
                note.query_one("#note-textarea", _NoteTextArea).load_text("changed")

                monkeypatch.setattr(aimbat._tui._widgets, "save_note", _boom)
                # Must not raise.
                note._auto_save()
                await pilot.pause()

                # Not marked saved, so the next trigger retries.
                assert note._saved_content != "changed"

        asyncio.run(_run())


# ===========================================================================
# TUI data import auto-snapshots the touched event
# ===========================================================================


@pytest.mark.slow
class TestAddDataAutoSnapshot:
    """The TUI's own data import (`i`) auto-snapshots the touched event.

    Regression coverage for the pre-existing CLI/TUI inconsistency: the CLI's
    `data add` always auto-snapshots, but `action_add_data` used to discard
    its `add_data_to_project` return value and never snapshot at all.
    """

    def test_import_creates_snapshot(
        self, engine: Engine, sac_file_good: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Importing a SAC file via `i` creates an automatic snapshot for its event."""
        _patch_engine(monkeypatch, engine)

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await pilot.pause(delay=0.5)

                # The real FileOpen picker browses the filesystem interactively,
                # which nothing here needs to exercise; short-circuit just that
                # one push_screen call to hand back a known file directly, while
                # every other screen (the real ActionMenuModal type picker
                # included) still goes through the normal, key-driven path.
                real_push_screen = app.push_screen

                def fake_push_screen(
                    screen: object,
                    callback: Callable[[object], object] | None = None,
                    **kwargs: object,
                ) -> object:
                    if isinstance(screen, FileOpen):
                        if callback is not None:
                            callback(sac_file_good)
                        return None
                    return real_push_screen(screen, callback, **kwargs)  # type: ignore[call-overload]

                monkeypatch.setattr(app, "push_screen", fake_push_screen)

                await pilot.press("i")  # open the "Add Data" menu
                await pilot.pause()
                await pilot.press("enter")  # first data type: SAC
                await pilot.pause(delay=0.5)

        asyncio.run(_run())

        with Session(engine) as session:
            event = session.exec(select(AimbatEvent)).one()
            snapshot = session.exec(
                select(AimbatSnapshot)
                .join(AimbatPhase)
                .where(AimbatPhase.event_id == event.id)
            ).one()
            assert snapshot.automatic is True
            assert snapshot.comment == "Added 1 pick"


@pytest.mark.slow
class TestAddDataTypeMenuExcludesUncreatableTypes:
    """The "Add Data" type menu only offers types with a registered creator.

    Regression coverage: `DataType.MSEED` registers a reader/writer but no
    station, event, or seismogram creator (miniSEED carries no such
    metadata), so it cannot do anything useful through this file-picker
    flow - `add_data_to_project` silently adds nothing for it. It must not
    appear as a selectable type here.
    """

    def test_mseed_not_offered(
        self, patched_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_engine(monkeypatch, patched_engine)

        captured: list[ActionMenuModal] = []

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await pilot.pause()

                real_push_screen = app.push_screen

                def fake_push_screen(
                    screen: object,
                    callback: Callable[[object], object] | None = None,
                    **kwargs: object,
                ) -> object:
                    if isinstance(screen, ActionMenuModal):
                        captured.append(screen)
                    return real_push_screen(screen, callback, **kwargs)  # type: ignore[call-overload]

                monkeypatch.setattr(app, "push_screen", fake_push_screen)

                await pilot.press("i")  # open the "Add Data" menu
                await pilot.pause()

        asyncio.run(_run())

        assert len(captured) == 1
        offered_types = {key for key, _ in captured[0]._actions}
        assert "mseed" not in offered_types
        assert "sac" in offered_types


class TestPhaseSelectorOnLabelledData:
    """The phase picker on testkit's real data with labelled P and pP picks."""

    def test_each_phase_has_its_own_rows_and_instance(
        self, multi_phase_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = multi_phase_engine_from_file
        _patch_engine(monkeypatch, engine)
        with Session(engine) as session:
            event = session.exec(select(AimbatEvent)).one()
            event_id = event.id
            phase_ids = {phase.name: phase.id for phase in event.phases}

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                app = cast(AimbatTUI, pilot.app)
                await _wait_for_iccs_worker(app)
                table = app.query_one("#seismogram-table", DataTable)

                app._select_event(str(event_id))
                await pilot.pause()
                assert isinstance(app.screen, PhaseSelectModal)
                assert [key for key, _ in app.screen._actions] == ["P", "pP"]

                for keys, name, rows in (
                    (("down", "enter"), "pP", 13),
                    (("p", "up", "enter"), "P", 14),
                ):
                    await pilot.press(*keys)
                    await _wait_for_iccs_worker(app)
                    await pilot.pause()

                    assert app._current_phase_name == name
                    bound = app._iccs_lifecycle.bound
                    assert bound is not None
                    assert bound.phase_id == phase_ids[name]
                    assert len(bound.iccs.seismograms) == rows
                    assert table.row_count == rows
                    bar = str(app.query_one("#event-bar", Static).render())
                    assert f"|  {name} " in bar

        asyncio.run(_run())
