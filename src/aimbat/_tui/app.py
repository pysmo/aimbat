"""AIMBAT Terminal User Interface application."""

from __future__ import annotations

import uuid
from collections.abc import Generator
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

from aimbat import settings
from aimbat._tui._iccs_lifecycle import _IccsLifecycleMixin
from aimbat._tui._panels import ProjectPanel, SeismogramPanel, SnapshotPanel
from aimbat._tui._tools import CAUSAL_TOOL_REGISTRY, TOOL_REGISTRY, VIEW_ONLY_TOOLS
from aimbat._tui.modals import (
    ActionMenuModal,
    AlignModal,
    ConfirmModal,
    HelpModal,
    InteractiveToolsModal,
    NoProjectModal,
    ParametersModal,
    SchemaStaleModal,
    SnapshotCommentModal,
    SnapshotDetailsModal,
    ToolLaunchResult,
)
from aimbat._types import SeismogramParameter
from aimbat.core import (
    BoundICCS,
    add_data_to_project,
    build_iccs_from_snapshot,
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
    toggle_event_completed,
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
from aimbat.plot import plot_matrix_image, plot_seismograms, plot_stack
from aimbat.utils.formatters import fmt_timestamp

from ._format import tui_cell, tui_display_title

_DEFAULT_THEME = settings.tui_dark_theme
_LIGHT_THEME = settings.tui_light_theme

_MAIN_TABS = {"tab-project", "tab-seismograms", "tab-snapshots"}


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------


class AimbatTUI(_IccsLifecycleMixin, App[None]):
    """Root screen of the AIMBAT Terminal User Interface.

    Composes a header, an event status bar, a tabbed content area (Project,
    Live data, Snapshots) and a footer. Owns the current active event, the
    long-lived `BoundICCS` instance used by the Live data tab and the
    interactive tools (lifecycle managed by `_IccsLifecycleMixin`), and
    dispatches row actions and key bindings to the corresponding core
    functions.
    """

    TITLE = "AIMBAT"
    CSS_PATH = "aimbat.tcss"

    BINDINGS = [
        Binding("i", "add_data", "Add Data", show=True),
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
        """Build the header, event bar, tabbed panels and footer."""
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
        """Initialise TUI state and start the application.

        If no project exists in the current directory, prompts to create
        one. If a project exists but its database schema is out of date,
        prompts to upgrade before entry is allowed. Otherwise creates the
        ICCS instance for the current event (if any) and populates all
        panels. Also starts the periodic ICCS staleness check.
        """
        self._init_iccs_lifecycle()
        self._current_event_id: uuid.UUID | None = None
        self._active_tab: str = "tab-project"

        self.theme = _DEFAULT_THEME

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
        """Handle the result of `NoProjectModal`.

        Creates a new project and the ICCS instance if the user opted in,
        otherwise exits the application.

        Args:
            create: Whether the user chose to create a new project.
        """
        if create:
            logger.info("User chose to create a new project.")
            create_project(engine)
            self._create_iccs()
            self.refresh_all()
        else:
            logger.info("User declined to create a project. Exiting.")
            self.exit()

    def _on_schema_stale_modal(self, upgrade: bool | None) -> None:
        """Handle the result of `SchemaStaleModal`.

        Exits the application if the user declines to upgrade. Otherwise
        runs the database upgrade and, on success, creates the ICCS
        instance and refreshes all panels. Exits with an error message if
        the upgrade itself fails.

        Args:
            upgrade: Whether the user chose to upgrade the project database.
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
        """Track the active main tab and focus its table.

        Updates `_active_tab`, refreshes key-binding availability, moves
        focus to the tab's `DataTable` unless a `Tabs` widget already has
        focus, and clears the highlighted row's detail panels when
        switching into an empty Live data or Snapshots tab.
        """
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
        """Enable or disable key bindings based on the active tab and selected event.

        Args:
            action: Name of the action being checked.
            parameters: Arguments the action would be called with.

        Returns:
            Whether the action is currently available.
        """
        if action == "add_data":
            return self._active_tab == "tab-project"
        if action == "new_snapshot":
            return (
                self._active_tab == "tab-seismograms"
                and self._current_event_id is not None
            )
        if action in {"open_interactive_tools", "open_align"}:
            return (
                self._active_tab == "tab-seismograms"
                and self._current_event_id is not None
            )
        if action == "open_parameters":
            if self._current_event_id is None:
                return False
            if self._active_tab == "tab-seismograms":
                return True
            if self._active_tab == "tab-project":
                # `self.focused` is the DataTable itself when a table has
                # keyboard focus (DataTable has no focusable descendants), so
                # comparing its id directly is sufficient - this would need
                # revisiting if DataTable ever grew focusable child widgets.
                return getattr(self.focused, "id", None) == "project-event-table"
            return False
        return True

    # ------------------------------------------------------------------
    # Event selection
    # ------------------------------------------------------------------

    def _get_current_event(self, session: Session) -> AimbatEvent:
        """Return the event currently selected for processing in the TUI.

        Clears a stale `_current_event_id` if the referenced event no longer
        exists.

        Args:
            session: Database session used to look up the event.

        Returns:
            The currently selected event.

        Raises:
            NoResultFound: If no event has been selected, or the previously
                selected event no longer exists.
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
        return" hint.  Any exception raised inside the block — including
        `KeyboardInterrupt` — is shown in the terminal while still suspended,
        then re-raised after Textual has fully resumed so callers can still
        react to it.
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
            except KeyboardInterrupt as exc:
                caught = exc
                console.print("\n[bold yellow]Cancelled.[/bold yellow]")
                console.input("\n[dim]Press Enter to return to AIMBAT...[/dim]")
            except Exception as exc:
                caught = exc
                console.print(f"\n[bold red]Error:[/bold red] {exc}")
                console.input("\n[dim]Press Enter to return to AIMBAT...[/dim]")
            finally:
                console.clear()
        if caught is not None:
            raise caught

    # ------------------------------------------------------------------
    # Data refresh
    # ------------------------------------------------------------------

    def refresh_all(self) -> None:
        """Refresh every panel to reflect the current database state.

        The default choice after any mutation. A targeted
        `<Panel>.refresh_data(...)` call is appropriate only when no other
        panel's displayed data (including `column_property` counts and the
        live quality getters) is affected by the change; record that
        reasoning as a comment at the call site.
        """
        self.refresh_bindings()
        self._refresh_event_bar()
        self.query_one(ProjectPanel).refresh_data(self._current_event_id)
        self.query_one(SeismogramPanel).refresh_data(
            self._current_event_id, self._iccs_lifecycle.bound
        )
        self.query_one(SnapshotPanel).refresh_data(self._current_event_id)

    def _refresh_event_bar(self) -> None:
        """Update the status bar with the current event's time, location and ICCS status.

        Shows a prompt to select an event or add data when no event is
        selected, or an error message if the current event could not be
        loaded.
        """
        bar = self.query_one("#event-bar", Static)
        try:
            with Session(engine) as session:
                event = self._get_current_event(session)
                iccs_status = (
                    " ● ICCS ready" if self._iccs_lifecycle.ready else " ○ no ICCS"
                )
                time_str = fmt_timestamp(event.time) if event.time else "unknown"
                lat = f"{event.latitude:.3f}°"
                lon = f"{event.longitude:.3f}°"
                modified = (
                    f"  modified: {fmt_timestamp(event.last_modified)}"
                    if event.last_modified is not None
                    else ""
                )
                bar.update(
                    f"▶ {time_str}  |  {lat}, {lon}{modified}"
                    f"  [dim]{iccs_status}  switch events on the Project tab[/dim]"
                )
        except NoResultFound:
            with Session(engine) as session:
                has_events = session.exec(select(AimbatEvent)).first() is not None
            if has_events:
                bar.update(
                    "[red]No event selected — select one on the Project tab[/red]"
                )
            else:
                bar.update("[red]No data in project — press i to add data[/red]")
        except RuntimeError as exc:
            bar.update(f"[red]{exc}[/red]")

    # ------------------------------------------------------------------
    # Row event handlers
    # ------------------------------------------------------------------

    @on(ProjectPanel.RowActionChosen)
    def _project_row_action_chosen(self, message: ProjectPanel.RowActionChosen) -> None:
        """Dispatch a row action chosen on the Project tab."""
        self._handle_row_action(message.tab, message.item_id, message.action)

    @on(SeismogramPanel.RowActionChosen)
    def _seismogram_row_action_chosen(
        self, message: SeismogramPanel.RowActionChosen
    ) -> None:
        """Dispatch a row action chosen on the Live data tab."""
        self._handle_row_action("tab-seismograms", message.item_id, message.action)

    @on(SnapshotPanel.ActionChosen)
    def _snapshot_action_chosen(self, message: SnapshotPanel.ActionChosen) -> None:
        """Dispatch a row action chosen on the Snapshots tab.

        Preview and results-saving actions are handled directly since they
        carry extra `context`/`all_seismograms` options not shared with the
        other tabs' row actions; all other actions go through
        `_handle_row_action`.
        """
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
        """Route a row action chosen from a table's action menu or footer hotkey to its handler.

        Args:
            tab: ID of the tab the row belongs to.
            item_id: ID of the row's underlying database entity.
            action: Action key chosen, or `None` if the menu was cancelled.
        """
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
        """Make the given event the active event and rebuild its ICCS instance."""
        logger.debug(f"User selected event {item_id[:8]}.")
        self._current_event_id = uuid.UUID(item_id)
        self._create_iccs()
        self.refresh_all()
        self.notify("Event selected", timeout=2)

    def _toggle_event_completed(self, item_id: str) -> None:
        """Flip the `completed` flag on the given event's parameters."""
        logger.debug(f"User toggled completed flag for event {item_id[:8]}.")
        try:
            with Session(engine) as session:
                toggle_event_completed(session, uuid.UUID(item_id))
            self.refresh_all()
            self.notify("Completed flag toggled", timeout=2)
        except Exception as exc:
            self.notify(str(exc), severity="error")

    def _view_seismograms(self, tab: str, item_id: str) -> None:
        """Suspend the TUI and show a matplotlib plot of seismograms for an event or station.

        Args:
            tab: Tab the row belongs to; determines whether `item_id`
                refers to an event or a station.
            item_id: ID of the event or station whose seismograms to plot.
        """
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
        except KeyboardInterrupt:
            pass
        except Exception as exc:
            self.notify(str(exc), severity="error")

    def _toggle_seismogram_bool(self, item_id: str, param: SeismogramParameter) -> None:
        """Flip a boolean seismogram parameter (select or flip) and update the in-memory ICCS instance.

        Persists the new value to the database, then updates the matching
        seismogram in the live ICCS instance directly and refreshes only
        the Live data table, without a full `refresh_all`.

        Args:
            item_id: ID of the seismogram to update.
            param: Boolean parameter to toggle.
        """
        logger.debug(f"User toggled {param} for seismogram {item_id[:8]}.")
        try:
            seis_uuid = uuid.UUID(item_id)
            with Session(engine) as session:
                seis = session.get(AimbatSeismogram, seis_uuid)
                if seis is None:
                    raise ValueError(f"Seismogram {item_id} not found")
                new_value = not getattr(seis.parameters, param)
                set_seismogram_parameter(session, seis_uuid, param, new_value)
            bound = self._iccs_lifecycle.bound
            if bound is not None:
                for iccs_seis in bound.iccs.seismograms:
                    if iccs_seis.extra.get("id") == seis_uuid:
                        setattr(iccs_seis, param, new_value)
                        bound.iccs.clear_cache()
                        bound.created_at = Timestamp.now("UTC")
                        break
            # Deliberately scoped: this only mutates the in-memory ICCS instance
            # and clears its cache, without re-upserting iccs_cc, so no other
            # panel's displayed data (quality panels, station cc_mean/cc_sem)
            # changes here. Also repeated once per seismogram during QC review,
            # so avoid the extra DB round trips a full refresh_all() would add.
            self.query_one(SeismogramPanel).refresh_data(
                self._current_event_id, self._iccs_lifecycle.bound
            )
            self.notify(f"{param} toggled", timeout=2)
        except Exception as exc:
            self.notify(str(exc), severity="error")

    def _reset_seismogram_parameters(self, item_id: str) -> None:
        """Reset a seismogram's processing parameters to their defaults."""
        logger.debug(f"User reset parameters for seismogram {item_id[:8]}.")
        try:
            with Session(engine) as session:
                reset_seismogram_parameters(session, uuid.UUID(item_id))
            self.refresh_all()
            self.notify("Seismogram parameters reset", timeout=2)
        except Exception as exc:
            self.notify(str(exc), severity="error")

    def _confirm_delete(self, tab: str, item_id: str) -> None:
        """Show a confirmation dialog, then delete the row's entity if confirmed.

        Args:
            tab: Tab the row belongs to; determines which entity type
                `item_id` refers to (event, station, seismogram or
                snapshot).
            item_id: ID of the entity to delete.
        """
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
                        self._iccs_lifecycle.clear()
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
        """Open a modal listing the event parameters captured in a snapshot."""
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
        """Prompt for a file path and write a snapshot's results to it as JSON."""
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
        """Suspend the TUI and show a matplotlib stack or matrix-image plot rebuilt from a snapshot.

        Args:
            snap_id: ID of the snapshot to rebuild ICCS from.
            plot_type: Either `"stack"` or `"image"`.
            context: Whether to plot the context window rather than the CC window.
            all_seis: Whether to include seismograms not currently selected.
        """
        logger.debug(f"User previewing {plot_type} plot for snapshot {snap_id[:8]}.")
        try:
            with self._suspend("Previewing snapshot"):
                with Session(engine) as session:
                    bound = build_iccs_from_snapshot(session, uuid.UUID(snap_id))
                if plot_type == "stack":
                    plot_stack(bound.iccs, context, all_seis, return_fig=False)
                else:
                    plot_matrix_image(bound.iccs, context, all_seis, return_fig=False)
        except KeyboardInterrupt:
            pass
        except Exception as exc:
            logger.exception(f"Snapshot preview failed: {exc}")
            self.notify(str(exc), severity="error")

    def _confirm_rollback(self, snap_id: str) -> None:
        """Show a confirmation dialog, then roll the active event back to a snapshot if confirmed."""

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
        """Open the parameters modal for the current event, recreating ICCS if changed."""
        logger.debug("User opened parameters modal.")
        try:
            with Session(engine) as session:
                event = self._get_current_event(session)
                event_id = event.id
        except NoResultFound:
            self.notify(
                "No event selected — select one on the Project tab",
                severity="warning",
            )
            return

        def on_close(changed: bool | None) -> None:
            if changed:
                logger.info("Parameters changed; recreating ICCS.")
                self._create_iccs()
                self.refresh_all()

        self.push_screen(ParametersModal(event_id), on_close)

    def action_add_data(self) -> None:
        """Prompt for a data type, then a data source, and add it to the project."""
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

    def action_open_interactive_tools(self) -> None:
        """Open the interactive tools menu and run the chosen tool."""
        if not self._require_iccs():
            return

        def on_result(result: ToolLaunchResult | None) -> None:
            if result is not None:
                self._run_tool(
                    result.tool, result.context, result.all_seismograms, result.causal
                )

        self.push_screen(InteractiveToolsModal(), on_result)

    def _run_tool(
        self, tool: str, context: bool, all_seis: bool, causal: bool | None
    ) -> None:
        """Run an interactive tool from `TOOL_REGISTRY` or `CAUSAL_TOOL_REGISTRY`.

        Uses the long-lived ICCS instance so waveform data do not need to be
        reloaded. Suspends the TUI while the tool's matplotlib window is
        open and refreshes all panels once it closes.

        Args:
            tool: Key identifying the tool in the registry.
            context: Whether to operate on the context window rather than
                the CC window.
            all_seis: Whether to include seismograms not currently selected.
            causal: Zero-phase/causal filter setting; only meaningful for
                tools in `CAUSAL_TOOL_REGISTRY`, otherwise `None`.
        """
        logger.debug(
            f"User launched interactive tool '{tool}' "
            f"(context={context}, all_seis={all_seis}, causal={causal})."
        )
        bound = self._iccs_lifecycle.bound
        if bound is None:
            self.notify("ICCS not ready — please wait", severity="warning")
            return
        iccs = bound.iccs
        is_causal_tool = tool in CAUSAL_TOOL_REGISTRY
        label = (
            CAUSAL_TOOL_REGISTRY[tool][0] if is_causal_tool else TOOL_REGISTRY[tool][0]
        )

        try:
            with self._suspend(label):
                with Session(engine) as session:
                    event = self._get_current_event(session)
                    if is_causal_tool:
                        assert causal is not None
                        CAUSAL_TOOL_REGISTRY[tool][1](
                            session, event, iccs, context, all_seis, causal
                        )
                    else:
                        TOOL_REGISTRY[tool][1](session, event, iccs, context, all_seis)
        except KeyboardInterrupt:
            self.notify(f"{label} cancelled", timeout=2)
            return
        except Exception as exc:
            logger.exception(f"Interactive tool '{tool}' raised: {exc}")
            self.notify(str(exc), severity="error")
            return

        if tool in VIEW_ONLY_TOOLS:
            # Nothing changed. suspend() is synchronous, so the staleness poller
            # cannot fire between here and this assignment.
            bound.created_at = Timestamp.now("UTC")
            self.refresh_all()
        else:
            # The tool persisted a parameter or pick change: the triggers have
            # nulled iccs_cc and the in-memory instance is now stale. Rebuild it
            # (which re-persists iccs_cc and refreshes every panel), matching the
            # Parameters modal's on-close behaviour.
            self._create_iccs()
        self.notify("Done", timeout=2)

    def action_open_align(self) -> None:
        """Open the alignment menu and run the chosen algorithm (ICCS or MCCC)."""
        if not self._require_iccs():
            return

        def on_result(result: tuple[str, bool, bool, bool] | None) -> None:
            if result is not None:
                self._run_align_tool(self._iccs_lifecycle.bound, *result)

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
        """Run ICCS or MCCC in a background thread and post the result to the main thread.

        Args:
            bound: The current `BoundICCS` instance to align.
            algorithm: Either `"iccs"` or `"mccc"`.
            autoflip: Whether ICCS should automatically flip polarity-reversed
                seismograms.
            autoselect: Whether ICCS should automatically deselect
                poorly-correlated seismograms.
            all_seis: Whether MCCC should run over all seismograms rather
                than only the selected ones.
        """
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
        """Refresh all panels and show the alignment result notification.

        Args:
            msg: Notification text.
            severity: Notification severity level.
        """
        self.refresh_all()
        self.notify(msg, severity=severity, timeout=4)

    def action_new_snapshot(self) -> None:
        """Prompt for an optional comment and create a snapshot of the current event's parameters."""

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
        """Switch to the previous main tab, unless a modal is open."""
        if not isinstance(self.screen, ModalScreen):
            self.query_one(TabbedContent).query_one(Tabs).action_previous_tab()

    def action_vim_right(self) -> None:
        """Switch to the next main tab, unless a modal is open."""
        if not isinstance(self.screen, ModalScreen):
            self.query_one(TabbedContent).query_one(Tabs).action_next_tab()

    def action_toggle_theme(self) -> None:
        """Toggle between the configured dark and light themes."""
        self.theme = _LIGHT_THEME if self.theme == _DEFAULT_THEME else _DEFAULT_THEME

    def action_show_help(self) -> None:
        """Open the help modal for the active tab."""
        self.push_screen(HelpModal(self._active_tab))

    def action_refresh(self) -> None:
        """Refresh all panels on demand."""
        logger.debug("User triggered manual refresh.")
        self.refresh_all()
        self.notify("Refreshed", timeout=1)


def main() -> None:
    """Run the AIMBAT TUI until it exits.

    Raises:
        RuntimeError: If the TUI exited after an unhandled exception (a
            non-zero `App.return_code`), so the process reports failure
            rather than exiting 0 despite the crash.
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
