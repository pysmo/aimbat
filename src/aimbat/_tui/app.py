"""AIMBAT Terminal User Interface application."""

from __future__ import annotations

import uuid
from pathlib import Path

from pydantic import ValidationError

from rich.console import Console
from rich.panel import Panel

from pandas import Timedelta
from pysmo.tools.iccs import ICCS
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
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
from textual_fspicker import FileOpen, Filters

from aimbat._types import EventParameter, SeismogramParameter
from aimbat.models._parameters import AimbatEventParametersBase
from aimbat.core import (
    add_data_to_project,
    create_iccs_instance,
    create_snapshot,
    delete_seismogram_by_id,
    reset_seismogram_parameters_by_id,
    sync_iccs_parameters,
    delete_snapshot_by_id,
    delete_station_by_id,
    get_active_event,
    rollback_to_snapshot_by_id,
    run_iccs,
    run_mccc,
    set_event_parameter,
    update_min_ccnorm,
    update_pick,
    update_timewindow,
)
from aimbat import settings
from aimbat.db import engine
from aimbat.io import DataType, DATATYPE_SUFFIXES
from aimbat.models import AimbatSeismogram, AimbatSnapshot
from aimbat._tui._widgets import VimDataTable
from aimbat._tui.modals import (
    ActionMenuModal,
    AlignModal,
    ConfirmModal,
    EventSwitcherModal,
    InteractiveToolsModal,
    ParameterInputModal,
    SnapshotCommentModal,
    SnapshotDetailsModal,
)

_DEFAULT_THEME = settings.tui_dark_theme
_LIGHT_THEME = settings.tui_light_theme


