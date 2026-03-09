"""AIMBAT Terminal User Interface application."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Generator
from contextlib import contextmanager, suppress
from pathlib import Path

from pandas import Timedelta, Timestamp
from rich.console import Console
from rich.panel import Panel
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, select
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Rule,
    Static,
    TabbedContent,
    TabPane,
    Tabs,
)
from textual_fspicker import FileOpen, Filters

from pysmo.tools.iccs import ICCS

from aimbat import settings
from aimbat._tui._widgets import VimDataTable
from aimbat._tui.modals import (
    ActionMenuModal,
    AlignModal,
    ConfirmModal,
    EventSwitcherModal,
    InteractiveToolsModal,
    NoProjectModal,
    ParametersModal,
    SnapshotActionMenuModal,
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
    delete_event_by_id,
    delete_seismogram_by_id,
    delete_snapshot_by_id,
    delete_station_by_id,
    get_stations_with_event_and_seismogram_count,
    reset_seismogram_parameters_by_id,
    rollback_to_snapshot_by_id,
    run_iccs,
    run_mccc,
)
from aimbat.core._project import _project_exists
from aimbat.db import engine
from aimbat.io import DATATYPE_SUFFIXES, DataType
from aimbat.models import AimbatEvent, AimbatSeismogram, AimbatSnapshot, AimbatStation
from aimbat.models._parameters import (
    AimbatEventParametersBase,
)  # used in _show_snapshot_details
from aimbat.plot import (
    plot_matrix_image,
    plot_seismograms,
    plot_stack,
    update_min_ccnorm,
    update_pick,
    update_timewindow,
)

_DEFAULT_THEME = settings.tui_dark_theme
_LIGHT_THEME = settings.tui_light_theme


# Extend this dict to add new per-row actions to any tab.
_TAB_ROW_ACTIONS: dict[str, list[tuple[str, str]]] = {
    "project-events": [
        ("select", "Select event"),
        ("toggle_completed", "Toggle completed"),
        ("view_seismograms", "View seismograms"),
        ("delete", "Delete event"),
    ],
    "project-stations": [
        ("view_seismograms", "View seismograms"),
        ("delete", "Delete station"),
    ],
    "tab-seismograms": [
        ("toggle_select", "Toggle select"),
        ("toggle_flip", "Toggle flip"),
        ("reset", "Reset parameters"),
        ("delete", "Delete seismogram"),
    ],
}


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
    update_pick(
        session,
        iccs,
        context,
        all_seismograms=all_seismograms,
        use_matrix_image=False,
        return_fig=False,
    )


def _tool_window(
    session: Session,
    event: AimbatEvent,
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
) -> None:
    update_timewindow(
        session,
        event,
        iccs,
        context,
        all_seismograms=all_seismograms,
        use_matrix_image=False,
        return_fig=False,
    )


def _tool_ccnorm(
    session: Session,
    event: AimbatEvent,
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
) -> None:
    update_min_ccnorm(
        session,
        event,
        iccs,
        context,
        all_seismograms=all_seismograms,
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
    "ccnorm": ("Min CC norm", _tool_ccnorm),
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
        Binding("H", "vim_left", "Vim left", show=False),
        Binding("L", "vim_right", "Vim right", show=False),
        Binding("q", "quit", "Quit", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="event-bar")
        with TabbedContent(initial="tab-project"):
            with TabPane("Project", id="tab-project"):
                yield Static("Events", classes="project-table-title")
                yield VimDataTable(id="project-event-table")
                yield Rule(classes="project-divider")
                yield Static("Stations", classes="project-table-title")
                yield VimDataTable(id="project-station-table")
            with TabPane("Seismograms", id="tab-seismograms"):
                yield VimDataTable(id="seismogram-table")
            with TabPane("Snapshots", id="tab-snapshots"):
                yield VimDataTable(id="snapshot-table")
        yield Footer()

    def on_mount(self) -> None:
        self._bound_iccs: BoundICCS | None = None
        self._iccs_creating: bool = False
        self._iccs_last_modified_seen: Timestamp | None = None
        self._current_event_id: uuid.UUID | None = None
        self._active_tab: str = "tab-seismograms"

        self.theme = _DEFAULT_THEME

        self._setup_project_tables()
        self._setup_seismogram_table()
        self._setup_snapshot_table()

        self.set_interval(5, self._check_iccs_staleness)

        if not _project_exists(engine):
            self.push_screen(NoProjectModal(), self._on_no_project_modal)
        else:
            self._create_iccs()
            self.refresh_all()

    def _on_no_project_modal(self, create: bool | None) -> None:
        if create:
            create_project(engine)
            self._create_iccs()
            self.refresh_all()
        else:
            self.exit()

    @on(TabbedContent.TabActivated)
    def on_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        if event.pane.id:
            self._active_tab = event.pane.id
            self.refresh_bindings()
            if not isinstance(self.focused, Tabs):
                with suppress(Exception):
                    event.pane.query_one(DataTable).focus()

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

        Raises ``NoResultFound`` when no event has been selected yet.
        Clears a stale ``_current_event_id`` if the referenced event no longer exists.
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

        If ``label`` is given, a panel is shown with a "close matplotlib to
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

    def _create_iccs(self) -> None:
        """Discard the existing ICCS instance and create a new one in a background worker.

        ICCS construction reads waveform data, so it must not block the asyncio event loop.
        Concurrent calls are ignored — only one worker runs at a time.
        """
        if self._iccs_creating:
            return
        self._iccs_creating = True
        self._bound_iccs = None
        self._worker_create_iccs()

    @work(thread=True)
    def _worker_create_iccs(self) -> None:
        """Background worker: create ICCS instance without blocking the UI."""
        try:
            with Session(engine) as session:
                event = self._get_current_event(session)
                bound_iccs = create_iccs_instance(session, event)
        except (NoResultFound, RuntimeError):
            self.call_from_thread(setattr, self, "_iccs_creating", False)
            return
        except Exception as exc:
            self.call_from_thread(
                self.notify, f"ICCS init failed: {exc}", severity="error"
            )
            self.call_from_thread(setattr, self, "_iccs_creating", False)
            return
        self.call_from_thread(self._assign_iccs, bound_iccs)

    def _assign_iccs(self, bound_iccs: BoundICCS) -> None:
        """Main-thread callback: store the new BoundICCS instance and refresh status."""
        self._iccs_creating = False
        self._bound_iccs = bound_iccs
        self._refresh_event_bar()
        self._refresh_seismograms()

    # ------------------------------------------------------------------
    # Table setup
    # ------------------------------------------------------------------

    def _setup_project_tables(self) -> None:
        et = self.query_one("#project-event-table", DataTable)
        et.cursor_type = "row"
        et.add_columns(
            " ",
            "ID",
            "Time (UTC)",
            "Lat °",
            "Lon °",
            "Depth km",
            "Stations",
            "Seismograms",
            "Completed",
        )
        st = self.query_one("#project-station-table", DataTable)
        st.cursor_type = "row"
        st.add_columns(
            "ID",
            "Network",
            "Name",
            "Location",
            "Channel",
            "Lat °",
            "Lon °",
            "Elev m",
            "Seismograms",
        )

    def _setup_seismogram_table(self) -> None:
        t = self.query_one("#seismogram-table", DataTable)
        t.cursor_type = "row"
        t.add_columns(
            "ID", "Network", "Station", "Channel", "Select", "Flip", "Δt (s)", "CC"
        )

    def _setup_snapshot_table(self) -> None:
        t = self.query_one("#snapshot-table", DataTable)
        t.cursor_type = "row"
        t.add_columns("ID", "Date (UTC)", "Comment", "Seismograms", "Select", "Flip")

    # ------------------------------------------------------------------
    # Data refresh
    # ------------------------------------------------------------------

    def refresh_all(self) -> None:
        self.refresh_bindings()
        self._refresh_event_bar()
        self._refresh_project()
        self._refresh_seismograms()
        self._refresh_snapshots()

    def _refresh_project(self) -> None:
        et = self.query_one("#project-event-table", DataTable)
        st = self.query_one("#project-station-table", DataTable)
        et_saved, st_saved = et.cursor_row, st.cursor_row
        et.clear()
        st.clear()
        with suppress(Exception):
            with Session(engine) as session:
                events = session.exec(select(AimbatEvent)).all()
                stations = get_stations_with_event_and_seismogram_count(session)
                for event in events:
                    marker = "▶" if event.id == self._current_event_id else " "
                    short_id = str(event.id)[:8]
                    time_str = str(event.time)[:19] if event.time else "—"
                    lat = f"{event.latitude:.3f}" if event.latitude is not None else "—"
                    lon = (
                        f"{event.longitude:.3f}" if event.longitude is not None else "—"
                    )
                    depth = (
                        f"{event.depth / 1000:.1f}" if event.depth is not None else "—"
                    )
                    done = "✓" if event.parameters.completed else " "
                    et.add_row(
                        marker,
                        short_id,
                        time_str,
                        lat,
                        lon,
                        depth,
                        str(event.station_count),
                        str(event.seismogram_count),
                        done,
                        key=str(event.id),
                    )
                for station, seis_count, _event_count in stations:
                    short_id = str(station.id)[:8]
                    lat = (
                        f"{station.latitude:.3f}"
                        if station.latitude is not None
                        else "—"
                    )
                    lon = (
                        f"{station.longitude:.3f}"
                        if station.longitude is not None
                        else "—"
                    )
                    elev = (
                        f"{station.elevation:.0f}"
                        if station.elevation is not None
                        else "—"
                    )
                    st.add_row(
                        short_id,
                        station.network,
                        station.name,
                        station.location or "—",
                        station.channel,
                        lat,
                        lon,
                        elev,
                        str(seis_count),
                        key=str(station.id),
                    )
        if et.row_count > 0:
            et.move_cursor(row=min(et_saved, et.row_count - 1))
        if st.row_count > 0:
            st.move_cursor(row=min(st_saved, st.row_count - 1))

    def _check_iccs_staleness(self) -> None:
        """Trigger ICCS recreation if the current event has been modified externally.

        When ICCS creation previously failed (e.g. due to an invalid parameter set via
        the CLI), retries whenever ``event.last_modified`` changes. On any detected
        change the full UI is refreshed so panels reflect the new DB state immediately.
        """
        try:
            with Session(engine) as session:
                event = self._get_current_event(session)
                changed = False
                if self._bound_iccs is not None:
                    if self._bound_iccs.is_stale(event):
                        self._iccs_last_modified_seen = event.last_modified
                        self._create_iccs()
                        changed = True
                elif event.last_modified != self._iccs_last_modified_seen:
                    self._iccs_last_modified_seen = event.last_modified
                    self._create_iccs()
                    changed = True
        except (NoResultFound, RuntimeError):
            return
        if changed:
            self.refresh_all()

    def _refresh_event_bar(self) -> None:
        bar = self.query_one("#event-bar", Static)
        try:
            with Session(engine) as session:
                event = self._get_current_event(session)
                iccs_status = (
                    " ● ICCS ready" if self._bound_iccs is not None else " ○ no ICCS"
                )
                time_str = str(event.time)[:19] if event.time else "unknown"
                lat = f"{event.latitude:.3f}°" if event.latitude is not None else "?"
                lon = f"{event.longitude:.3f}°" if event.longitude is not None else "?"
                modified = (
                    f"  modified: {str(event.last_modified)[:19]}"
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

    def _refresh_seismograms(self) -> None:
        table = self.query_one("#seismogram-table", DataTable)
        saved_row = table.cursor_row
        table.clear()

        ccnorm_map: dict[uuid.UUID, float] = {}
        if self._bound_iccs is not None:
            with suppress(Exception):
                for iccs_seis, ccnorm in zip(
                    self._bound_iccs.iccs.seismograms, self._bound_iccs.iccs.ccnorms
                ):
                    ccnorm_map[iccs_seis.extra["id"]] = float(ccnorm)

        with suppress(NoResultFound, RuntimeError):
            with Session(engine) as session:
                event = self._get_current_event(session)
                seismograms = sorted(
                    event.seismograms,
                    key=lambda s: ccnorm_map.get(s.id, -2.0),
                    reverse=True,
                )
                for seis in seismograms:
                    station = seis.station
                    params = seis.parameters
                    short_id = str(seis.id)[:8]
                    net = station.network if station else "—"
                    name = station.name if station else "—"
                    chan = station.channel if station else "—"
                    selected = "✓" if params and params.select else "✗"
                    flipped = "↕" if params and params.flip else " "
                    t1 = params.t1 if params else None
                    if seis.t0 and t1:
                        dt = f"{(t1 - seis.t0).total_seconds():.3f}"
                    else:
                        dt = "—"
                    cc = f"{ccnorm_map[seis.id]:.3f}" if seis.id in ccnorm_map else "—"
                    table.add_row(
                        short_id,
                        net,
                        name,
                        chan,
                        selected,
                        flipped,
                        dt,
                        cc,
                        key=str(seis.id),
                    )
        if table.row_count > 0:
            table.move_cursor(row=min(saved_row, table.row_count - 1))

    def _refresh_snapshots(self) -> None:
        table = self.query_one("#snapshot-table", DataTable)
        saved_row = table.cursor_row
        table.clear()
        with suppress(NoResultFound, RuntimeError):
            with Session(engine) as session:
                event = self._get_current_event(session)
                for snap in event.snapshots:
                    short_id = str(snap.id)[:8]
                    date_str = str(snap.date)[:19] if snap.date else "—"
                    comment = snap.comment or "—"
                    seismogram_count = str(snap.seismogram_count)
                    selected_count = str(snap.selected_seismogram_count)
                    flipped_count = str(snap.flipped_seismogram_count)
                    table.add_row(
                        short_id,
                        date_str,
                        comment,
                        seismogram_count,
                        selected_count,
                        flipped_count,
                        key=str(snap.id),
                    )
        if table.row_count > 0:
            table.move_cursor(row=min(saved_row, table.row_count - 1))

    # ------------------------------------------------------------------
    # Row event handlers
    # ------------------------------------------------------------------

    @on(DataTable.RowSelected, "#project-event-table")
    def project_event_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key.value:
            self._open_row_action_menu(
                "project-events",
                event.row_key.value,
                f"Event  {event.row_key.value[:8]}",
            )

    @on(DataTable.RowSelected, "#project-station-table")
    def project_station_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key.value:
            self._open_row_action_menu(
                "project-stations",
                event.row_key.value,
                f"Station  {event.row_key.value[:8]}",
            )

    @on(DataTable.RowSelected, "#seismogram-table")
    def seismogram_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key.value:
            self._open_row_action_menu(
                "tab-seismograms",
                event.row_key.value,
                f"Seismogram  {event.row_key.value[:8]}",
            )

    @on(DataTable.RowSelected, "#snapshot-table")
    def snapshot_row_selected(self, event: DataTable.RowSelected) -> None:
        snap_id = event.row_key.value
        if not snap_id:
            return

        def on_action(result: tuple[str, bool, bool] | None) -> None:
            if result is None:
                return
            action, context, all_seis = result
            if action == "preview_stack":
                self._preview_snapshot_plot(snap_id, "stack", context, all_seis)
            elif action == "preview_image":
                self._preview_snapshot_plot(snap_id, "image", context, all_seis)
            else:
                self._handle_row_action("tab-snapshots", snap_id, action)

        self.push_screen(SnapshotActionMenuModal(f"Snapshot  {snap_id[:8]}"), on_action)

    # ------------------------------------------------------------------
    # Row-action menu helpers
    # ------------------------------------------------------------------

    def _open_row_action_menu(self, tab: str, item_id: str, title: str) -> None:
        actions = _TAB_ROW_ACTIONS.get(tab, [])
        if not actions:
            return

        def on_action(action: str | None) -> None:
            self._handle_row_action(tab, item_id, action)

        self.push_screen(ActionMenuModal(title, actions), on_action)

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
        self._current_event_id = uuid.UUID(item_id)
        self._create_iccs()
        self.refresh_all()
        self.notify("Event selected", timeout=2)

    def _toggle_event_completed(self, item_id: str) -> None:
        try:
            with Session(engine) as session:
                event = session.get(AimbatEvent, uuid.UUID(item_id))
                if event is None:
                    return
                event.parameters.completed = not event.parameters.completed
                session.add(event)
                session.commit()
            self._refresh_project()
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
        try:
            seis_uuid = uuid.UUID(item_id)
            with Session(engine) as session:
                seis = session.get(AimbatSeismogram, seis_uuid)
                if seis is None:
                    raise ValueError(f"Seismogram {item_id} not found")
                new_value = not getattr(seis.parameters, param)
                setattr(seis.parameters, param, new_value)
                session.add(seis)
                session.commit()
            if self._bound_iccs is not None:
                for iccs_seis in self._bound_iccs.iccs.seismograms:
                    if iccs_seis.extra.get("id") == seis_uuid:
                        setattr(iccs_seis, param, new_value)
                        self._bound_iccs.iccs.clear_cache()
                        self._bound_iccs.created_at = Timestamp.now("UTC")
                        break
            self._refresh_seismograms()
            self.notify(f"{param} toggled", timeout=2)
        except Exception as exc:
            self.notify(str(exc), severity="error")

    def _reset_seismogram_parameters(self, item_id: str) -> None:
        try:
            with Session(engine) as session:
                reset_seismogram_parameters_by_id(session, uuid.UUID(item_id))
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
                    with Session(engine) as session:
                        delete_event_by_id(session, uuid.UUID(item_id))
                    if self._current_event_id == uuid.UUID(item_id):
                        self._current_event_id = None
                        self._bound_iccs = None
                    self.refresh_all()
                    self.notify("Event deleted", timeout=2)
                elif tab == "project-stations":
                    with Session(engine) as session:
                        delete_station_by_id(session, uuid.UUID(item_id))
                    self._create_iccs()
                    self.refresh_all()
                    self.notify("Station deleted", timeout=2)
                elif tab == "tab-seismograms":
                    with Session(engine) as session:
                        delete_seismogram_by_id(session, uuid.UUID(item_id))
                    self._create_iccs()
                    self.refresh_all()
                    self.notify("Seismogram deleted", timeout=2)
                elif tab == "tab-snapshots":
                    with Session(engine) as session:
                        delete_snapshot_by_id(session, uuid.UUID(item_id))
                    self._refresh_snapshots()
                    self.notify("Snapshot deleted", timeout=2)
            except Exception as exc:
                self.notify(str(exc), severity="error")

        self.push_screen(ConfirmModal(msg), on_confirm)

    def _show_snapshot_details(self, snap_id: str) -> None:
        try:
            with Session(engine) as session:
                snap = session.get(AimbatSnapshot, uuid.UUID(snap_id))
                if snap is None:
                    return
                p = snap.event_parameters_snapshot
                rows: list[tuple[str, str]] = []
                for attr, field_info in AimbatEventParametersBase.model_fields.items():
                    value = getattr(p, attr)
                    if isinstance(value, bool):
                        display = "✓" if value else "✗"
                    elif isinstance(value, Timedelta):
                        display = f"{value.total_seconds():.2f}"
                    else:
                        display = f"{value}"
                    label = field_info.title or attr
                    rows.append((label, display))
            self.push_screen(SnapshotDetailsModal(f"Snapshot  {snap_id[:8]}", rows))
        except Exception as exc:
            self.notify(str(exc), severity="error")

    def _preview_snapshot_plot(
        self, snap_id: str, plot_type: str, context: bool, all_seis: bool
    ) -> None:
        try:
            with self._suspend("Previewing snapshot"):
                with Session(engine) as session:
                    bound = build_iccs_from_snapshot(session, uuid.UUID(snap_id))
                if plot_type == "stack":
                    plot_stack(bound.iccs, context, all_seis, return_fig=False)
                else:
                    plot_matrix_image(bound.iccs, context, all_seis, return_fig=False)
        except Exception as exc:
            self.notify(str(exc), severity="error")

    def _confirm_rollback(self, snap_id: str) -> None:
        def on_confirm(confirmed: bool | None) -> None:
            if not confirmed:
                return
            try:
                with Session(engine) as session:
                    rollback_to_snapshot_by_id(session, uuid.UUID(snap_id))
                self._create_iccs()
                self.refresh_all()
                self.notify("Rolled back to snapshot", timeout=3)
            except Exception as exc:
                self.notify(str(exc), severity="error")

        self.push_screen(ConfirmModal("Roll back to this snapshot?"), on_confirm)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_open_parameters(self) -> None:
        try:
            with Session(engine) as session:
                event = self._get_current_event(session)
                event_id = event.id
        except NoResultFound:
            self.notify("No event selected — press e to select one", severity="warning")
            return

        def on_close(changed: bool | None) -> None:
            if changed:
                self._create_iccs()
                self.refresh_all()

        self.push_screen(ParametersModal(event_id), on_close)

    def action_switch_event(self) -> None:
        def on_result(result: uuid.UUID | None) -> None:
            if result is not None:
                self._current_event_id = result
                self._create_iccs()
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
                        add_data_to_project(
                            session, [path], data_type, disable_progress_bar=True
                        )
                        session.commit()
                    self.notify(f"Added: {path.name}", severity="information")
                    self.refresh_all()
                except Exception as exc:
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
            self.notify(str(exc), severity="error")
            return
        self._bound_iccs.created_at = Timestamp.now("UTC")
        self._refresh_seismograms()
        self._refresh_event_bar()
        self.notify("Done", timeout=2)

    def action_open_align(self) -> None:
        if not self._require_iccs():
            return

        def on_result(result: tuple[str, bool, bool, bool] | None) -> None:
            if result is not None:
                self._run_align_tool(self._bound_iccs.iccs, *result)  # type: ignore[union-attr]

        self.push_screen(AlignModal(), on_result)

    @work(thread=True)
    def _run_align_tool(
        self,
        iccs: ICCS,
        algorithm: str,
        autoflip: bool,
        autoselect: bool,
        all_seis: bool,
    ) -> None:
        """Run ICCS or MCCC in a background thread."""
        try:
            with Session(engine) as session:
                if algorithm == "iccs":
                    run_iccs(session, iccs, autoflip, autoselect)
                elif algorithm == "mccc":
                    event = self._get_current_event(session)
                    run_mccc(session, event, iccs, all_seis)
        except Exception as exc:
            self.call_from_thread(self.notify, str(exc), severity="error")
            return
        self.call_from_thread(self._post_align_complete)

    def _post_align_complete(self) -> None:
        # Acknowledge our own writes (t1/flip/select written back by ICCS/MCCC)
        # so the staleness check doesn't recreate an ICCS we just ran.
        if self._bound_iccs is not None:
            self._bound_iccs.created_at = Timestamp.now("UTC")
        self.refresh_all()
        self.notify("Alignment complete", timeout=3)

    def action_new_snapshot(self) -> None:
        def on_comment(comment: str | None) -> None:
            if comment is None:
                return
            try:
                with Session(engine) as session:
                    event = self._get_current_event(session)
                    create_snapshot(session, event, comment or None)
                self._refresh_snapshots()
                self.notify("Snapshot created", timeout=2)
            except Exception as exc:
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

    def action_refresh(self) -> None:
        self.refresh_all()
        self.notify("Refreshed", timeout=1)


def main() -> None:
    """Entry point for the AIMBAT TUI."""
    AimbatTUI().run()


if __name__ == "__main__":
    main()
