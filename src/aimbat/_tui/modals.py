"""Modal screens for the AIMBAT TUI."""

from __future__ import annotations

import uuid
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from pandas import Timedelta
from pydantic import ValidationError
from sqlmodel import Session
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import DataTable, Input, Label, Markdown, Static

from aimbat._cli.common import CAUSAL_DEFAULTS
from aimbat._tui._tools import CAUSAL_TOOL_REGISTRY, TOOL_REGISTRY
from aimbat._tui._widgets import VimDataTable
from aimbat._types import EventParameter
from aimbat.core import set_event_parameter
from aimbat.db import engine
from aimbat.models import AimbatEvent
from aimbat.models._parameters import AimbatEventParametersBase
from aimbat.utils import format_validation_error

if TYPE_CHECKING:
    from aimbat._tui._panels import RowAction


class _CSS(StrEnum):
    """CSS class names shared across modal widgets."""

    TITLE = "modal-title"
    HINT = "modal-hint"


class _Hint(StrEnum):
    """Hint label strings shown at the bottom of modal dialogs."""

    SAVE_CANCEL = (
        "[@click='screen.save']⏎ save[/]   [@click='screen.cancel']⎋ cancel[/]"
    )
    NAVIGATE_SELECT_CANCEL = "↑↓ navigate   [@click='screen.select']⏎ select[/]   [@click='screen.cancel']⎋ cancel[/]"
    NAVIGATE_RUN_CANCEL = "↑↓ navigate   [@click='screen.select']⏎ run[/]   [@click='screen.cancel']⎋ cancel[/]"
    CONFIRM_CANCEL = "[@click='screen.confirm'][bold]y[/bold] / ⏎ confirm[/]   [@click='screen.cancel'][bold]n[/bold] / ⎋ cancel[/]"
    CLOSE = "[@click='screen.cancel']⎋ close[/]"
    NAVIGATE_EDIT_CLOSE = "↑↓ navigate   [@click='screen.select']⏎ edit[/]   [@click='screen.cancel']⎋ close[/]"


__all__ = [
    "ActionMenuModal",
    "AlignModal",
    "ConfirmModal",
    "HelpModal",
    "InteractiveToolsModal",
    "NoProjectModal",
    "ParameterInputModal",
    "ParametersModal",
    "SnapshotActionMenuModal",
    "SnapshotCommentModal",
    "SnapshotDetailsModal",
    "ToolLaunchResult",
]


# ---------------------------------------------------------------------------
# Parameter-edit modal
# ---------------------------------------------------------------------------