# Extend this dict to add new per-row actions to any tab.
_TAB_ROW_ACTIONS: dict[str, list[tuple[str, str]]] = {
    "tab-seismograms": [
        ("toggle_select", "Toggle select"),
        ("toggle_flip", "Toggle flip"),
        ("reset", "Reset parameters"),
        ("delete", "Delete seismogram"),
    ],
    "tab-stations": [("delete", "Delete station and all seismograms")],
    "tab-snapshots": [
        ("show_details", "Show details"),
        ("rollback", "Rollback to this snapshot"),
        ("delete", "Delete snapshot"),
    ],
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
        Binding("p", "open_interactive_tools", "Interactive Tools", show=True),
        Binding("a", "open_align", "Align", show=True),
        Binding("n", "new_snapshot", "New Snapshot", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("t", "toggle_theme", "Theme", show=True),
        Binding("H", "vim_left", "Vim left", show=False),
        Binding("L", "vim_right", "Vim right", show=False),
        Binding("q", "quit", "Quit", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="event-bar")
        with TabbedContent(initial="tab-seismograms"):
            with TabPane("Seismograms", id="tab-seismograms"):
                yield VimDataTable(id="seismogram-table")
            with TabPane("Parameters", id="tab-parameters"):
                yield VimDataTable(id="parameter-table")
            with TabPane("Stations", id="tab-stations"):
                yield VimDataTable(id="station-table")
            with TabPane("Snapshots", id="tab-snapshots"):
                yield VimDataTable(id="snapshot-table")
        yield Footer()

    def on_mount(self) -> None:
        self._iccs: ICCS | None = None
        self._active_tab: str = "tab-seismograms"

        self.theme = _DEFAULT_THEME

        self._setup_seismogram_table()
        self._setup_parameter_table()
        self._setup_station_table()
        self._setup_snapshot_table()

        self._create_iccs()
        self.refresh_all()

    @on(TabbedContent.TabActivated)
    def on_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        if event.pane.id:
            self._active_tab = event.pane.id
            self.refresh_bindings()
            if not isinstance(self.focused, Tabs):
                try:
                    event.pane.query_one(DataTable).focus()
                except Exception:
                    pass

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        tab = getattr(self, "_active_tab", "")
        if action == "new_snapshot":
            return True if tab == "tab-snapshots" else False
        return True

    # ------------------------------------------------------------------
    # ICCS lifecycle
    # ------------------------------------------------------------------

    def _create_iccs(self) -> None:
        """Discard the existing ICCS instance and create a new one in a background worker.

        ICCS construction reads waveform data, so it must not block the asyncio event loop.
        """
        self._iccs = None
        self._worker_create_iccs()

    @work(thread=True)
    def _worker_create_iccs(self) -> None:
        """Background worker: create ICCS instance without blocking the UI."""
        try:
            with Session(engine) as session:
                new_iccs = create_iccs_instance(session)
        except (NoResultFound, RuntimeError):
            return
        except Exception as exc:
            self.call_from_thread(
                self.notify, f"ICCS init failed: {exc}", severity="error"
            )
            return
        self.call_from_thread(self._assign_iccs, new_iccs)

    def _assign_iccs(self, iccs: ICCS) -> None:
        """Main-thread callback: store the new ICCS instance and refresh status."""
        self._iccs = iccs
        self._refresh_event_bar()
        self._refresh_seismograms()

    # ------------------------------------------------------------------
    # Table setup
    # ------------------------------------------------------------------

    def _setup_seismogram_table(self) -> None:
        t = self.query_one("#seismogram-table", DataTable)
        t.cursor_type = "row"
        t.add_columns(
            "ID", "Network", "Station", "Channel", "Select", "Flip", "Δt (s)", "CC"
        )

    def _setup_parameter_table(self) -> None:
        t = self.query_one("#parameter-table", DataTable)
        t.cursor_type = "row"
        t.add_columns("Parameter", "Value", "Description")

    def _setup_station_table(self) -> None:
        t = self.query_one("#station-table", DataTable)
        t.cursor_type = "row"
        t.add_columns(
            "ID", "Network", "Name", "Location", "Channel", "Lat °", "Lon °", "Elev m"
        )

    def _setup_snapshot_table(self) -> None:
        t = self.query_one("#snapshot-table", DataTable)
        t.cursor_type = "row"
        t.add_columns("ID", "Date (UTC)", "Comment", "Seismograms", "Select", "Flip")

    # ------------------------------------------------------------------
    # Data refresh
    # ------------------------------------------------------------------

    def refresh_all(self) -> None:
        self._refresh_event_bar()
        self._refresh_seismograms()
        self._refresh_parameters()
        self._refresh_stations()
        self._refresh_snapshots()

    def _refresh_event_bar(self) -> None:
        bar = self.query_one("#event-bar", Static)
        iccs_status = " ● ICCS ready" if self._iccs is not None else " ○ no ICCS"
        try:
            with Session(engine) as session:
                event = get_active_event(session)
                time_str = str(event.time)[:19] if event.time else "unknown"
                lat = f"{event.latitude:.3f}°" if event.latitude is not None else "?"
                lon = f"{event.longitude:.3f}°" if event.longitude is not None else "?"
                depth = (
                    f"  depth {event.depth / 1000:.1f} km"
                    if event.depth is not None
                    else ""
                )
                bar.update(
                    f"Active event: {time_str}  |  {lat}, {lon}{depth}"
                    f"  [dim]{iccs_status}  e = switch event[/dim]"
                )
        except NoResultFound:
            bar.update("[red]No active event — press e to select one[/red]")
        except RuntimeError as exc:
            bar.update(f"[red]{exc}[/red]")

    def _refresh_seismograms(self) -> None:
        table = self.query_one("#seismogram-table", DataTable)
        saved_row = table.cursor_row
        table.clear()

        ccnorm_map: dict[uuid.UUID, float] = {}
        if self._iccs is not None:
            try:
                for iccs_seis, ccnorm in zip(
                    self._iccs.seismograms, self._iccs.ccnorms
                ):
                    ccnorm_map[iccs_seis.extra["id"]] = float(ccnorm)
            except Exception:
                pass

        try:
            with Session(engine) as session:
                event = get_active_event(session)
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
        except (NoResultFound, RuntimeError):
            pass
        if table.row_count > 0:
            table.move_cursor(row=min(saved_row, table.row_count - 1))

    def _refresh_parameters(self) -> None:
        table = self.query_one("#parameter-table", DataTable)
        saved_row = table.cursor_row
        table.clear()
        try:
            with Session(engine) as session:
                event = get_active_event(session)
                p = event.parameters
                for attr, field_info in AimbatEventParametersBase.model_fields.items():
                    value = getattr(p, attr)
                    if isinstance(value, bool):
                        display = "✓" if value else "✗"
                    elif isinstance(value, Timedelta):
                        display = f"{value.total_seconds():.2f}"
                    else:
                        display = f"{value}"
                    label = field_info.title or attr
                    desc = field_info.description or ""
                    table.add_row(label, display, desc, key=attr)
        except (NoResultFound, RuntimeError):
            pass
        if table.row_count > 0:
            table.move_cursor(row=min(saved_row, table.row_count - 1))

    def _refresh_stations(self) -> None:
        table = self.query_one("#station-table", DataTable)
        saved_row = table.cursor_row
        table.clear()
        try:
            with Session(engine) as session:
                event = get_active_event(session)
                seen: set[uuid.UUID] = set()
                for seis in event.seismograms:
                    st = seis.station
                    if st and st.id not in seen:
                        seen.add(st.id)
                        short_id = str(st.id)[:8]
                        lat = f"{st.latitude:.3f}" if st.latitude is not None else "—"
                        lon = f"{st.longitude:.3f}" if st.longitude is not None else "—"
                        elev = (
                            f"{st.elevation:.0f}" if st.elevation is not None else "—"
                        )
                        table.add_row(
                            short_id,
                            st.network,
                            st.name,
                            st.location or "—",
                            st.channel,
                            lat,
                            lon,
                            elev,
                            key=str(st.id),
                        )
        except (NoResultFound, RuntimeError):
            pass
        if table.row_count > 0:
            table.move_cursor(row=min(saved_row, table.row_count - 1))

    def _refresh_snapshots(self) -> None:
        table = self.query_one("#snapshot-table", DataTable)
        saved_row = table.cursor_row
        table.clear()
        try:
            with Session(engine) as session:
                event = get_active_event(session)
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
        except (NoResultFound, RuntimeError):
            pass
        if table.row_count > 0:
            table.move_cursor(row=min(saved_row, table.row_count - 1))

    # ------------------------------------------------------------------
    # Parameter editing
    # ------------------------------------------------------------------

    @on(DataTable.RowSelected, "#seismogram-table")
    def seismogram_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key.value:
            self._open_row_action_menu(
                "tab-seismograms",
                event.row_key.value,
                f"Seismogram  {event.row_key.value[:8]}",
            )

    @on(DataTable.RowSelected, "#station-table")
    def station_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key.value:
            self._open_row_action_menu(
                "tab-stations",
                event.row_key.value,
                f"Station  {event.row_key.value[:8]}",
            )

    @on(DataTable.RowSelected, "#snapshot-table")
    def snapshot_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key.value:
            self._open_row_action_menu(
                "tab-snapshots",
                event.row_key.value,
                f"Snapshot  {event.row_key.value[:8]}",
            )

    @on(DataTable.RowSelected, "#parameter-table")
    def parameter_row_selected(self, event: DataTable.RowSelected) -> None:
        attr = event.row_key.value
        if not attr:
            return
        self._edit_parameter(attr)

    def _edit_parameter(self, attr: str) -> None:
        """Toggle a bool parameter, or open input modal for others."""
        try:
            with Session(engine) as session:
                active_event = get_active_event(session)
                current = getattr(active_event.parameters, attr)
        except (NoResultFound, RuntimeError) as exc:
            self.notify(str(exc), severity="error")
            return

        if isinstance(current, bool):
            self._apply_parameter(attr, not current)
            return

        # Numeric / timedelta — open input modal
        if isinstance(current, Timedelta):
            current_str = f"{current.total_seconds():.2f}"
            unit = "s"
        else:
            current_str = f"{current}"
            unit = ""

        def on_input(raw: str | None) -> None:
            if raw is None:
                return
            try:
                if isinstance(current, Timedelta):
                    new_val: object = Timedelta(seconds=float(raw))
                else:
                    new_val = float(raw)
                self._apply_parameter(attr, new_val)
            except ValueError as exc:
                self.notify(str(exc), severity="error")

        label = AimbatEventParametersBase.model_fields[attr].title or attr
        self.push_screen(ParameterInputModal(label, current_str, unit), on_input)

    def _apply_parameter(self, attr: str, value: object) -> None:
        """Write a parameter to the DB and sync to the in-memory ICCS object."""
        # Validate with ICCS first — before touching the DB — so invalid values
        # are rejected without being persisted.
        if self._iccs is not None and hasattr(self._iccs, attr):
            try:
                setattr(self._iccs, attr, value)
                self._iccs.clear_cache()
            except ValueError as exc:
                self.notify(str(exc), severity="error")
                return

        try:
            with Session(engine) as session:
                if attr in {p.value for p in EventParameter}:
                    set_event_parameter(session, EventParameter(attr), value)  # type: ignore[call-overload]
                else:
                    # mccc_damp / mccc_min_ccnorm — not in EventParameter enum
                    active_event = get_active_event(session)
                    validated = AimbatEventParametersBase.model_validate(
                        active_event.parameters, update={attr: value}
                    )
                    setattr(active_event.parameters, attr, getattr(validated, attr))
                    session.add(active_event)
                    session.commit()
        except ValidationError as exc:
            msgs = "; ".join(
                e["msg"].removeprefix("Value error, ") for e in exc.errors()
            )
            self.notify(msgs, severity="error")
            self._create_iccs()  # revert ICCS to DB state
            return
        except Exception as exc:
            self.notify(str(exc), severity="error")
            self._create_iccs()  # revert ICCS to DB state
            return

        # Parameter change may have fixed previously invalid ranges.
        if self._iccs is None:
            self._create_iccs()

        self._refresh_parameters()
        self._refresh_seismograms()
        self._refresh_event_bar()
        self.notify(f"{attr} updated", timeout=2)

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
            if self._iccs is not None:
                for iccs_seis in self._iccs.seismograms:
                    if iccs_seis.extra.get("id") == seis_uuid:
                        setattr(iccs_seis, param, new_value)
                        self._iccs.clear_cache()
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
            "tab-seismograms": "Delete this seismogram?",
            "tab-stations": "Delete this station and all its seismograms?",
            "tab-snapshots": "Delete this snapshot?",
        }
        msg = messages.get(tab)
        if not msg:
            return

        def on_confirm(confirmed: bool | None) -> None:
            if not confirmed:
                return
            try:
                if tab == "tab-seismograms":
                    with Session(engine) as session:
                        delete_seismogram_by_id(session, uuid.UUID(item_id))
                    self._create_iccs()
                    self.refresh_all()
                    self.notify("Seismogram deleted", timeout=2)
                elif tab == "tab-stations":
                    with Session(engine) as session:
                        delete_station_by_id(session, uuid.UUID(item_id))
                    self._create_iccs()
                    self.refresh_all()
                    self.notify("Station deleted", timeout=2)
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

    def _confirm_rollback(self, snap_id: str) -> None:
        def on_confirm(confirmed: bool | None) -> None:
            if not confirmed:
                return
            try:
                with Session(engine) as session:
                    rollback_to_snapshot_by_id(session, uuid.UUID(snap_id))
                    if self._iccs is not None:
                        sync_iccs_parameters(session, self._iccs)
                if self._iccs is None:
                    self._create_iccs()
                self.refresh_all()
                self.notify("Rolled back to snapshot", timeout=3)
            except Exception as exc:
                self.notify(str(exc), severity="error")

        self.push_screen(ConfirmModal("Roll back to this snapshot?"), on_confirm)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_switch_event(self) -> None:
        def on_result(event_id: uuid.UUID | None) -> None:
            if event_id is not None:
                self._create_iccs()
            self.refresh_all()

        self.push_screen(EventSwitcherModal(), on_result)

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

    def action_open_interactive_tools(self) -> None:
        if self._iccs is None:
            self.notify("No active event — activate one first", severity="warning")
            return

        def on_result(result: tuple[str, bool, bool] | None) -> None:
            if result is not None:
                self._run_pick_tool(*result)

        self.push_screen(InteractiveToolsModal(), on_result)

    def _run_pick_tool(self, tool: str, context: bool, all_seis: bool) -> None:
        """Run an interactive pick tool, suspending Textual while matplotlib is active.

        Uses the long-lived ICCS instance (waveform data already loaded) and runs
        matplotlib on the main thread via App.suspend(), which is the correct
        Textual pattern for blocking terminal-adjacent processes.
        """
        if self._iccs is None:
            self.notify("ICCS not ready — please wait", severity="warning")
            return
        _TOOL_LABELS = {
            "phase": "Phase arrival (t1)",
            "window": "Time window",
            "ccnorm": "Min CC norm",
        }
        tool_label = _TOOL_LABELS.get(tool, tool)

        try:
            with self.suspend():
                console = Console()
                console.clear()
                console.print(
                    Panel(
                        f"[bold]{tool_label}[/bold]\n\n"
                        "Close the matplotlib window to return to AIMBAT.",
                        title="Interactive Tool Running",
                        border_style="bright_blue",
                        padding=(1, 4),
                    )
                )
                with Session(engine) as session:
                    if tool == "phase":
                        update_pick(
                            session,
                            self._iccs,
                            context,
                            all_seis,
                            False,
                            return_fig=False,
                        )
                    elif tool == "window":
                        update_timewindow(
                            session,
                            self._iccs,
                            context,
                            all_seis,
                            False,
                            return_fig=False,
                        )
                    elif tool == "ccnorm":
                        update_min_ccnorm(
                            session,
                            self._iccs,
                            context,
                            all_seis,
                            return_fig=False,
                        )
                console.clear()
        except Exception as exc:
            self.notify(str(exc), severity="error")
            return
        self._refresh_parameters()
        self._refresh_seismograms()
        self._refresh_event_bar()
        self.notify("Done", timeout=2)

    def action_open_align(self) -> None:
        if self._iccs is None:
            self.notify("No active event — activate one first", severity="warning")
            return

        def on_result(result: tuple[str, bool, bool, bool] | None) -> None:
            if result is not None:
                self._run_align_tool(self._iccs, *result)

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
                    run_mccc(session, iccs, all_seis)
        except Exception as exc:
            self.call_from_thread(self.notify, str(exc), severity="error")
            return
        self.call_from_thread(self._post_align_complete)

    def _post_align_complete(self) -> None:
        self.refresh_all()
        self.notify("Alignment complete", timeout=3)

    def action_new_snapshot(self) -> None:
        def on_comment(comment: str | None) -> None:
            if comment is None:
                return
            try:
                with Session(engine) as session:
                    create_snapshot(session, comment or None)
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
