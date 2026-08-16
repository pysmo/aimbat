"""AIMBAT Terminal User Interface application."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Generator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Literal

from pandas import Timestamp
from rich.console import Console
from rich.panel import Panel
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, select
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Static,
    TabbedContent,
    TabPane,
    Tabs,
)
from textual_fspicker import FileOpen, FileSave, Filters

from pysmo.tools.iccs import ICCS

from aimbat import settings
from aimbat._tui._panels import ProjectPanel, SeismogramPanel, SnapshotPanel
from aimbat._tui.modals import (
    ActionMenuModal,
    AlignModal,
    ConfirmModal,
    EventSwitcherModal,
    HelpModal,
    InteractiveToolsModal,
    NoProjectModal,
    ParametersModal,
    SchemaStaleModal,
    SnapshotCommentModal,
    SnapshotDetailsModal,
)
from aimbat._types import SeismogramParameter
from aimbat.core import (
    BoundICCS,
    add_data_to_project,
    build_iccs_from_snapshot,
    create_iccs_instance,
    create_project,
    create_snapshot,
    delete_event,
    delete_seismogram,
    delete_snapshot,
    delete_station,
    dump_snapshot_results,
    get_current_revision,
    reset_seismogram_parameters,
    rollback_to_snapshot,
    run_iccs,
    run_mccc,
    set_seismogram_parameter,
    upgrade_project,
)
from aimbat.core._migrations import SchemaMismatchError, _build_staleness_warning
from aimbat.core._project import _project_exists
from aimbat.db import engine
from aimbat.io import DATATYPE_SUFFIXES, DataType
from aimbat.logger import logger
from aimbat.models import (
    AimbatEvent,
    AimbatEventParametersBase,
    AimbatSeismogram,
    AimbatSnapshot,
    AimbatStation,
)
from aimbat.plot import (
    plot_matrix_image,
    plot_seismograms,
    plot_stack,
    update_bandpass,
    update_min_cc,
    update_pick,
    update_timewindow,
)
from aimbat.utils.formatters import fmt_timestamp

from ._format import tui_cell, tui_display_title

_DEFAULT_THEME = settings.tui_dark_theme
_LIGHT_THEME = settings.tui_light_theme

_MAIN_TABS = {"tab-project", "tab-seismograms", "tab-snapshots"}


# Extend _TOOL_REGISTRY to register new interactive tools.  Each entry maps a
# key to a (label, callable) pair.  The callable receives
# (session, event, iccs, context, all_seismograms) and returns None.
type _ToolFn = Callable[[Session, AimbatEvent, ICCS, bool, bool], None]


def _tool_phase(
    session: Session,
    event: AimbatEvent,
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
) -> None:
    # TODO: expose a causal/zero-phase toggle once the TUI overhaul adds a
    # widget-based equivalent of the CLI's --causal/--zero-phase flag.
    update_pick(
        session,
        iccs,
        context,
        all_seismograms=all_seismograms,
        use_matrix_image=False,
        causal=True,
        return_fig=False,
    )


def _tool_window(
    session: Session,
    event: AimbatEvent,
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
) -> None:
    # TODO: expose a causal/zero-phase toggle once the TUI overhaul adds a
    # widget-based equivalent of the CLI's --causal/--zero-phase flag.
    update_timewindow(
        session,
        event,
        iccs,
        context,
        all_seismograms=all_seismograms,
        use_matrix_image=False,
        causal=False,
        return_fig=False,
    )


def _tool_cc(
    session: Session,
    event: AimbatEvent,
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
) -> None:
    # TODO: expose a causal/zero-phase toggle once the TUI overhaul adds a
    # widget-based equivalent of the CLI's --causal/--zero-phase flag.
    update_min_cc(
        session,
        event,
        iccs,
        context,
        all_seismograms=all_seismograms,
        causal=False,
        return_fig=False,
    )


def _tool_bandpass(
    session: Session,
    event: AimbatEvent,
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
) -> None:
    update_bandpass(
        session,
        event,
        iccs,
        context,
        all_seismograms=all_seismograms,
        use_matrix_image=False,
        return_fig=False,
    )


def _tool_stack(
    session: Session,
    event: AimbatEvent,
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
) -> None:
    plot_stack(iccs, context, all_seismograms, return_fig=False)


def _tool_image(
    session: Session,
    event: AimbatEvent,
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
) -> None:
    plot_matrix_image(iccs, context, all_seismograms, return_fig=False)


_TOOL_REGISTRY: dict[str, tuple[str, _ToolFn]] = {
    "phase": ("Phase arrival (t1)", _tool_phase),
    "window": ("Time window", _tool_window),
    "cc": ("Min CC", _tool_cc),
    "bandpass": ("Bandpass filter", _tool_bandpass),
    "stack": ("Stack plot", _tool_stack),
    "image": ("Matrix image", _tool_image),
}


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------


class AimbatTUI(App[None]):
    """AIMBAT Terminal User Interface."""

    TITLE = "AIMBAT"
    CSS_PATH = "aimbat.tcss"

    BINDINGS = [
        Binding("e", "switch_event", "Events", show=True),
        Binding("d", "add_data", "Add Data", show=True),
        Binding("p", "open_parameters", "Parameters", show=True),
        Binding("t", "open_interactive_tools", "Tools", show=True),
        Binding("a", "open_align", "Align", show=True),
        Binding("n", "new_snapshot", "New Snapshot", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("c", "toggle_theme", "Theme", show=True),
        Binding("?", "show_help", "Help", show=True),
        Binding("H", "vim_left", "Vim left", show=False),
        Binding("L", "vim_right", "Vim right", show=False),
        Binding("q", "quit", "Quit", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="event-bar")
        with TabbedContent(initial="tab-project"):
            with TabPane("Project", id="tab-project"):
                yield ProjectPanel()
            with TabPane("Live data", id="tab-seismograms"):
                yield SeismogramPanel()
            with TabPane("Snapshots", id="tab-snapshots"):
                yield SnapshotPanel()
        yield Footer()

    def on_mount(self) -> None:
        self._bound_iccs: BoundICCS | None = None
        self._iccs_creating: bool = False
        self._iccs_last_modified_seen: Timestamp | None = None
        self._iccs_retry_pending: bool = False
        self._current_event_id: uuid.UUID | None = None
        self._active_tab: str = "tab-project"

        self.theme = _DEFAULT_THEME

        self.set_interval(5, self._check_iccs_staleness)

        logger.info("TUI started.")
        if not _project_exists(engine):
            self.push_screen(NoProjectModal(), self._on_no_project_modal)
        else:
            warning = _build_staleness_warning(get_current_revision(engine))
            if warning is not None:
                self.push_screen(
                    SchemaStaleModal(str(warning)), self._on_schema_stale_modal
                )
            else:
                self._create_iccs()
                self.refresh_all()

    def _on_no_project_modal(self, create: bool | None) -> None:
        if create:
            logger.info("User chose to create a new project.")
            create_project(engine)
            self._create_iccs()
            self.refresh_all()
        else:
            logger.info("User declined to create a project. Exiting.")
            self.exit()

    def _on_schema_stale_modal(self, upgrade: bool | None) -> None:
        """Blocks entry to the main UI entirely until the schema is current.

        Proceeding into panels that query columns the live schema doesn't
        have would crash with a raw `sqlalchemy.exc.OperationalError` from
        whichever panel happens to touch the drifted table first - see
        `aimbat.db`'s module docstring for the full reasoning behind always
        treating this as a hard stop rather than an advisory toast.
        """
        if not upgrade:
            logger.info("User declined to upgrade the project database. Exiting.")
            self.exit()
            return

        logger.info("User chose to upgrade the project database.")
        try:
            upgrade_project(engine)
        except SchemaMismatchError as exc:
            logger.error(f"Automatic upgrade failed: {exc}")
            self.exit(return_code=1, message=str(exc))
            return

        self._create_iccs()
        self.refresh_all()

    @on(TabbedContent.TabActivated)
    def on_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        if event.pane.id not in _MAIN_TABS:
            return
        self._active_tab = event.pane.id
        self.refresh_bindings()
        if not isinstance(self.focused, Tabs):
            with suppress(NoMatches):
                event.pane.query_one(DataTable).focus()
        if event.pane.id == "tab-seismograms":
            self.query_one(SeismogramPanel).clear_selection_if_empty()
        elif event.pane.id == "tab-snapshots":
            self.query_one(SnapshotPanel).clear_selection_if_empty()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action in {
            "open_parameters",
            "open_interactive_tools",
            "open_align",
            "new_snapshot",
        }:
            return self._current_event_id is not None
        return True

    # ------------------------------------------------------------------
    # Event selection
    # ------------------------------------------------------------------

    def _get_current_event(self, session: Session) -> AimbatEvent:
        """Return the event currently selected for processing in the TUI.

        Raises `NoResultFound` when no event has been selected yet.
        Clears a stale `_current_event_id` if the referenced event no longer exists.
        """
        if self._current_event_id is not None:
            event = session.get(AimbatEvent, self._current_event_id)
            if event is not None:
                return event
            self._current_event_id = None
        raise NoResultFound("No event selected")

    # ------------------------------------------------------------------
    # Suspend helper
    # ------------------------------------------------------------------

    @contextmanager
    def _suspend(self, label: str | None = None) -> Generator[None, None, None]:
        """Suspend Textual and handle errors gracefully.

        If `label` is given, a panel is shown with a "close matplotlib to
        return" hint.  Any exception raised inside the block is shown in the
        terminal while still suspended, then re-raised after Textual has fully
        resumed so callers can still react to it.
        """
        console = Console()
        caught: BaseException | None = None
        with self.suspend():
            console.clear()
            if label is not None:
                console.print(
                    Panel(
                        f"[bold]{label}[/bold]\n\n"
                        "Close the matplotlib window to return to AIMBAT.",
                        title="Interactive Tool Running",
                        border_style="bright_blue",
                        padding=(1, 4),
                    )
                )
            try:
                yield
            except Exception as exc:
                caught = exc
                console.print(f"\n[bold red]Error:[/bold red] {exc}")
                console.input("\n[dim]Press Enter to return to AIMBAT...[/dim]")
            finally:
                console.clear()
        if caught is not None:
            raise caught

    # ------------------------------------------------------------------
    # ICCS lifecycle
    # ------------------------------------------------------------------

    def _create_iccs(self, *, is_retry: bool = False) -> None:
        """Discard the existing ICCS instance and create a new one in a background worker.

        ICCS construction reads waveform data, so it must not block the asyncio event loop.
        Concurrent calls are ignored — only one worker runs at a time.

        `is_retry` marks a call made in response to `_iccs_retry_pending` (i.e. the
        one-shot retry after a previous failure). It is not itself allowed to
        re-arm `_iccs_retry_pending` on failure, so a persistently failing event
        gets exactly one automatic retry rather than retrying forever.
        """
        if self._iccs_creating:
            logger.debug(
                "ICCS creation already in progress; skipping duplicate request."
            )
            return
        self._iccs_creating = True
        self._bound_iccs = None
        self._iccs_retry_pending = False
        self._worker_create_iccs(is_retry)

    @work(thread=True)
    def _worker_create_iccs(self, is_retry: bool = False) -> None:
        """Background worker: create ICCS instance without blocking the UI."""
        try:
            with Session(engine) as session:
                event = self._get_current_event(session)
                bound_iccs = create_iccs_instance(session, event)
        except (NoResultFound, RuntimeError):
            logger.debug("ICCS worker: no event selected or no data; aborting.")
            self.call_from_thread(setattr, self, "_iccs_creating", False)
            return
        except Exception as exc:
            logger.exception(f"ICCS worker: unexpected error during creation: {exc}")
            self.call_from_thread(
                self.notify, f"ICCS init failed: {exc}", severity="error"
            )
            self.call_from_thread(setattr, self, "_iccs_creating", False)
            if not is_retry:
                # Give the staleness poller one retry attempt on the next tick.
                self.call_from_thread(setattr, self, "_iccs_retry_pending", True)
            return
        logger.debug("ICCS worker: instance created successfully.")
        self.call_from_thread(self._assign_iccs, bound_iccs)

    def _assign_iccs(self, bound_iccs: BoundICCS) -> None:
        """Main-thread callback: store the new BoundICCS instance and refresh status."""
        self._iccs_creating = False
        self._bound_iccs = bound_iccs
        logger.info("ICCS instance ready and assigned.")
        # Rebuilding ICCS re-upserts iccs_cc per seismogram, which also feeds
        # ProjectPanel's quality panel and station cc_mean/cc_sem column.
        self.refresh_all()

    # ------------------------------------------------------------------
    # Data refresh
    # ------------------------------------------------------------------

    def refresh_all(self) -> None:
        """Refresh every panel.

        Call this after any mutation by default. Only use a targeted
        `<Panel>.refresh_data(...)` call when you can name the specific
        reason no other panel's displayed data (including `column_property`
        counts and the live quality getters) is affected, and record that
        reasoning as a comment at the call site.
        """
        self.refresh_bindings()
        self._refresh_event_bar()
        self.query_one(ProjectPanel).refresh_data(self._current_event_id)
        self.query_one(SeismogramPanel).refresh_data(
            self._current_event_id, self._bound_iccs
        )
        self.query_one(SnapshotPanel).refresh_data(self._current_event_id)

    def _check_iccs_staleness(self) -> None:
        """Trigger ICCS recreation if the current event has been modified externally.

        When ICCS creation previously failed (e.g. due to an invalid parameter set via
        the CLI), retries once via `_iccs_retry_pending`, then waits for
        `event.last_modified` to change again before retrying further — this avoids
        retrying forever against a persistently failing event. On any detected
        change the full UI is refreshed so panels reflect the new DB state immediately.
        """
        if self._current_event_id is None:
            return
        try:
            with Session(engine) as session:
                event = self._get_current_event(session)
                last_modified = event.last_modified
                stale = (
                    self._bound_iccs.is_stale(event)
                    if self._bound_iccs is not None
                    else last_modified != self._iccs_last_modified_seen
                )
        except (NoResultFound, RuntimeError):
            return
        if stale:
            logger.debug(
                "ICCS staleness detected; recreating instance and refreshing UI."
            )
            self._iccs_last_modified_seen = last_modified
            self._create_iccs()
            self.refresh_all()
        elif self._iccs_retry_pending:
            logger.debug("Retrying ICCS creation after a previous failure.")
            self._create_iccs(is_retry=True)
            self.refresh_all()

    def _refresh_event_bar(self) -> None:
        bar = self.query_one("#event-bar", Static)
        try:
            with Session(engine) as session:
                event = self._get_current_event(session)
                iccs_status = (
                    " ● ICCS ready" if self._bound_iccs is not None else " ○ no ICCS"
                )
                time_str = fmt_timestamp(event.time) if event.time else "unknown"
                lat = f"{event.latitude:.3f}°" if event.latitude is not None else "?"
                lon = f"{event.longitude:.3f}°" if event.longitude is not None else "?"
                modified = (
                    f"  modified: {fmt_timestamp(event.last_modified)}"
                    if event.last_modified is not None
                    else ""
                )
                bar.update(
                    f"▶ {time_str}  |  {lat}, {lon}{modified}"
                    f"  [dim]{iccs_status}  e = switch event[/dim]"
                )
        except NoResultFound:
            with Session(engine) as session:
                has_events = session.exec(select(AimbatEvent)).first() is not None
            if has_events:
                bar.update("[red]No event selected — press e to select one[/red]")
            else:
                bar.update("[red]No data in project — press d to add data[/red]")
        except RuntimeError as exc:
            bar.update(f"[red]{exc}[/red]")

    # ------------------------------------------------------------------
    # Row event handlers
    # ------------------------------------------------------------------

    @on(ProjectPanel.RowActionChosen)
    def _project_row_action_chosen(self, message: ProjectPanel.RowActionChosen) -> None:
        self._handle_row_action(message.tab, message.item_id, message.action)

    @on(SeismogramPanel.RowActionChosen)
    def _seismogram_row_action_chosen(
        self, message: SeismogramPanel.RowActionChosen
    ) -> None:
        self._handle_row_action("tab-seismograms", message.item_id, message.action)

    @on(SnapshotPanel.ActionChosen)
    def _snapshot_action_chosen(self, message: SnapshotPanel.ActionChosen) -> None:
        if message.action == "preview_stack":
            self._preview_snapshot_plot(
                message.item_id, "stack", message.context, message.all_seismograms
            )
        elif message.action == "preview_image":
            self._preview_snapshot_plot(
                message.item_id, "image", message.context, message.all_seismograms
            )
        elif message.action == "save_results":
            self._save_snapshot_results(message.item_id)
        else:
            self._handle_row_action("tab-snapshots", message.item_id, message.action)

    # ------------------------------------------------------------------
    # Row-action menu helpers
    # ------------------------------------------------------------------

    def _handle_row_action(self, tab: str, item_id: str, action: str | None) -> None:
        if action == "delete":
            self._confirm_delete(tab, item_id)
        elif action == "select":
            self._select_event(item_id)
        elif action == "toggle_completed":
            self._toggle_event_completed(item_id)
        elif action == "view_seismograms":
            self._view_seismograms(tab, item_id)
        elif action == "rollback":
            self._confirm_rollback(item_id)
        elif action == "show_details":
            self._show_snapshot_details(item_id)
        elif action == "toggle_select":
            self._toggle_seismogram_bool(item_id, SeismogramParameter.SELECT)
        elif action == "toggle_flip":
            self._toggle_seismogram_bool(item_id, SeismogramParameter.FLIP)
        elif action == "reset":
            self._reset_seismogram_parameters(item_id)

    def _select_event(self, item_id: str) -> None:
        logger.debug(f"User selected event {item_id[:8]}.")
        self._current_event_id = uuid.UUID(item_id)
        self._create_iccs()
        self.refresh_all()
        self.notify("Event selected", timeout=2)

    def _toggle_event_completed(self, item_id: str) -> None:
        logger.debug(f"User toggled completed flag for event {item_id[:8]}.")
        try:
            with Session(engine) as session:
                event = session.get(AimbatEvent, uuid.UUID(item_id))
                if event is None:
                    return
                event.parameters.completed = not event.parameters.completed
                session.add(event)
                session.commit()
            self.refresh_all()
            self.notify("Completed flag toggled", timeout=2)
        except Exception as exc:
            self.notify(str(exc), severity="error")

    def _view_seismograms(self, tab: str, item_id: str) -> None:
        item_uuid = uuid.UUID(item_id)
        try:
            with self._suspend("View seismograms"):
                with Session(engine) as session:
                    if tab == "project-events":
                        event = session.get(AimbatEvent, item_uuid)
                        if event is None:
                            return
                        plot_seismograms(session, event, return_fig=False)
                    else:
                        station = session.get(AimbatStation, item_uuid)
                        if station is None:
                            return
                        plot_seismograms(session, station, return_fig=False)
        except Exception as exc:
            self.notify(str(exc), severity="error")

    def _toggle_seismogram_bool(self, item_id: str, param: SeismogramParameter) -> None:
        logger.debug(f"User toggled {param} for seismogram {item_id[:8]}.")
        try:
            seis_uuid = uuid.UUID(item_id)
            with Session(engine) as session:
                seis = session.get(AimbatSeismogram, seis_uuid)
                if seis is None:
                    raise ValueError(f"Seismogram {item_id} not found")
                new_value = not getattr(seis.parameters, param)
                set_seismogram_parameter(session, seis_uuid, param, new_value)
            if self._bound_iccs is not None:
                for iccs_seis in self._bound_iccs.iccs.seismograms:
                    if iccs_seis.extra.get("id") == seis_uuid:
                        setattr(iccs_seis, param, new_value)
                        self._bound_iccs.iccs.clear_cache()
                        self._bound_iccs.created_at = Timestamp.now("UTC")
                        break
            # Deliberately scoped: this only mutates the in-memory ICCS instance
            # and clears its cache, without re-upserting iccs_cc, so no other
            # panel's displayed data (quality panels, station cc_mean/cc_sem)
            # changes here. Also repeated once per seismogram during QC review,
            # so avoid the extra DB round trips a full refresh_all() would add.
            self.query_one(SeismogramPanel).refresh_data(
                self._current_event_id, self._bound_iccs
            )
            self.notify(f"{param} toggled", timeout=2)
        except Exception as exc:
            self.notify(str(exc), severity="error")

    def _reset_seismogram_parameters(self, item_id: str) -> None:
        logger.debug(f"User reset parameters for seismogram {item_id[:8]}.")
        try:
            with Session(engine) as session:
                reset_seismogram_parameters(session, uuid.UUID(item_id))
            self.refresh_all()
            self.notify("Seismogram parameters reset", timeout=2)
        except Exception as exc:
            self.notify(str(exc), severity="error")

    def _confirm_delete(self, tab: str, item_id: str) -> None:
        messages = {
            "project-events": "Delete this event and all its data?",
            "project-stations": "Delete this station and all its seismograms?",
            "tab-seismograms": "Delete this seismogram?",
            "tab-snapshots": "Delete this snapshot?",
        }
        msg = messages.get(tab)
        if not msg:
            return

        def on_confirm(confirmed: bool | None) -> None:
            if not confirmed:
                return
            try:
                if tab == "project-events":
                    logger.info(f"User confirmed deletion of event {item_id[:8]}.")
                    with Session(engine) as session:
                        delete_event(session, uuid.UUID(item_id))
                    if self._current_event_id == uuid.UUID(item_id):
                        self._current_event_id = None
                        self._bound_iccs = None
                    self.refresh_all()
                    self.notify("Event deleted", timeout=2)
                elif tab == "project-stations":
                    logger.info(f"User confirmed deletion of station {item_id[:8]}.")
                    with Session(engine) as session:
                        delete_station(session, uuid.UUID(item_id))
                    self._create_iccs()
                    self.refresh_all()
                    self.notify("Station deleted", timeout=2)
                elif tab == "tab-seismograms":
                    logger.info(f"User confirmed deletion of seismogram {item_id[:8]}.")
                    with Session(engine) as session:
                        delete_seismogram(session, uuid.UUID(item_id))
                    self._create_iccs()
                    self.refresh_all()
                    self.notify("Seismogram deleted", timeout=2)
                elif tab == "tab-snapshots":
                    logger.info(f"User confirmed deletion of snapshot {item_id[:8]}.")
                    with Session(engine) as session:
                        delete_snapshot(session, uuid.UUID(item_id))
                    self.refresh_all()
                    self.notify("Snapshot deleted", timeout=2)
            except Exception as exc:
                logger.exception(f"Deletion failed: {exc}")
                self.notify(str(exc), severity="error")

        self.push_screen(ConfirmModal(msg), on_confirm)

    def _show_snapshot_details(self, snap_id: str) -> None:
        try:
            with Session(engine) as session:
                snap = session.get(AimbatSnapshot, uuid.UUID(snap_id))
                if snap is None:
                    return
                data = snap.event_parameters_snapshot.model_dump(mode="json")
            rows: list[tuple[str, str]] = []
            for attr in AimbatEventParametersBase.model_fields:
                title = tui_display_title(AimbatEventParametersBase, attr)
                display = str(tui_cell(AimbatEventParametersBase, title, data[attr]))
                rows.append((title, display))
            self.push_screen(SnapshotDetailsModal(f"Snapshot  {snap_id[:8]}", rows))
        except Exception as exc:
            self.notify(str(exc), severity="error")

    def _save_snapshot_results(self, snap_id: str) -> None:
        default_name = f"results_{snap_id[:8]}.json"

        def on_path(path: Path | None) -> None:
            if path is None:
                return
            import json

            try:
                with Session(engine) as session:
                    data = dump_snapshot_results(session, uuid.UUID(snap_id))
                path.write_text(json.dumps(data, indent=2), encoding="utf-8")
                logger.info(f"Snapshot results saved to {path}.")
                self.notify(f"Results saved to {path.name}", timeout=3)
            except Exception as exc:
                logger.exception(f"Failed to save snapshot results: {exc}")
                self.notify(str(exc), severity="error")

        self.push_screen(
            FileSave(".", title="Save results", default_file=default_name), on_path
        )

    def _preview_snapshot_plot(
        self, snap_id: str, plot_type: str, context: bool, all_seis: bool
    ) -> None:
        logger.debug(f"User previewing {plot_type} plot for snapshot {snap_id[:8]}.")
        try:
            with self._suspend("Previewing snapshot"):
                with Session(engine) as session:
                    bound = build_iccs_from_snapshot(session, uuid.UUID(snap_id))
                if plot_type == "stack":
                    plot_stack(bound.iccs, context, all_seis, return_fig=False)
                else:
                    plot_matrix_image(bound.iccs, context, all_seis, return_fig=False)
        except Exception as exc:
            logger.exception(f"Snapshot preview failed: {exc}")
            self.notify(str(exc), severity="error")

    def _confirm_rollback(self, snap_id: str) -> None:
        def on_confirm(confirmed: bool | None) -> None:
            if not confirmed:
                return
            try:
                logger.info(f"User confirmed rollback to snapshot {snap_id[:8]}.")
                with Session(engine) as session:
                    rollback_to_snapshot(session, uuid.UUID(snap_id))
                self._create_iccs()
                self.refresh_all()
                if self._active_tab == "tab-snapshots":
                    self.query_one(TabbedContent).active = "tab-seismograms"
                self.notify("Rolled back to snapshot", timeout=3)
            except Exception as exc:
                logger.exception(f"Rollback failed: {exc}")
                self.notify(str(exc), severity="error")

        self.push_screen(ConfirmModal("Roll back to this snapshot?"), on_confirm)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_open_parameters(self) -> None:
        logger.debug("User opened parameters modal.")
        try:
            with Session(engine) as session:
                event = self._get_current_event(session)
                event_id = event.id
        except NoResultFound:
            self.notify("No event selected — press e to select one", severity="warning")
            return

        def on_close(changed: bool | None) -> None:
            if changed:
                logger.info("Parameters changed; recreating ICCS.")
                self._create_iccs()
                self.refresh_all()

        self.push_screen(ParametersModal(event_id), on_close)

    def action_switch_event(self) -> None:
        def on_result(result: tuple[uuid.UUID | None, bool] | None) -> None:
            selected_event_id, deleted_current_event = result or (None, False)
            if selected_event_id is not None:
                logger.debug(f"User switched to event {str(selected_event_id)[:8]}.")
                self._current_event_id = selected_event_id
                self._create_iccs()
            elif deleted_current_event:
                self._current_event_id = None
                self._bound_iccs = None
            self.refresh_all()

        self.push_screen(EventSwitcherModal(self._current_event_id), on_result)

    def action_add_data(self) -> None:
        actions = [(dt.value, dt.name.replace("_", " ")) for dt in DataType]

        def on_type(selected: str | None) -> None:
            if selected is None:
                return
            data_type = DataType(selected)
            suffixes = DATATYPE_SUFFIXES[data_type]
            label = data_type.name.replace("_", " ")

            def on_file(path: Path | None) -> None:
                if path is None:
                    return
                try:
                    with Session(engine) as session:
                        add_data_to_project(session, [path], data_type)
                        session.commit()
                    logger.info(f"User added data file: {path}.")
                    self.notify(f"Added: {path.name}", severity="information")
                    self.refresh_all()
                except Exception as exc:
                    logger.exception(f"Failed to add data file {path}: {exc}")
                    self.notify(str(exc), severity="error")

            self.push_screen(
                FileOpen(
                    ".",
                    title=f"Add {label}",
                    filters=Filters(
                        (f"{label} files", lambda p: p.suffix.lower() in suffixes),
                        ("All files", lambda _: True),
                    ),
                ),
                on_file,
            )

        self.push_screen(ActionMenuModal("Add Data", actions), on_type)

    def _require_iccs(self) -> bool:
        """Return True if ICCS is ready; show a contextual warning and return False otherwise."""
        if self._bound_iccs is not None:
            return True
        if self._current_event_id is not None:
            self.notify(
                "ICCS not ready — check event parameters (Parameters tab)",
                severity="warning",
            )
        else:
            self.notify("No event selected — press e to select one", severity="warning")
        return False

    def action_open_interactive_tools(self) -> None:
        if not self._require_iccs():
            return

        def on_result(result: tuple[str, bool, bool] | None) -> None:
            if result is not None:
                self._run_tool(*result)

        self.push_screen(InteractiveToolsModal(), on_result)

    def _run_tool(self, tool: str, context: bool, all_seis: bool) -> None:
        """Run an interactive tool, suspending Textual while matplotlib is active.

        Uses the long-lived ICCS instance (waveform data already loaded) and runs
        matplotlib on the main thread via App.suspend(), which is the correct
        Textual pattern for blocking terminal-adjacent processes.
        """
        logger.debug(
            f"User launched interactive tool '{tool}' (context={context}, all_seis={all_seis})."
        )
        if self._bound_iccs is None:
            self.notify("ICCS not ready — please wait", severity="warning")
            return
        label, fn = _TOOL_REGISTRY[tool]
        iccs = self._bound_iccs.iccs

        try:
            with self._suspend(label):
                with Session(engine) as session:
                    event = self._get_current_event(session)
                    fn(session, event, iccs, context, all_seis)
        except Exception as exc:
            logger.exception(f"Interactive tool '{tool}' raised: {exc}")
            self.notify(str(exc), severity="error")
            return

        # suspend() is synchronous, so the staleness poller cannot fire
        # between the session commit and this assignment.
        self._bound_iccs.created_at = Timestamp.now("UTC")
        self.refresh_all()
        self.notify("Done", timeout=2)

    def action_open_align(self) -> None:
        if not self._require_iccs():
            return

        def on_result(result: tuple[str, bool, bool, bool] | None) -> None:
            if result is not None:
                self._run_align_tool(self._bound_iccs, *result)

        self.push_screen(AlignModal(), on_result)

    @work(thread=True)
    def _run_align_tool(
        self,
        bound: BoundICCS,
        algorithm: str,
        autoflip: bool,
        autoselect: bool,
        all_seis: bool,
    ) -> None:
        """Run ICCS or MCCC in a background thread."""
        logger.debug(
            f"Alignment worker starting: {algorithm=}, {autoflip=}, {autoselect=}, {all_seis=}."
        )
        notify_msg = "Alignment complete"
        notify_severity: Literal["information", "warning", "error"] = "information"
        try:
            with Session(engine) as session:
                event = self._get_current_event(session)
                if algorithm == "iccs":
                    result = run_iccs(session, event, bound.iccs, autoflip, autoselect)
                    n = len(result.convergence)
                    status = "converged" if result.converged else "did not converge"
                    noun = "iteration" if n == 1 else "iterations"
                    notify_msg = f"ICCS {status} after {n} {noun}"
                    notify_severity = "information" if result.converged else "warning"
                elif algorithm == "mccc":
                    run_mccc(session, event, bound.iccs, all_seis)
                    notify_msg = "MCCC complete"
        except Exception as exc:
            logger.exception(f"Alignment worker error ({algorithm}): {exc}")
            self.call_from_thread(self.notify, str(exc), severity="error")
            return
        # Stamp created_at here, before posting to the event loop, so the
        # staleness poller cannot observe last_modified > created_at between
        # this call_from_thread and _post_align_complete actually running.
        bound.created_at = Timestamp.now("UTC")
        self.call_from_thread(self._post_align_complete, notify_msg, notify_severity)

    def _post_align_complete(
        self, msg: str, severity: Literal["information", "warning", "error"]
    ) -> None:
        self.refresh_all()
        self.notify(msg, severity=severity, timeout=4)

    def action_new_snapshot(self) -> None:
        def on_comment(comment: str | None) -> None:
            if comment is None:
                return
            try:
                logger.info(f"User creating snapshot with comment={comment!r}.")
                with Session(engine) as session:
                    event = self._get_current_event(session)
                    create_snapshot(session, event, comment or None)
                self.refresh_all()
                self.notify("Snapshot created", timeout=2)
            except Exception as exc:
                logger.exception(f"Snapshot creation failed: {exc}")
                self.notify(str(exc), severity="error")

        self.push_screen(SnapshotCommentModal(), on_comment)

    def action_vim_left(self) -> None:
        if not isinstance(self.screen, ModalScreen):
            self.query_one(TabbedContent).query_one(Tabs).action_previous_tab()

    def action_vim_right(self) -> None:
        if not isinstance(self.screen, ModalScreen):
            self.query_one(TabbedContent).query_one(Tabs).action_next_tab()

    def action_toggle_theme(self) -> None:
        self.theme = _LIGHT_THEME if self.theme == _DEFAULT_THEME else _DEFAULT_THEME

    def action_show_help(self) -> None:
        self.push_screen(HelpModal(self._active_tab))

    def action_refresh(self) -> None:
        logger.debug("User triggered manual refresh.")
        self.refresh_all()
        self.notify("Refreshed", timeout=1)


def main() -> None:
    """Entry point for the AIMBAT TUI.

    Raises:
        RuntimeError: If the TUI exited due to an unhandled exception (e.g.
            a `SchemaStaleWarning` promoted to an error by
            `AIMBAT_STRICT_SCHEMA_CHECK`). Textual catches exceptions raised
            inside its own message loop and shows its own crash screen
            rather than letting them propagate - `App.run()` then returns
            normally, which would otherwise report a successful (exit 0)
            process despite the crash. Checking `return_code` (Textual's own
            documented mechanism for this - see `App.return_code`) and
            re-raising here restores the same hard-failure contract every
            other AIMBAT command already has via `handle_issues`.
    """
    app = AimbatTUI()
    app.run()
    if app.return_code:
        raise RuntimeError(
            "AIMBAT TUI exited after an unhandled error - see the crash "
            "report above for details."
        )


if __name__ == "__main__":
    main()