class ParameterInputModal(ModalScreen[str | None]):
    """Modal for entering a new numeric/timedelta parameter value."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, param_name: str, current: str, unit: str) -> None:
        """Initialise the modal.

        Args:
            param_name: Display name of the parameter being edited.
            current: Current value shown as the default input text.
            unit: Unit label appended to the hint (e.g. `"s"` for seconds).
        """
        super().__init__()
        self._param_name = param_name
        self._current = current
        self._unit = unit

    def compose(self) -> ComposeResult:
        """Build the title, current-value hint, input field and save/cancel hint."""
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
        """Focus the input field."""
        self.query_one(Input).focus()

    @on(Input.Submitted)
    def submitted(self, event: Input.Submitted) -> None:
        """Dismiss with the submitted value."""
        self.dismiss(event.value.strip())

    def action_save(self) -> None:
        """Dismiss with the current input value."""
        self.dismiss(self.query_one("#param-input", Input).value.strip())

    def action_cancel(self) -> None:
        """Dismiss without a value."""
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
        """Build the no-project message and create/quit hint."""
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
        """Dismiss, indicating a project should be created."""
        self.dismiss(True)

    def action_quit_app(self) -> None:
        """Dismiss, indicating the application should quit."""
        self.dismiss(False)


# ---------------------------------------------------------------------------
# Schema-stale modal
# ---------------------------------------------------------------------------


class SchemaStaleModal(ModalScreen[bool]):
    """Shown on startup when the project's database schema is out of date.

    Blocks entry to the main UI entirely, mirroring `NoProjectModal` -
    proceeding into panels that query columns the live schema doesn't have
    would crash with a raw `sqlalchemy.exc.OperationalError` from whichever
    panel happens to touch the drifted table first, rather than a clean,
    attributable message. Dismisses True if the user chose to upgrade now,
    False to quit.
    """

    BINDINGS = [
        Binding("u", "upgrade", show=False),
        Binding("enter", "upgrade", show=False),
        Binding("q", "quit_app", show=False),
        Binding("escape", "quit_app", show=False),
    ]

    def __init__(self, message: str) -> None:
        """Initialise the modal.

        Args:
            message: The staleness message from `_build_staleness_warning`.
        """
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        """Build the staleness message and upgrade/quit hint."""
        with Container(id="confirm-dialog"):
            yield Label(self._message, classes=_CSS.TITLE)
            yield Label(
                "[@click='screen.upgrade'][bold]u[/bold] / ⏎ upgrade now[/]"
                "   "
                "[@click='screen.quit_app'][bold]q[/bold] / ⎋ quit[/]",
                classes=_CSS.HINT,
            )

    def action_upgrade(self) -> None:
        """Dismiss, indicating the database should be upgraded."""
        self.dismiss(True)

    def action_quit_app(self) -> None:
        """Dismiss, indicating the application should quit."""
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
        """Initialise the modal.

        Args:
            message: Confirmation prompt displayed to the user.
        """
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        """Build the confirmation message and confirm/cancel hint."""
        with Container(id="confirm-dialog"):
            yield Label(self._message, classes=_CSS.TITLE)
            yield Label(
                _Hint.CONFIRM_CANCEL,
                classes=_CSS.HINT,
            )

    def action_confirm(self) -> None:
        """Dismiss with confirmation."""
        self.dismiss(True)

    def action_cancel(self) -> None:
        """Dismiss with cancellation."""
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
        """Build the title, comment input and save/cancel hint."""
        with Container(id="param-edit-dialog"):
            yield Label("New Snapshot", classes=_CSS.TITLE)
            yield Input(placeholder="Comment (optional)", id="param-input")
            yield Label(
                _Hint.SAVE_CANCEL,
                classes=_CSS.HINT,
            )

    def on_mount(self) -> None:
        """Focus the comment input field."""
        self.query_one(Input).focus()

    @on(Input.Submitted)
    def submitted(self, event: Input.Submitted) -> None:
        """Dismiss with the submitted comment."""
        self.dismiss(event.value.strip())

    def action_save(self) -> None:
        """Dismiss with the current comment input value."""
        self.dismiss(self.query_one("#param-input", Input).value.strip())

    def action_cancel(self) -> None:
        """Dismiss without creating a snapshot."""
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
        """Initialise the modal.

        Args:
            event_id: ID of the event whose parameters are displayed.
        """
        super().__init__()
        self._event_id = event_id
        self._changed = False

    def compose(self) -> ComposeResult:
        """Build the title, parameter table and navigate/edit/close hint."""
        with Container(id="param-table-dialog"):
            yield Label("Parameters", classes=_CSS.TITLE)
            yield VimDataTable(id="param-modal-table", show_header=True)
            yield Label(_Hint.NAVIGATE_EDIT_CLOSE, classes=_CSS.HINT)

    def on_mount(self) -> None:
        """Configure the parameter table's columns and load its rows."""
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.add_columns("Parameter", "Value", "Description")
        self._populate()
        table.focus()

    def _populate(self) -> None:
        """Reload the parameter table from the database, preserving cursor position."""
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
        """Open the edit dialog for the selected parameter."""
        attr = event.row_key.value
        if not attr:
            return
        self._edit_parameter(attr)

    def _edit_parameter(self, attr: str) -> None:
        """Open an edit dialog for `attr`, toggling booleans inline."""
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
                new_val: Timedelta | float
                if isinstance(current, Timedelta):
                    new_val = Timedelta(seconds=float(raw))
                else:
                    new_val = float(raw)
                self._apply_parameter(attr, new_val)
            except ValueError as exc:
                self.notify(str(exc), severity="error")

        label = AimbatEventParametersBase.model_fields[attr].title or attr
        self.app.push_screen(ParameterInputModal(label, current_str, unit), on_input)

    def _apply_parameter(
        self, attr: str, value: Timedelta | bool | float | int | str
    ) -> None:
        """Persist a validated parameter change to the database."""
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
                )
        except ValidationError as exc:
            self.notify(format_validation_error(exc), severity="error")
            return
        except Exception as exc:
            self.notify(str(exc), severity="error")
            return
        self._changed = True
        self.notify(f"{attr} updated", timeout=2)
        self._populate()

    def action_select(self) -> None:
        """Trigger selection of the row under the cursor."""
        self.query_one(DataTable).action_select_cursor()

    def action_cancel(self) -> None:
        """Close the modal, reporting whether any parameter was changed."""
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
        """Initialise the modal.

        Args:
            title: Heading displayed at the top of the menu.
            actions: List of `(action_key, display_label)` pairs shown as rows.
        """
        super().__init__()
        self._title = title
        self._actions = actions  # [(action_key, display_label), ...]

    def compose(self) -> ComposeResult:
        """Build the title, action table and navigate/select/cancel hint."""
        with Container(id="action-menu-dialog"):
            yield Label(self._title, classes=_CSS.TITLE)
            yield VimDataTable(id="action-table", show_header=False)
            yield Label(
                _Hint.NAVIGATE_SELECT_CANCEL,
                classes=_CSS.HINT,
            )

    def on_mount(self) -> None:
        """Populate the action table from `_actions`."""
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.add_column("action")
        for key, label in self._actions:
            table.add_row(label, key=key)
        table.styles.height = len(self._actions)
        table.focus()

    @on(DataTable.RowSelected)
    def row_selected(self, event: DataTable.RowSelected) -> None:
        """Dismiss with the chosen action's key."""
        self.dismiss(event.row_key.value)

    def action_select(self) -> None:
        """Trigger selection of the row under the cursor."""
        self.query_one(DataTable).action_select_cursor()

    def action_cancel(self) -> None:
        """Dismiss without choosing an action."""
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Snapshot action menu modal
# ---------------------------------------------------------------------------

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

    def __init__(self, title: str, actions: list["RowAction"]) -> None:
        """Initialise the modal.

        Args:
            title: Heading displayed above the action list.
            actions: Row actions shown as rows (same registry the Snapshots
                tab's footer hotkeys are built from).
        """
        super().__init__()
        self._title = title
        self._actions = actions
        self._use_context = True
        self._all_seis = False
        self._highlighted: str = ""

    def compose(self) -> ComposeResult:
        """Build the title, action table, toggle options display and hint."""
        with Container(id="snapshot-action-dialog"):
            yield Label(self._title, classes=_CSS.TITLE)
            yield VimDataTable(id="snapshot-action-table", show_header=False)
            yield Static(id="snapshot-action-options")
            yield Label(_Hint.NAVIGATE_SELECT_CANCEL, classes=_CSS.HINT)

    def on_mount(self) -> None:
        """Populate the action table from `_actions`."""
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.add_column("action")
        for action in self._actions:
            table.add_row(action.label, key=action.id)
        table.styles.height = len(self._actions)
        table.focus()

    def _update_options(self) -> None:
        """Refresh the context/all-seismograms toggle display."""
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
        """Track the highlighted action and show its toggles if it is a preview action."""
        self._highlighted = event.row_key.value or ""
        self._update_options()

    @on(DataTable.RowSelected, "#snapshot-action-table")
    def row_selected(self, event: DataTable.RowSelected) -> None:
        """Dismiss with the chosen action and the current toggle values."""
        key = event.row_key.value
        if key:
            self.dismiss((key, self._use_context, self._all_seis))

    def action_toggle_context(self) -> None:
        """Toggle the context option, if the highlighted action is a preview action."""
        if self._highlighted in _PREVIEW_ACTIONS:
            self._use_context = not self._use_context
            self._update_options()

    def action_toggle_all(self) -> None:
        """Toggle the all-seismograms option, if the highlighted action is a preview action."""
        if self._highlighted in _PREVIEW_ACTIONS:
            self._all_seis = not self._all_seis
            self._update_options()

    def action_select(self) -> None:
        """Trigger selection of the row under the cursor."""
        self.query_one(DataTable).action_select_cursor()

    def action_cancel(self) -> None:
        """Dismiss without choosing an action."""
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Interactive Tools modal
# ---------------------------------------------------------------------------

