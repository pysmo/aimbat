"""Per-tab panel widgets for the AIMBAT TUI."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, ClassVar, Literal

from pydantic import BaseModel
from rich.text import Text
from sqlalchemy.exc import NoResultFound, SQLAlchemyError
from sqlmodel import Session, select
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable, Static

from pysmo.tools.plotutils import relative_time_array

from aimbat.core import (
    BoundICCS,
    cc_stats,
    dump_event_table,
    dump_seismogram_table,
    dump_snapshot_table,
    dump_station_table,
    get_event_quality,
    get_snapshot_quality,
    get_station_quality,
)
from aimbat.db import engine
from aimbat.models import (
    AimbatEvent,
    AimbatEventRead,
    AimbatSeismogram,
    AimbatSeismogramRead,
    AimbatSnapshotRead,
    AimbatStationRead,
    SeismogramQualityStats,
)
from aimbat.utils.formatters import fmt_float_sem

from ._format import format_quality_panel, tui_cell, tui_display_title
from ._widgets import NoteWidget, SeismogramPlotWidget, VimDataTable
from .modals import ActionMenuModal, SnapshotActionMenuModal

__all__ = ["ProjectPanel", "SeismogramPanel", "SnapshotPanel"]

_EVENT_TABLE_EXCLUDE: set[str] = set()
_STATION_TABLE_EXCLUDE: set[str] = {"event_count"}
_SEISMOGRAM_TABLE_EXCLUDE: set[str] = {"event_id", "short_event_id"}
_SNAPSHOT_TABLE_EXCLUDE: set[str] = {"event_id", "short_event_id"}


@dataclass(frozen=True)
class RowAction:
    """One row-level action: a menu entry and, when its table has focus, a footer hotkey."""

    id: str
    """Action identifier, dispatched via `RowActionChosen`/`ActionChosen`."""

    label: str
    """Display label shown in the Enter-triggered action menu."""

    key: str
    """Footer/table hotkey when the owning row's table has keyboard focus."""


# Extend this dict to add new per-row actions to any tab. Both the
# Enter-triggered action menu and the table-focused footer hotkeys
# (`_RowActionTable`, below) read from this single registry.
_TAB_ROW_ACTIONS: dict[str, list[RowAction]] = {
    "project-events": [
        RowAction("select", "Select event", "s"),
        RowAction("toggle_completed", "Toggle completed", "m"),
        RowAction("view_seismograms", "View seismograms", "v"),
        RowAction("delete", "Delete event", "d"),
    ],
    "project-stations": [
        RowAction("view_seismograms", "View seismograms", "v"),
        RowAction("delete", "Delete station", "d"),
    ],
    "tab-seismograms": [
        RowAction("toggle_select", "Toggle select", "s"),
        RowAction("toggle_flip", "Toggle flip", "f"),
        RowAction("reset", "Reset seismogram", "u"),
        RowAction("delete", "Delete seismogram", "d"),
    ],
    "tab-snapshots": [
        RowAction("show_details", "Show details", "v"),
        RowAction("preview_stack", "Preview stack", "s"),
        RowAction("preview_image", "Preview matrix image", "x"),
        RowAction("save_results", "Save results to JSON", "w"),
        RowAction("rollback", "Rollback to this snapshot", "b"),
        RowAction("delete", "Delete snapshot", "d"),
    ],
}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _settle_cursor(
    widget: Widget,
    tables: Sequence[tuple[DataTable, int]],
    on_settled: Callable[[], None],
) -> None:
    """Restore cursor position on `tables`, deferring `on_settled` until any
    RowHighlighted events the moves trigger have been processed.

    If none of `tables` has any rows, no cursor move happens and `on_settled`
    runs immediately instead of being deferred.
    """
    moved = False
    for table, saved_row in tables:
        if table.row_count > 0:
            table.move_cursor(row=min(saved_row, table.row_count - 1))
            moved = True
    if moved:
        widget.call_after_refresh(on_settled)
    else:
        on_settled()


def _setup_table(
    widget: Widget,
    selector: str,
    model: type[BaseModel],
    exclude: set[str],
    title: str,
    *,
    extra_columns: Sequence[str] = (),
) -> DataTable:
    """Configure the `DataTable` at `selector`: border title, row cursor, and
    columns derived from `model`'s fields (minus `exclude` and `id`),
    prefixed by any `extra_columns`."""
    headers = [
        tui_display_title(model, f)
        for f in model.model_fields
        if f not in exclude | {"id"}
    ]
    table = widget.query_one(selector, DataTable)
    table.border_title = title
    table.cursor_type = "row"
    table.add_columns(*extra_columns, *headers)
    return table


