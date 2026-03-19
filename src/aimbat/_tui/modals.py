"""Modal screens for the AIMBAT TUI."""

from __future__ import annotations

import uuid
from enum import StrEnum

from pandas import Timedelta
from pydantic import ValidationError
from sqlmodel import Session
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import DataTable, Input, Label, Static

from aimbat._tui._format import tui_cell, tui_display_title
from aimbat._tui._widgets import VimDataTable
from aimbat._types import EventParameter
from aimbat.core import delete_event, dump_event_table, set_event_parameter
from aimbat.db import engine
from aimbat.models import AimbatEvent, AimbatEventRead
from aimbat.models._parameters import AimbatEventParametersBase

_SWITCHER_EVENT_EXCLUDE: set[str] = {"snapshot_count", "last_modified"}


class _CSS(StrEnum):
    """CSS class names shared across modal widgets."""

    TITLE = "modal-title"
    HINT = "modal-hint"


class _Hint(StrEnum):
    """Hint label strings shown at the bottom of modal dialogs."""

    SAVE_CANCEL = (
        "[@click='screen.save']⏎ save[/]   [@click='screen.cancel']⎋ cancel[/]"
    )
    NAVIGATE_EVENT_SWITCHER = "↑↓ navigate   [@click='screen.select']⏎ select[/]   [@click='screen.toggle_completed']c complete[/]   [@click='screen.delete_event']⌫ delete[/]   [@click='screen.cancel']⎋ cancel[/]"
    NAVIGATE_SELECT_CANCEL = "↑↓ navigate   [@click='screen.select']⏎ select[/]   [@click='screen.cancel']⎋ cancel[/]"
    NAVIGATE_RUN_CANCEL = "↑↓ navigate   [@click='screen.select']⏎ run[/]   [@click='screen.cancel']⎋ cancel[/]"
    CONFIRM_CANCEL = "[@click='screen.confirm'][bold]y[/bold] / ⏎ confirm[/]   [@click='screen.cancel'][bold]n[/bold] / ⎋ cancel[/]"
    CLOSE = "[@click='screen.cancel']⎋ close[/]"
    NAVIGATE_EDIT_CLOSE = "↑↓ navigate   [@click='screen.select']⏎ edit[/]   [@click='screen.cancel']⎋ close[/]"


__all__ = [
    "ActionMenuModal",
    "AlignModal",
    "ConfirmModal",
    "EventSwitcherModal",
    "InteractiveToolsModal",
    "NoProjectModal",
    "ParameterInputModal",
    "ParametersModal",
    "QualityModal",
    "SnapshotActionMenuModal",
    "SnapshotCommentModal",
    "SnapshotDetailsModal",
]


# ---------------------------------------------------------------------------
# Event-switcher modal
# ---------------------------------------------------------------------------