_TOOLS: list[tuple[str, str]] = [
    (key, label) for key, (label, _) in (CAUSAL_TOOL_REGISTRY | TOOL_REGISTRY).items()
]


class ToolLaunchResult(NamedTuple):
    """Result of choosing a tool in `InteractiveToolsModal`.

    `causal` is `None` for tools that don't take a causal argument.
    """

    tool: str
    context: bool
    all_seismograms: bool
    causal: bool | None


class InteractiveToolsModal(ModalScreen[ToolLaunchResult | None]):
    """Menu for launching interactive matplotlib tools.

    Options are toggled with key bindings so no Checkbox widgets are needed.
    Dismisses with a `ToolLaunchResult` or None on cancel.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("c", "toggle_context", "Context", show=False),
        Binding("a", "toggle_all", "All", show=False),
        Binding("z", "toggle_zero_phase", "Zero-phase", show=False),
    ]

    def __init__(self) -> None:
        """Initialise the modal with context enabled and all-seismograms/causal defaults."""
        super().__init__()
        self._use_context = True
        self._all_seis = False
        self._highlighted_tool: str = ""
        self._causal: bool = True

    def compose(self) -> ComposeResult:
        """Build the title, tool table, toggle options display and hint."""
        with Container(id="tools-dialog"):
            yield Label("Tools", classes=_CSS.TITLE)
            yield VimDataTable(id="tools-table", show_header=False)
            yield Static(id="tools-options")
            yield Label(
                _Hint.NAVIGATE_RUN_CANCEL,
                classes=_CSS.HINT,
            )

    def on_mount(self) -> None:
        """Populate the tool table and set the causal default for the first tool."""
        table = self.query_one("#tools-table", DataTable)
        table.cursor_type = "row"
        table.add_column("tool")
        for key, label in _TOOLS:
            table.add_row(label, key=key)
        self._highlighted_tool = _TOOLS[0][0]
        self._causal = CAUSAL_DEFAULTS.get(self._highlighted_tool, True)
        self._update_options()
        table.focus()

    def _update_options(self) -> None:
        """Refresh the context/all-seismograms/zero-phase toggle display."""
        ctx = "✓" if self._use_context else "✗"
        al = "✓" if self._all_seis else "✗"
        options = (
            f"  [@click='screen.toggle_context'][dim]c[/dim] context: {ctx}[/]"
            f"   [@click='screen.toggle_all'][dim]a[/dim] all seismograms: {al}[/]"
        )
        if self._highlighted_tool in CAUSAL_DEFAULTS:
            zp = "✓" if not self._causal else "✗"
            options += f"   [@click='screen.toggle_zero_phase'][dim]z[/dim] zero-phase: {zp}[/]"
        self.query_one("#tools-options", Static).update(options)

    @on(DataTable.RowHighlighted, "#tools-table")
    def row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Track the highlighted tool and reset the causal toggle to its default."""
        self._highlighted_tool = event.row_key.value or ""
        self._causal = CAUSAL_DEFAULTS.get(self._highlighted_tool, True)
        self._update_options()

    @on(DataTable.RowSelected, "#tools-table")
    def row_selected(self, event: DataTable.RowSelected) -> None:
        """Dismiss with the chosen tool and the current toggle values."""
        key = event.row_key.value
        if key:
            causal = self._causal if key in CAUSAL_DEFAULTS else None
            self.dismiss(
                ToolLaunchResult(key, self._use_context, self._all_seis, causal)
            )

    def action_toggle_context(self) -> None:
        """Toggle the context option."""
        self._use_context = not self._use_context
        self._update_options()

    def action_toggle_all(self) -> None:
        """Toggle the all-seismograms option."""
        self._all_seis = not self._all_seis
        self._update_options()

    def action_toggle_zero_phase(self) -> None:
        """Toggle the causal/zero-phase filter option, if the highlighted tool supports it."""
        if self._highlighted_tool in CAUSAL_DEFAULTS:
            self._causal = not self._causal
            self._update_options()

    def action_select(self) -> None:
        """Trigger selection of the row under the cursor."""
        self.query_one(DataTable).action_select_cursor()

    def action_cancel(self) -> None:
        """Dismiss without choosing a tool."""
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
        """Initialise the modal with all toggles off and ICCS as the highlighted algorithm."""
        super().__init__()
        self._autoflip = False
        self._autoselect = False
        self._all_seis = False
        self._highlighted_algorithm: str = "iccs"

    def compose(self) -> ComposeResult:
        """Build the title, algorithm table, toggle options display and hint."""
        with Container(id="align-dialog"):
            yield Label("Align Seismograms", classes=_CSS.TITLE)
            yield VimDataTable(id="align-table", show_header=False)
            yield Static(id="align-options")
            yield Label(
                _Hint.NAVIGATE_RUN_CANCEL,
                classes=_CSS.HINT,
            )

    def on_mount(self) -> None:
        """Populate the algorithm table."""
        table = self.query_one("#align-table", DataTable)
        table.cursor_type = "row"
        table.add_column("algorithm")
        for key, label in _ALIGN_ALGORITHMS:
            table.add_row(label, key=key)
        self._update_options()
        table.focus()

    def _update_options(self) -> None:
        """Refresh the algorithm-specific option toggles."""
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
        """Track the highlighted algorithm and show its option toggles."""
        self._highlighted_algorithm = event.row_key.value or "iccs"
        self._update_options()

    @on(DataTable.RowSelected, "#align-table")
    def row_selected(self, event: DataTable.RowSelected) -> None:
        """Dismiss with the chosen algorithm and the current toggle values."""
        key = event.row_key.value
        if key:
            self.dismiss((key, self._autoflip, self._autoselect, self._all_seis))

    def action_toggle_autoflip(self) -> None:
        """Toggle the ICCS autoflip option, if ICCS is the highlighted algorithm."""
        if self._highlighted_algorithm == "iccs":
            self._autoflip = not self._autoflip
            self._update_options()

    def action_toggle_autoselect(self) -> None:
        """Toggle the ICCS autoselect option, if ICCS is the highlighted algorithm."""
        if self._highlighted_algorithm == "iccs":
            self._autoselect = not self._autoselect
            self._update_options()

    def action_toggle_all(self) -> None:
        """Toggle the MCCC all-seismograms option, if MCCC is the highlighted algorithm."""
        if self._highlighted_algorithm == "mccc":
            self._all_seis = not self._all_seis
            self._update_options()

    def action_select(self) -> None:
        """Trigger selection of the row under the cursor."""
        self.query_one(DataTable).action_select_cursor()

    def action_cancel(self) -> None:
        """Dismiss without choosing an algorithm."""
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
        """Initialise the modal.

        Args:
            title: Heading displayed above the parameter table.
            rows: List of `(label, value)` pairs to display as read-only rows.
        """
        super().__init__()
        self._title = title
        self._rows = rows  # [(label, value), ...]

    def compose(self) -> ComposeResult:
        """Build the title, read-only parameter table and close hint."""
        with Container(id="snapshot-details-dialog"):
            yield Label(self._title, classes=_CSS.TITLE)
            yield VimDataTable(id="snapshot-details-table", show_header=True)
            yield Label(_Hint.CLOSE, classes=_CSS.HINT)

    def on_mount(self) -> None:
        """Populate the table from `_rows`."""
        table = self.query_one(DataTable)
        table.cursor_type = "none"
        table.add_columns("Parameter", "Value")
        for row in self._rows:
            table.add_row(*row)
        table.styles.height = len(self._rows) + 2

    def action_cancel(self) -> None:
        """Close the modal."""
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Help modal
# ---------------------------------------------------------------------------