def _styled_cell(cell: str | Text, style: str) -> Text:
    """Return `cell` as a `Text` with `style` applied, preserving any
    existing `Text` formatting (e.g. `text_align`)."""
    if isinstance(cell, Text):
        styled = cell.copy()
        styled.stylize(style)
        return styled
    return Text(cell, style=style)


def _populate_rows(
    table: DataTable,
    rows: Sequence[dict[str, Any]],
    model: type[BaseModel],
    *,
    on_row: Callable[[dict[str, Any]], Sequence[str]] | None = None,
    row_style: Callable[[dict[str, Any]], str | None] | None = None,
) -> None:
    """Add `rows` (dicts with title keys and an "ID" key) to `table`,
    formatting cells via `tui_cell(model, ...)`.

    If given, `on_row` is called with each row dict before "ID" is popped;
    its return value is prepended as extra leading cells (e.g. a marker).

    If given, `row_style` is called with each row dict (before "ID" is
    popped); when it returns a Rich style string, every cell in that row
    (including any `on_row` prefix) is wrapped in that style, e.g. to fade
    rows not relevant to the current context.
    """
    for row in rows:
        style = row_style(row) if row_style is not None else None
        prefix: Sequence[str | Text] = on_row(row) if on_row is not None else ()
        row_id = str(row.pop("ID"))
        cells: Sequence[str | Text] = [tui_cell(model, k, v) for k, v in row.items()]
        if style is not None:
            prefix = [_styled_cell(c, style) for c in prefix]
            cells = [_styled_cell(c, style) for c in cells]
        table.add_row(*prefix, *cells, key=row_id)


def _update_note(
    note_widget: NoteWidget, entity_kind: str, item_id: str | None
) -> None:
    """Clear `note_widget`, or bind it to `item_id` if given."""
    if item_id is None:
        note_widget.clear()
    else:
        with suppress(ValueError):
            note_widget.set_entity(entity_kind, uuid.UUID(item_id))


def _update_quality_panel(
    panel: Static,
    note_widget: NoteWidget,
    entity_kind: str,
    border_title: str,
    quality_fn: Callable[[Session, uuid.UUID], SeismogramQualityStats],
    item_id: str | None,
) -> None:
    """Refresh a quality `Static` panel and its associated note widget for `item_id`."""
    panel.border_title = border_title
    stats = None
    if item_id is not None:
        try:
            with Session(engine) as session:
                stats = quality_fn(session, uuid.UUID(item_id))
        except (ValueError, SQLAlchemyError):
            pass
    body, subtitle = format_quality_panel(stats)
    panel.update(body)
    panel.border_subtitle = subtitle
    _update_note(note_widget, entity_kind, item_id)


def _open_row_action_menu(
    widget: Widget,
    tab: str,
    item_id: str,
    title: str,
    dispatch: Callable[[str, str, str], None],
) -> None:
    """Open the row-action menu for `tab`, calling `dispatch(tab, item_id, action)`
    if the user picks an action (does nothing if they cancel)."""
    actions = _TAB_ROW_ACTIONS.get(tab, [])
    if not actions:
        return

    def on_action(action: str | None) -> None:
        if action is not None:
            dispatch(tab, item_id, action)

    widget.app.push_screen(
        ActionMenuModal(title, [(a.id, a.label) for a in actions]), on_action
    )


class _RowActionTable(VimDataTable):
    """`VimDataTable` that exposes its `_TAB_ROW_ACTIONS` entries as footer hotkeys.

    Subclasses set `TAB_ID`; `BINDINGS` and `check_action` are derived from
    `_TAB_ROW_ACTIONS[TAB_ID]` so the Enter-triggered action menu and the
    footer hotkeys can never drift apart.
    """

    TAB_ID: ClassVar[str]

    class RowActionSelected(Message):
        """Posted when a row action is triggered directly via its footer hotkey."""

        def __init__(
            self, table: "_RowActionTable", row_key: str, action_id: str
        ) -> None:
            super().__init__()
            self.table = table
            self.row_key = row_key
            self.action_id = action_id

        @property
        def control(self) -> "_RowActionTable":
            return self.table

    def __init_subclass__(cls, **kwargs: Any) -> None:
        # Textual's own DOMNode.__init_subclass__ (called via super() below)
        # merges BINDINGS across the MRO into cls._merged_bindings as part of
        # its own class-setup work, so BINDINGS must already reflect this
        # subclass's actions *before* that call, not after - getting this
        # order wrong silently drops every row-action hotkey from the footer
        # (row actions still work via Enter -> menu, so it's easy to miss).
        # This depends on the internal ordering of an undocumented Textual
        # mechanism, not a stable public contract; if a Textual upgrade ever
        # changes it, TestRowActionFooterHotkeys in test_tui.py is what will
        # fail and point back here.
        cls.BINDINGS = [
            Binding(a.key, f"row_action('{a.id}')", a.label, show=True)
            for a in _TAB_ROW_ACTIONS[cls.TAB_ID]
        ]
        super().__init_subclass__(**kwargs)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "row_action":
            return self.row_count > 0
        return True

    def action_row_action(self, action_id: str) -> None:
        if self.row_count == 0:
            return
        row_key = self.coordinate_to_cell_key(self.cursor_coordinate).row_key.value
        if row_key:
            self.post_message(self.RowActionSelected(self, row_key, action_id))


