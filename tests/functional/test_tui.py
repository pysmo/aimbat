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
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from typing import cast

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, select
from textual.binding import Binding
from textual.widgets import DataTable, Static, TabbedContent, TabPane

import aimbat._tui._iccs_lifecycle
import aimbat._tui._panels
import aimbat._tui._tools
import aimbat._tui._widgets
import aimbat._tui.app
import aimbat._tui.modals
import aimbat.db
from aimbat._tui.app import AimbatTUI
from aimbat._tui.modals import (
    InteractiveToolsModal,
    SchemaStaleModal,
    SnapshotDetailsModal,
    ToolLaunchResult,
)
from aimbat._types import SeismogramParameter
from aimbat.core import (
    BoundICCS,
    IccsLifecycle,
    create_snapshot,
    get_current_revision,
    get_head_revision,
)
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
    monkeypatch.setattr(aimbat._tui._iccs_lifecycle, "engine", engine)
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

    def test_modal_shown_for_legacy_unstamped_database(
        self, patched_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A pre-Alembic database (no `alembic_version` table) blocks on a modal."""
        _patch_engine(monkeypatch, patched_engine)
        with patched_engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE alembic_version")

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause()
                modal = pilot.app.screen
                assert isinstance(modal, SchemaStaleModal)
                assert "predates AIMBAT's schema versioning" in modal._message

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
        """Pressing 'u' upgrades the database in place and enters the main UI."""
        _patch_engine(monkeypatch, patched_engine)
        with patched_engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE alembic_version")

        async def _run() -> None:
            async with AimbatTUI().run_test(size=_TUI_SIZE) as pilot:
                await pilot.pause()
                assert isinstance(pilot.app.screen, SchemaStaleModal)

                await pilot.press("u")
                await pilot.pause()

                assert not isinstance(pilot.app.screen, SchemaStaleModal)
                assert get_current_revision(patched_engine) == get_head_revision()

        asyncio.run(_run())

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
    consumes at most once before falling silent again until
    `event.last_modified` changes.
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

        monkeypatch.setattr(
            aimbat._tui._iccs_lifecycle, "create_iccs_instance", _always_fails
        )

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
                # attempt, so later polls see an unchanged `last_modified`.
                app._iccs_lifecycle.note_checked(event.last_modified)

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
            aimbat._tui._iccs_lifecycle, "create_iccs_instance", _fail_once_then_succeed
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
                app._iccs_lifecycle.note_checked(event.last_modified)

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

        def _always_raises(self: IccsLifecycle, last_modified: object) -> None:
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
                        session, stale_event_reloaded
                    )

                # Simulate the user having switched to a different event
                # while `stale_bound` was still being built in the
                # background for `stale_event`.
                app._current_event_id = current_event.id

                app._assign_iccs(stale_bound)
                assert app._iccs_lifecycle.bound is None

                await _wait_for_iccs_worker(app)
                assert app._iccs_lifecycle.bound is not None
                assert app._iccs_lifecycle.bound.event_id == current_event.id

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
                    stale_bound = _real_create_iccs_instance(session, event_reloaded)

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
    instance yet, it points at the Parameters tab instead.
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
            assert seismogram.parameters.select is False

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
                assert "p" in pilot.app.screen.active_bindings

                station_table = pilot.app.query_one("#project-station-table", DataTable)
                station_table.focus()
                await pilot.pause()
                assert app.check_action("open_parameters", ()) is False
                assert "p" not in pilot.app.screen.active_bindings

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

                # Leave focus on the stations table (where 'p' is hidden),
                # then switch tabs — the seismograms-tab branch must not
                # inherit that restriction.
                station_table = pilot.app.query_one("#project-station-table", DataTable)
                station_table.focus()
                await pilot.pause()
                await pilot.press("L")  # -> tab-seismograms
                await pilot.pause()
                assert app.check_action("open_parameters", ()) is True
                assert "p" in pilot.app.screen.active_bindings

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
                assert "p" not in pilot.app.screen.active_bindings

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
                # _TOOLS[0] == "phase", causal default True.
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
        def _noop_suspend(
            self: AimbatTUI, label: str | None = None
        ) -> Generator[None, None, None]:
            yield

        monkeypatch.setattr(AimbatTUI, "_suspend", _noop_suspend)

        captured: dict[str, object] = {}

        def _fake_update_pick(
            session: object,
            iccs: object,
            context: object,
            *,
            all_seismograms: object,
            use_matrix_image: object,
            causal: object,
            return_fig: object,
        ) -> None:
            captured["causal"] = causal

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

                # "phase"'s causal default is True; pass the non-default
                # value through explicitly.
                app._run_tool("phase", True, False, False)
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
        def _noop_suspend(
            self: AimbatTUI, label: str | None = None
        ) -> Generator[None, None, None]:
            yield

        monkeypatch.setattr(AimbatTUI, "_suspend", _noop_suspend)

        calls: list[dict[str, object]] = []

        def _fake_update_bandpass(*args: object, **kwargs: object) -> None:
            calls.append(kwargs)

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
def _noop_suspend(
    self: AimbatTUI, label: str | None = None
) -> Generator[None, None, None]:
    yield


@pytest.mark.slow
class TestRunToolRebuildsIccs:
    """A parameter/pick-changing tool rebuilds ICCS (re-persisting iccs_cc);
    a view-only tool (stack/image) leaves the instance untouched.
    """

    def _prepare(self, monkeypatch: pytest.MonkeyPatch, engine: Engine) -> list[str]:
        _patch_engine(monkeypatch, engine)
        monkeypatch.setattr(AimbatTUI, "_suspend", _noop_suspend)
        monkeypatch.setattr(aimbat._tui._tools, "update_bandpass", lambda *a, **k: None)
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

    def test_view_only_tool_leaves_created_at_untouched(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Bumping created_at after a view-only tool would mask an external
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
                before = bound.created_at
                app._run_tool("stack", True, False, None)
                await pilot.pause()
                return before, bound.created_at

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
            assert refetched.parameters.select is False


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