class EventSwitcherModal(ModalScreen[uuid.UUID | None]):
    """Modal screen for selecting a seismic event to process."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("c", "toggle_completed", "Complete", show=True),
        Binding("backspace", "delete_event", "Delete", show=True),
    ]

    def __init__(self, current_event_id: uuid.UUID | None = None) -> None:
        super().__init__()
        self._current_event_id = current_event_id
        self._selected_event_id: str | None = None

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action in {"delete_event", "toggle_completed"}:
            return True if self._selected_event_id else False
        return True

    def compose(self) -> ComposeResult:
        with Container(id="switcher-dialog"):
            yield Label("Switch Event", classes=_CSS.TITLE)
            yield VimDataTable(id="event-table")
            yield Label(_Hint.NAVIGATE_EVENT_SWITCHER, classes=_CSS.HINT)

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        headers = [
            tui_display_title(AimbatEventRead, f)
            for f in AimbatEventRead.model_fields
            if f not in _SWITCHER_EVENT_EXCLUDE | {"id"}
        ]
        table.add_columns(" ", *headers)
        self._populate(table)

    def _populate(self, table: DataTable) -> None:
        try:
            with Session(engine) as session:
                rows = dump_event_table(
                    session,
                    from_read_model=True,
                    by_title=True,
                    exclude=_SWITCHER_EVENT_EXCLUDE,
                )
            for row in rows:
                row_id = str(row.pop("ID"))
                marker = "▶" if row_id == str(self._current_event_id) else " "
                cells = [tui_cell(AimbatEventRead, k, v) for k, v in row.items()]
                table.add_row(marker, *cells, key=row_id)
        except RuntimeError as exc:
            self.notify(str(exc), severity="error")
            self.dismiss(None)

    def _refresh_table(self) -> None:
        table = self.query_one("#event-table", DataTable)
        saved_row = table.cursor_row
        table.clear()
        self._populate(table)
        if table.row_count > 0:
            table.move_cursor(row=min(saved_row, table.row_count - 1))

    @on(DataTable.RowHighlighted, "#event-table")
    def row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._selected_event_id = event.row_key.value if event.row_key else None
        self.refresh_bindings()

    @on(DataTable.RowSelected, "#event-table")
    def row_selected(self, event: DataTable.RowSelected) -> None:
        row_key = event.row_key.value
        if not row_key:
            return
        self.dismiss(uuid.UUID(row_key))

    def action_toggle_completed(self) -> None:
        event_id = self._selected_event_id
        if not event_id:
            return
        try:
            with Session(engine) as session:
                event = session.get(AimbatEvent, uuid.UUID(event_id))
                if event is None:
                    return
                event.parameters.completed = not event.parameters.completed
                session.add(event)
                session.commit()
            self._refresh_table()
        except Exception as exc:
            self.notify(str(exc), severity="error")

    def action_delete_event(self) -> None:
        event_id = self._selected_event_id
        if not event_id:
            return

        def on_confirm(confirmed: bool | None) -> None:
            if not confirmed:
                return
            try:
                with Session(engine) as session:
                    delete_event(session, uuid.UUID(event_id))
                self._selected_event_id = None
                self._refresh_table()
                self.notify("Event deleted", timeout=2)
            except Exception as exc:
                self.notify(str(exc), severity="error")

        self.app.push_screen(
            ConfirmModal("Delete this event and all its data?"), on_confirm
        )

    def action_select(self) -> None:
        self.query_one(DataTable).action_select_cursor()

    def action_cancel(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Parameter-edit modal
# ---------------------------------------------------------------------------


class ParameterInputModal(ModalScreen[str | None]):
    """Modal for entering a new numeric/timedelta parameter value."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, param_name: str, current: str, unit: str) -> None:
        super().__init__()
        self._param_name = param_name
        self._current = current
        self._unit = unit

    def compose(self) -> ComposeResult:
        hint = f"Current: {self._current} {self._unit}".strip()
        with Container(id="param-edit-dialog"):
            yield Label(f"Edit: {self._param_name}", classes=_CSS.TITLE)
            yield Label(hint, classes=_CSS.HINT)
            yield Input(value=self._current, id="param-input")
            yield Label(
                _Hint.SAVE_CANCEL,
                classes=_CSS.HINT,
            )

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    @on(Input.Submitted)
    def submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip())

    def action_save(self) -> None:
        self.dismiss(self.query_one("#param-input", Input).value.strip())

    def action_cancel(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# No-project modal
# ---------------------------------------------------------------------------


class NoProjectModal(ModalScreen[bool]):
    """Shown on startup when no project exists.

    Dismisses True if the user chose to create a project, False to quit.
    """

    BINDINGS = [
        Binding("c", "create", show=False),
        Binding("enter", "create", show=False),
        Binding("q", "quit_app", show=False),
        Binding("escape", "quit_app", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="confirm-dialog"):
            yield Label(
                "No project found in the current directory.", classes=_CSS.TITLE
            )
            yield Label(
                "[@click='screen.create'][bold]c[/bold] / ⏎ create project[/]"
                "   "
                "[@click='screen.quit_app'][bold]q[/bold] / ⎋ quit[/]",
                classes=_CSS.HINT,
            )

    def action_create(self) -> None:
        self.dismiss(True)

    def action_quit_app(self) -> None:
        self.dismiss(False)


# ---------------------------------------------------------------------------
# Confirm modal
# ---------------------------------------------------------------------------


class ConfirmModal(ModalScreen[bool | None]):
    """Generic yes/no confirmation dialog.

    Dismisses True on confirm, False on cancel.
    """

    BINDINGS = [
        Binding("y", "confirm", show=False),
        Binding("enter", "confirm", show=False),
        Binding("n", "cancel", show=False),
        Binding("escape", "cancel", show=False),
    ]

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Container(id="confirm-dialog"):
            yield Label(self._message, classes=_CSS.TITLE)
            yield Label(
                _Hint.CONFIRM_CANCEL,
                classes=_CSS.HINT,
            )

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


# ---------------------------------------------------------------------------
# Snapshot comment modal
# ---------------------------------------------------------------------------


class SnapshotCommentModal(ModalScreen[str | None]):
    """Prompt for an optional snapshot comment.

    Dismisses with the comment string (empty string = no comment) or None if
    the user cancels.
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def compose(self) -> ComposeResult:
        with Container(id="param-edit-dialog"):
            yield Label("New Snapshot", classes=_CSS.TITLE)
            yield Input(placeholder="Comment (optional)", id="param-input")
            yield Label(
                _Hint.SAVE_CANCEL,
                classes=_CSS.HINT,
            )

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    @on(Input.Submitted)
    def submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip())

    def action_save(self) -> None:
        self.dismiss(self.query_one("#param-input", Input).value.strip())

    def action_cancel(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Parameters modal
# ---------------------------------------------------------------------------


class ParametersModal(ModalScreen[bool]):
    """View and edit all event processing parameters inline.

    Dismisses with True if any parameter was changed, False otherwise.
    """

    BINDINGS = [Binding("escape", "cancel", show=False)]

    def __init__(self, event_id: uuid.UUID) -> None:
        super().__init__()
        self._event_id = event_id
        self._changed = False

    def compose(self) -> ComposeResult:
        with Container(id="param-table-dialog"):
            yield Label("Parameters", classes=_CSS.TITLE)
            yield VimDataTable(id="param-modal-table", show_header=True)
            yield Label(_Hint.NAVIGATE_EDIT_CLOSE, classes=_CSS.HINT)

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.add_columns("Parameter", "Value", "Description")
        self._populate()
        table.focus()

    def _populate(self) -> None:
        table = self.query_one("#param-modal-table", DataTable)
        saved_row = table.cursor_row
        table.clear()
        with Session(engine) as session:
            event = session.get(AimbatEvent, self._event_id)
            if event is None:
                return
            fields = list(AimbatEventParametersBase.model_fields.items())
            p = event.parameters
            for attr, field_info in fields:
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
            table.styles.height = len(fields) + 2
        if table.row_count > 0:
            table.move_cursor(row=min(saved_row, table.row_count - 1))

    @on(DataTable.RowSelected)
    def row_selected(self, event: DataTable.RowSelected) -> None:
        attr = event.row_key.value
        if not attr:
            return
        self._edit_parameter(attr)

    def _edit_parameter(self, attr: str) -> None:
        with Session(engine) as session:
            ev = session.get(AimbatEvent, self._event_id)
            if ev is None:
                return
            current = getattr(ev.parameters, attr)

        if isinstance(current, bool):
            self._apply_parameter(attr, not current)
            return

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
        self.app.push_screen(ParameterInputModal(label, current_str, unit), on_input)

    def _apply_parameter(self, attr: str, value: object) -> None:
        try:
            with Session(engine) as session:
                event = session.get(AimbatEvent, self._event_id)
                if event is None:
                    return
                set_event_parameter(
                    session,
                    event.id,
                    EventParameter(attr),
                    value,
                    validate_iccs=True,
                )  # type: ignore[call-overload]
        except ValidationError as exc:
            msgs = "; ".join(
                e["msg"].removeprefix("Value error, ") for e in exc.errors()
            )
            self.notify(msgs, severity="error")
            return
        except Exception as exc:
            self.notify(str(exc), severity="error")
            return
        self._changed = True
        self.notify(f"{attr} updated", timeout=2)
        self._populate()

    def action_select(self) -> None:
        self.query_one(DataTable).action_select_cursor()

    def action_cancel(self) -> None:
        self.dismiss(self._changed)


# ---------------------------------------------------------------------------
# Row-action context menu modal
# ---------------------------------------------------------------------------


class ActionMenuModal(ModalScreen[str | None]):
    """Generic context-action menu for a selected table row.

    Dismisses with the chosen action key, or None on cancel.
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False),
    ]

    def __init__(self, title: str, actions: list[tuple[str, str]]) -> None:
        super().__init__()
        self._title = title
        self._actions = actions  # [(action_key, display_label), ...]

    def compose(self) -> ComposeResult:
        with Container(id="action-menu-dialog"):
            yield Label(self._title, classes=_CSS.TITLE)
            yield VimDataTable(id="action-table", show_header=False)
            yield Label(
                _Hint.NAVIGATE_SELECT_CANCEL,
                classes=_CSS.HINT,
            )

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.add_column("action")
        for key, label in self._actions:
            table.add_row(label, key=key)
        table.styles.height = len(self._actions)
        table.focus()

    @on(DataTable.RowSelected)
    def row_selected(self, event: DataTable.RowSelected) -> None:
        self.dismiss(event.row_key.value)

    def action_select(self) -> None:
        self.query_one(DataTable).action_select_cursor()

    def action_cancel(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Snapshot action menu modal
# ---------------------------------------------------------------------------

_SNAPSHOT_ACTIONS: list[tuple[str, str]] = [
    ("show_details", "Show details"),
    ("show_quality", "Show quality"),
    ("preview_stack", "Preview stack"),
    ("preview_image", "Preview matrix image"),
    ("rollback", "Rollback to this snapshot"),
    ("delete", "Delete snapshot"),
]

_PREVIEW_ACTIONS: frozenset[str] = frozenset({"preview_stack", "preview_image"})


class SnapshotActionMenuModal(ModalScreen[tuple[str, bool, bool] | None]):
    """Action menu for a snapshot row.

    Shows context/all-seismograms toggles dynamically when a preview action
    is highlighted.  Dismisses with (action, context, all_seismograms) or None.
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("c", "toggle_context", show=False),
        Binding("a", "toggle_all", show=False),
    ]

    def __init__(self, title: str) -> None:
        super().__init__()
        self._title = title
        self._use_context = True
        self._all_seis = False
        self._highlighted: str = ""

    def compose(self) -> ComposeResult:
        with Container(id="snapshot-action-dialog"):
            yield Label(self._title, classes=_CSS.TITLE)
            yield VimDataTable(id="snapshot-action-table", show_header=False)
            yield Static(id="snapshot-action-options")
            yield Label(_Hint.NAVIGATE_SELECT_CANCEL, classes=_CSS.HINT)

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.add_column("action")
        for key, label in _SNAPSHOT_ACTIONS:
            table.add_row(label, key=key)
        table.styles.height = len(_SNAPSHOT_ACTIONS)
        table.focus()

    def _update_options(self) -> None:
        opts = self.query_one("#snapshot-action-options", Static)
        if self._highlighted in _PREVIEW_ACTIONS:
            ctx = "✓" if self._use_context else "✗"
            al = "✓" if self._all_seis else "✗"
            opts.update(
                f"  [@click='screen.toggle_context'][dim]c[/dim] context: {ctx}[/]"
                f"   [@click='screen.toggle_all'][dim]a[/dim] all seismograms: {al}[/]"
            )
        else:
            opts.update("")

    @on(DataTable.RowHighlighted, "#snapshot-action-table")
    def row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._highlighted = event.row_key.value or ""
        self._update_options()

    @on(DataTable.RowSelected, "#snapshot-action-table")
    def row_selected(self, event: DataTable.RowSelected) -> None:
        key = event.row_key.value
        if key:
            self.dismiss((key, self._use_context, self._all_seis))

    def action_toggle_context(self) -> None:
        if self._highlighted in _PREVIEW_ACTIONS:
            self._use_context = not self._use_context
            self._update_options()

    def action_toggle_all(self) -> None:
        if self._highlighted in _PREVIEW_ACTIONS:
            self._all_seis = not self._all_seis
            self._update_options()

    def action_select(self) -> None:
        self.query_one(DataTable).action_select_cursor()

    def action_cancel(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Interactive Tools modal
# ---------------------------------------------------------------------------

# Keep in sync with _TOOL_REGISTRY in app.py.
_TOOLS: list[tuple[str, str]] = [
    ("phase", "Phase arrival (t1)"),
    ("window", "Time window"),
    ("cc", "Min CC"),
    ("stack", "Stack plot"),
    ("image", "Matrix image"),
]


class InteractiveToolsModal(ModalScreen[tuple[str, bool, bool] | None]):
    """Menu for launching interactive matplotlib tools.

    Options are toggled with key bindings so no Checkbox widgets are needed.
    Dismisses with (tool_key, context, all_seismograms) or None on cancel.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("c", "toggle_context", "Context", show=False),
        Binding("a", "toggle_all", "All", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._use_context = True
        self._all_seis = False

    def compose(self) -> ComposeResult:
        with Container(id="tools-dialog"):
            yield Label("Tools", classes=_CSS.TITLE)
            yield VimDataTable(id="tools-table", show_header=False)
            yield Static(id="tools-options")
            yield Label(
                _Hint.NAVIGATE_RUN_CANCEL,
                classes=_CSS.HINT,
            )

    def on_mount(self) -> None:
        table = self.query_one("#tools-table", DataTable)
        table.cursor_type = "row"
        table.add_column("tool")
        for key, label in _TOOLS:
            table.add_row(label, key=key)
        self._update_options()
        table.focus()

    def _update_options(self) -> None:
        ctx = "✓" if self._use_context else "✗"
        al = "✓" if self._all_seis else "✗"
        self.query_one("#tools-options", Static).update(
            f"  [@click='screen.toggle_context'][dim]c[/dim] context: {ctx}[/]"
            f"   [@click='screen.toggle_all'][dim]a[/dim] all seismograms: {al}[/]"
        )

    @on(DataTable.RowSelected, "#tools-table")
    def row_selected(self, event: DataTable.RowSelected) -> None:
        key = event.row_key.value
        if key:
            self.dismiss((key, self._use_context, self._all_seis))

    def action_toggle_context(self) -> None:
        self._use_context = not self._use_context
        self._update_options()

    def action_toggle_all(self) -> None:
        self._all_seis = not self._all_seis
        self._update_options()

    def action_select(self) -> None:
        self.query_one(DataTable).action_select_cursor()

    def action_cancel(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Align modal  (ICCS / MCCC)
# ---------------------------------------------------------------------------

_ALIGN_ALGORITHMS: list[tuple[str, str]] = [
    ("iccs", "ICCS — Iterative Cross-Correlation and Stack"),
    ("mccc", "MCCC — Multi-Channel Cross-Correlation"),
]


class AlignModal(ModalScreen[tuple[str, bool, bool, bool] | None]):
    """Menu for running ICCS or MCCC alignment.

    Dismisses with (algorithm, autoflip, autoselect, all_seismograms) or None.
    ICCS options: autoflip (f), autoselect (s).
    MCCC options: all seismograms (a).
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("f", "toggle_autoflip", "Autoflip", show=False),
        Binding("s", "toggle_autoselect", "Autoselect", show=False),
        Binding("a", "toggle_all", "All", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._autoflip = False
        self._autoselect = False
        self._all_seis = False
        self._highlighted_algorithm: str = "iccs"

    def compose(self) -> ComposeResult:
        with Container(id="align-dialog"):
            yield Label("Align Seismograms", classes=_CSS.TITLE)
            yield VimDataTable(id="align-table", show_header=False)
            yield Static(id="align-options")
            yield Label(
                _Hint.NAVIGATE_RUN_CANCEL,
                classes=_CSS.HINT,
            )

    def on_mount(self) -> None:
        table = self.query_one("#align-table", DataTable)
        table.cursor_type = "row"
        table.add_column("algorithm")
        for key, label in _ALIGN_ALGORITHMS:
            table.add_row(label, key=key)
        self._update_options()
        table.focus()

    def _update_options(self) -> None:
        opts = self.query_one("#align-options", Static)
        if self._highlighted_algorithm == "iccs":
            fl = "✓" if self._autoflip else "✗"
            sl = "✓" if self._autoselect else "✗"
            opts.update(
                f"  [@click='screen.toggle_autoflip'][dim]f[/dim] Autoflip: {fl}[/]"
                f"   [@click='screen.toggle_autoselect'][dim]s[/dim] Autoselect: {sl}[/]"
            )
        else:
            al = "✓" if self._all_seis else "✗"
            opts.update(
                f"  [@click='screen.toggle_all'][dim]a[/dim] All seismograms: {al}[/]"
            )

    @on(DataTable.RowHighlighted, "#align-table")
    def row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._highlighted_algorithm = event.row_key.value or "iccs"
        self._update_options()

    @on(DataTable.RowSelected, "#align-table")
    def row_selected(self, event: DataTable.RowSelected) -> None:
        key = event.row_key.value
        if key:
            self.dismiss((key, self._autoflip, self._autoselect, self._all_seis))

    def action_toggle_autoflip(self) -> None:
        if self._highlighted_algorithm == "iccs":
            self._autoflip = not self._autoflip
            self._update_options()

    def action_toggle_autoselect(self) -> None:
        if self._highlighted_algorithm == "iccs":
            self._autoselect = not self._autoselect
            self._update_options()

    def action_toggle_all(self) -> None:
        if self._highlighted_algorithm == "mccc":
            self._all_seis = not self._all_seis
            self._update_options()

    def action_select(self) -> None:
        self.query_one(DataTable).action_select_cursor()

    def action_cancel(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Quality modal
# ---------------------------------------------------------------------------


class QualityModal(ModalScreen[None]):
    """Read-only quality metrics view with one headerless table per group.

    Each element of `groups` is a `(title, rows)` pair where `rows` is
    a list of pre-formatted `(label, value)` strings. An empty title
    suppresses the section heading.
    """

    BINDINGS = [Binding("escape", "cancel", show=False)]

    def __init__(
        self,
        title: str,
        groups: list[tuple[str, list[tuple[str, str]]]],
    ) -> None:
        super().__init__()
        self._title = title
        self._groups = groups

    def compose(self) -> ComposeResult:
        with Container(id="quality-dialog"):
            yield Label(self._title, classes=_CSS.TITLE)
            for i, (group_title, _) in enumerate(self._groups):
                if group_title:
                    yield Label(
                        f"[bold]{group_title}[/bold]", classes="quality-section"
                    )
                yield VimDataTable(id=f"quality-table-{i}", show_header=False)
            yield Label(_Hint.CLOSE, classes=_CSS.HINT)

    def on_mount(self) -> None:
        for i, (_, rows) in enumerate(self._groups):
            table = self.query_one(f"#quality-table-{i}", DataTable)
            table.cursor_type = "none"
            table.add_columns("label", "value")
            for row in rows:
                table.add_row(*row)
            table.styles.height = len(rows) + 1

    def action_cancel(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Snapshot details modal
# ---------------------------------------------------------------------------


class SnapshotDetailsModal(ModalScreen[None]):
    """Read-only view of the event parameters captured in a snapshot."""

    BINDINGS = [
        Binding("escape", "cancel", show=False),
    ]

    def __init__(self, title: str, rows: list[tuple[str, str]]) -> None:
        super().__init__()
        self._title = title
        self._rows = rows  # [(label, value), ...]

    def compose(self) -> ComposeResult:
        with Container(id="snapshot-details-dialog"):
            yield Label(self._title, classes=_CSS.TITLE)
            yield VimDataTable(id="snapshot-details-table", show_header=True)
            yield Label(_Hint.CLOSE, classes=_CSS.HINT)

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "none"
        table.add_columns("Parameter", "Value")
        for row in self._rows:
            table.add_row(*row)
        table.styles.height = len(self._rows) + 2

    def action_cancel(self) -> None:
        self.dismiss(None)