class _EventTable(_RowActionTable):
    """Row-action-aware table for the Project tab's event list."""

    TAB_ID = "project-events"


class _StationTable(_RowActionTable):
    """Row-action-aware table for the Project tab's station list."""

    TAB_ID = "project-stations"


class _SeismogramTable(_RowActionTable):
    """Row-action-aware table for the Live data tab's seismogram list."""

    TAB_ID = "tab-seismograms"


class _SnapshotTable(_RowActionTable):
    """Row-action-aware table for the Snapshots tab's snapshot list."""

    TAB_ID = "tab-snapshots"


# ---------------------------------------------------------------------------
# Project tab
# ---------------------------------------------------------------------------


class ProjectPanel(Widget):
    """Event and station tables for the Project tab.

    Owns both `VimDataTable`s (events and stations), the shared quality
    panel, and the note widget. Call `refresh_data` to reload from the
    database.
    """

    class RowActionChosen(Message):
        """Posted when the user resolves a project row's action menu."""

        def __init__(self, tab: str, item_id: str, action: str) -> None:
            super().__init__()
            self.tab = tab
            self.item_id = item_id
            self.action = action

    def compose(self) -> ComposeResult:
        with Horizontal(id="project-layout"):
            with Vertical(id="project-tables"):
                yield _EventTable(id="project-event-table")
                yield _StationTable(id="project-station-table")
            with Vertical(id="project-right-panel"):
                yield Static(id="project-quality-panel", classes="quality-panel")
                yield NoteWidget(id="project-note")

    def on_mount(self) -> None:
        self._highlighted_event_id: str | None = None
        self._highlighted_station_id: str | None = None
        self._quality_source: Literal["event", "station"] = "event"
        self._refreshing: bool = False
        _setup_table(
            self,
            "#project-event-table",
            AimbatEventRead,
            _EVENT_TABLE_EXCLUDE,
            "Events",
            extra_columns=(" ",),
        )
        _setup_table(
            self,
            "#project-station-table",
            AimbatStationRead,
            _STATION_TABLE_EXCLUDE,
            "Stations",
        )

    def refresh_data(self, current_event_id: uuid.UUID | None) -> None:
        et = self.query_one("#project-event-table", DataTable)
        st = self.query_one("#project-station-table", DataTable)
        et_saved, st_saved = et.cursor_row, st.cursor_row
        et.clear()
        st.clear()
        with suppress(NoResultFound, RuntimeError):
            with Session(engine) as session:
                event_rows = dump_event_table(
                    session,
                    from_read_model=True,
                    by_title=True,
                    exclude=_EVENT_TABLE_EXCLUDE,
                )
                station_rows = dump_station_table(
                    session,
                    from_read_model=True,
                    by_title=True,
                    exclude=_STATION_TABLE_EXCLUDE,
                )
                used_station_ids: set[str] = (
                    {
                        str(station_id)
                        for station_id in session.exec(
                            select(AimbatSeismogram.station_id)
                            .where(AimbatSeismogram.event_id == current_event_id)
                            .distinct()
                        ).all()
                    }
                    if current_event_id is not None
                    else set()
                )

            total = len(event_rows)
            completed = sum(1 for r in event_rows if r.get("Completed"))
            et.border_title = (
                f"Events  [dim]{total} total · {completed} completed[/dim]"
            )

            if current_event_id is not None:
                active = next(
                    (r for r in event_rows if r.get("ID") == str(current_event_id)),
                    None,
                )
                if active is not None:
                    _sc_key = tui_display_title(AimbatEventRead, "station_count")
                    st.border_title = f"Stations  [dim]{active.get(_sc_key, '?')} in active event[/dim]"

            _populate_rows(
                et,
                event_rows,
                AimbatEventRead,
                on_row=lambda row: (
                    "▶" if str(row["ID"]) == str(current_event_id) else " ",
                ),
            )
            _populate_rows(
                st,
                station_rows,
                AimbatStationRead,
                row_style=lambda row: (
                    None
                    if current_event_id is None or str(row["ID"]) in used_station_ids
                    else "dim"
                ),
            )

        self._refreshing = True
        _settle_cursor(self, [(et, et_saved), (st, st_saved)], self._on_settled)

    def _dispatch_row_action(self, tab: str, item_id: str, action: str) -> None:
        self.post_message(self.RowActionChosen(tab, item_id, action))

    @on(DataTable.RowSelected, "#project-event-table")
    def project_event_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key.value:
            _open_row_action_menu(
                self,
                "project-events",
                event.row_key.value,
                f"Event  {event.row_key.value[:8]}",
                self._dispatch_row_action,
            )

    @on(DataTable.RowSelected, "#project-station-table")
    def project_station_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key.value:
            _open_row_action_menu(
                self,
                "project-stations",
                event.row_key.value,
                f"Station  {event.row_key.value[:8]}",
                self._dispatch_row_action,
            )

    @on(_RowActionTable.RowActionSelected)
    def _row_action_selected(self, message: _RowActionTable.RowActionSelected) -> None:
        message.stop()
        self._dispatch_row_action(
            message.table.TAB_ID, message.row_key, message.action_id
        )

    @on(DataTable.RowHighlighted, "#project-event-table")
    def project_event_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._highlighted_event_id = event.row_key.value if event.row_key else None
        if not self._refreshing:
            self._quality_source = "event"
            self._update_event_quality(self._highlighted_event_id)

    @on(DataTable.RowHighlighted, "#project-station-table")
    def project_station_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._highlighted_station_id = event.row_key.value if event.row_key else None
        if not self._refreshing:
            self._quality_source = "station"
            self._update_station_quality(self._highlighted_station_id)

    @on(VimDataTable.Focused, "#project-event-table")
    def _project_event_table_focused(self) -> None:
        if not self._refreshing:
            self._quality_source = "event"
            self._update_event_quality(self._highlighted_event_id)

    @on(VimDataTable.Focused, "#project-station-table")
    def _project_station_table_focused(self) -> None:
        if not self._refreshing:
            self._quality_source = "station"
            self._update_station_quality(self._highlighted_station_id)

    def _update_event_quality(self, item_id: str | None) -> None:
        _update_quality_panel(
            self.query_one("#project-quality-panel", Static),
            self.query_one("#project-note", NoteWidget),
            "event",
            "Live event statistics",
            get_event_quality,
            item_id,
        )

    def _update_station_quality(self, item_id: str | None) -> None:
        _update_quality_panel(
            self.query_one("#project-quality-panel", Static),
            self.query_one("#project-note", NoteWidget),
            "station",
            "Live station statistics",
            get_station_quality,
            item_id,
        )

    def _on_settled(self) -> None:
        self._refreshing = False
        if self._quality_source == "station":
            self._update_station_quality(self._highlighted_station_id)
        else:
            self._update_event_quality(self._highlighted_event_id)