_HELP_DIR = Path(__file__).parent / "help"
_HELP_FALLBACK = "No help available for this tab."


def _load_help(tab_id: str) -> str:
    """Load help Markdown for the given tab from a file.

    Args:
        tab_id: The `TabPane` ID (e.g. `tab-project`).

    Returns:
        Markdown text, or a fallback string if no file exists.
    """
    path = _HELP_DIR / f"{tab_id}.md"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return _HELP_FALLBACK


class HelpModal(ModalScreen[None]):
    """Modal screen showing keyboard help for the current TUI tab."""

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=False),
        Binding("question_mark", "cancel", "Close", show=False),
    ]

    def __init__(self, tab_id: str) -> None:
        """Initialise the modal for the given tab.

        Args:
            tab_id: The ID of the active `TabPane` whose help to display.
        """
        super().__init__()
        self._tab_id = tab_id

    def compose(self) -> ComposeResult:
        """Build the title, rendered help Markdown and close hint."""
        with Container(id="help-dialog"):
            yield Label("Help", classes=_CSS.TITLE)
            yield Markdown(_load_help(self._tab_id), id="help-content")
            yield Label(_Hint.CLOSE, classes=_CSS.HINT)

    def action_cancel(self) -> None:
        """Close the modal."""
        self.dismiss(None)