# ---------------------------------------------------------------------------
# Seismogram tab (Live data)
# ---------------------------------------------------------------------------


class SeismogramPanel(Widget):
    """Seismogram table, waveform plot, and note widget for the Live data tab.

    Call `refresh_data` to reload from the database and cache the current
    `BoundICCS` for plot rendering.
    """

    class RowActionChosen(Message):
        """Posted when the user resolves a seismogram row's action menu."""

        def __init__(self, item_id: str, action: str) -> None:
            super().__init__()
            self.item_id = item_id
            self.action = action

    def compose(self) -> ComposeResult:
        with Horizontal(id="seismogram-layout"):
            yield _SeismogramTable(id="seismogram-table")
            with Vertical(id="seismogram-right-panel"):
                yield SeismogramPlotWidget(id="seismogram-plot")
                yield NoteWidget(id="seismogram-note")

    def on_mount(self) -> None:
        self._highlighted_id: str | None = None
        self._refreshing: bool = False
        self._bound_iccs: BoundICCS | None = None
        _setup_table(
            self,
            "#seismogram-table",
            AimbatSeismogramRead,
            _SEISMOGRAM_TABLE_EXCLUDE,
            "Seismograms",
        )

    def refresh_data(
        self, current_event_id: uuid.UUID | None, bound_iccs: BoundICCS | None
    ) -> None:
        self._bound_iccs = bound_iccs
        table = self.query_one("#seismogram-table", DataTable)
        saved_row = table.cursor_row
        table.clear()

        live_cc_map: dict[str, float] = {}
        if bound_iccs is not None:
            with suppress(AttributeError, ValueError):
                for iccs_seis, cc in zip(
                    bound_iccs.iccs.seismograms, bound_iccs.iccs.ccs
                ):
                    live_cc_map[str(iccs_seis.extra["id"])] = float(cc)

        with suppress(NoResultFound, RuntimeError):
            with Session(engine) as session:
                event = (
                    session.get(AimbatEvent, current_event_id)
                    if current_event_id is not None
                    else None
                )
                rows = (
                    dump_seismogram_table(
                        session,
                        from_read_model=True,
                        by_title=True,
                        exclude=_SEISMOGRAM_TABLE_EXCLUDE,
                        event_id=event.id,
                    )
                    if event is not None
                    else None
                )

            if rows is not None:
                for row in rows:
                    seis_id = str(row["ID"])
                    if seis_id in live_cc_map:
                        row["Stack CC"] = live_cc_map[seis_id]

                rows.sort(
                    key=lambda r: (
                        r["Stack CC"] if r.get("Stack CC") is not None else -2.0
                    ),
                    reverse=True,
                )

                _populate_rows(table, rows, AimbatSeismogramRead)

        stats = cc_stats(bound_iccs.iccs) if bound_iccs is not None else None
        if stats is not None and stats.n_all > 0:
            table.border_title = (
                f"Seismograms  [dim]CC: selected "
                f"{fmt_float_sem(stats.mean_selected, stats.sem_selected)}"
                f" · all {fmt_float_sem(stats.mean_all, stats.sem_all)}[/dim]"
            )
        else:
            table.border_title = "Seismograms"

        self._refreshing = True
        if table.row_count == 0:
            self._highlighted_id = None
        _settle_cursor(self, [(table, saved_row)], self._on_settled)

    def clear_selection_if_empty(self) -> None:
        if self.query_one("#seismogram-table", DataTable).row_count == 0:
            self._update_seismogram_note(None)
            self._update_seismogram_plot(None)

    @on(DataTable.RowHighlighted, "#seismogram-table")
    def seismogram_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._highlighted_id = event.row_key.value if event.row_key else None
        if not self._refreshing:
            self._update_seismogram_note(self._highlighted_id)
            self._update_seismogram_plot(self._highlighted_id)

    def _dispatch_row_action(self, tab: str, item_id: str, action: str) -> None:
        self.post_message(self.RowActionChosen(item_id, action))

    @on(DataTable.RowSelected, "#seismogram-table")
    def seismogram_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key.value:
            _open_row_action_menu(
                self,
                "tab-seismograms",
                event.row_key.value,
                f"Seismogram  {event.row_key.value[:8]}",
                self._dispatch_row_action,
            )

    @on(_RowActionTable.RowActionSelected)
    def _row_action_selected(self, message: _RowActionTable.RowActionSelected) -> None:
        message.stop()
        self._dispatch_row_action(
            message.table.TAB_ID, message.row_key, message.action_id
        )

    def _update_seismogram_note(self, item_id: str | None) -> None:
        _update_note(
            self.query_one("#seismogram-note", NoteWidget), "seismogram", item_id
        )

    def _update_seismogram_plot(self, item_id: str | None) -> None:
        try:
            plot_widget = self.query_one("#seismogram-plot", SeismogramPlotWidget)
        except NoMatches:
            return
        if item_id is None or self._bound_iccs is None:
            plot_widget.clear()
            return
        seis_uuid = uuid.UUID(item_id)
        iccs = self._bound_iccs.iccs
        idx = next(
            (
                i
                for i, s in enumerate(iccs.seismograms)
                if s.extra.get("id") == seis_uuid
            ),
            None,
        )
        if idx is None:
            plot_widget.clear()
            return
        parent = iccs.seismograms[idx]
        pick = parent.t1 if parent.t1 is not None else parent.t0
        try:
            cc_seis = iccs.cc_seismograms[idx]
            ctx_seis = iccs.context_seismograms[idx]
        except Exception:
            plot_widget.clear()
            return
        cc_times = relative_time_array(cc_seis, pick).tolist()
        ctx_times = relative_time_array(ctx_seis, pick).tolist()
        plot_widget.update_plots(
            cc_times,
            cc_seis.data.tolist(),
            ctx_times,
            ctx_seis.data.tolist(),
        )

    def _on_settled(self) -> None:
        self._refreshing = False
        self._update_seismogram_note(self._highlighted_id)
        self._update_seismogram_plot(self._highlighted_id)


# ---------------------------------------------------------------------------
# Snapshot tab
# ---------------------------------------------------------------------------


class SnapshotPanel(Widget):
    """Snapshot table, quality panel, and note widget for the Snapshots tab.

    Pushes `SnapshotActionMenuModal` itself (it has extra preview/save
    actions not shared with the other tabs) and posts `ActionChosen` with
    the resolved action. Call `refresh_data` to reload from the database.
    """

    class ActionChosen(Message):
        """Posted when the user resolves a snapshot row's action menu."""

        def __init__(
            self, item_id: str, action: str, context: bool, all_seismograms: bool
        ) -> None:
            super().__init__()
            self.item_id = item_id
            self.action = action
            self.context = context
            self.all_seismograms = all_seismograms

    def compose(self) -> ComposeResult:
        with Horizontal(id="snapshot-layout"):
            yield _SnapshotTable(id="snapshot-table")
            with Vertical(id="snapshot-right-panel"):
                yield Static(id="snapshot-quality-panel", classes="quality-panel")
                yield NoteWidget(id="snapshot-note")

    def on_mount(self) -> None:
        self._highlighted_id: str | None = None
        self._refreshing: bool = False
        _setup_table(
            self,
            "#snapshot-table",
            AimbatSnapshotRead,
            _SNAPSHOT_TABLE_EXCLUDE,
            "Snapshots",
        )

    def refresh_data(self, current_event_id: uuid.UUID | None) -> None:
        table = self.query_one("#snapshot-table", DataTable)
        saved_row = table.cursor_row
        table.clear()
        with suppress(NoResultFound, RuntimeError):
            if current_event_id is not None:
                with Session(engine) as session:
                    event = session.get(AimbatEvent, current_event_id)
                    if event is not None:
                        snapshots = dump_snapshot_table(
                            session,
                            from_read_model=True,
                            by_title=True,
                            exclude=_SNAPSHOT_TABLE_EXCLUDE,
                            event_id=event.id,
                        )
                        _populate_rows(table, snapshots, AimbatSnapshotRead)
        self._refreshing = True
        if table.row_count == 0:
            self._highlighted_id = None
        _settle_cursor(self, [(table, saved_row)], self._on_settled)

    def clear_selection_if_empty(self) -> None:
        if self.query_one("#snapshot-table", DataTable).row_count == 0:
            self._update_snapshot_quality(None)

    @on(DataTable.RowHighlighted, "#snapshot-table")
    def snapshot_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._highlighted_id = event.row_key.value if event.row_key else None
        if not self._refreshing:
            self._update_snapshot_quality(self._highlighted_id)

    @on(DataTable.RowSelected, "#snapshot-table")
    def snapshot_row_selected(self, event: DataTable.RowSelected) -> None:
        snap_id = event.row_key.value
        if not snap_id:
            return

        def on_action(result: tuple[str, bool, bool] | None) -> None:
            if result is None:
                return
            action, context, all_seis = result
            self.post_message(self.ActionChosen(snap_id, action, context, all_seis))

        self.app.push_screen(
            SnapshotActionMenuModal(
                f"Snapshot  {snap_id[:8]}", _TAB_ROW_ACTIONS["tab-snapshots"]
            ),
            on_action,
        )

    @on(_RowActionTable.RowActionSelected)
    def _row_action_selected(self, message: _RowActionTable.RowActionSelected) -> None:
        # Direct hotkeys use the modal's own default toggle values; non-default
        # context/all_seismograms combinations still require Enter -> modal.
        message.stop()
        self.post_message(
            self.ActionChosen(message.row_key, message.action_id, True, False)
        )

    def _update_snapshot_quality(self, item_id: str | None) -> None:
        _update_quality_panel(
            self.query_one("#snapshot-quality-panel", Static),
            self.query_one("#snapshot-note", NoteWidget),
            "snapshot",
            "Snapshot statistics",
            get_snapshot_quality,
            item_id,
        )

    def _on_settled(self) -> None:
        self._refreshing = False
        self._update_snapshot_quality(self._highlighted_id)
