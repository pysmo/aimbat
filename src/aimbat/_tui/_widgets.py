"""Reusable Textual widgets for the AIMBAT TUI."""

import uuid
from contextlib import suppress

from sqlmodel import Session
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable, Markdown, TabbedContent, TabPane, TextArea
from textual_plotext import PlotextPlot

from aimbat.core import get_note_content, save_note
from aimbat.db import engine

__all__ = ["NoteWidget", "SeismogramPlotWidget", "VimDataTable"]


class VimDataTable(DataTable):
    """DataTable with vim-style navigation keys.

    Adds j/k for cursor down/up, h/l for cursor left/right (aliases for the
    existing cursor actions) and g/G for jumping to the first/last row.
    """

    class Focused(Message):
        """Posted when this table gains keyboard focus."""

        def __init__(self, table: "VimDataTable") -> None:
            super().__init__()
            self.table = table

        @property
        def control(self) -> "VimDataTable":
            return self.table

    BINDINGS = [
        Binding("h", "cursor_left", "Cursor left", show=False),
        Binding("j", "cursor_down", "Cursor down", show=False),
        Binding("k", "cursor_up", "Cursor up", show=False),
        Binding("l", "cursor_right", "Cursor right", show=False),
        Binding("g", "scroll_home", "Scroll to top", show=False),
        Binding("G", "scroll_end", "Scroll to bottom", show=False),
    ]

    def on_focus(self) -> None:
        self.post_message(self.Focused(self))

    def action_scroll_home(self) -> None:
        self.move_cursor(row=0)

    def action_scroll_end(self) -> None:
        if self.row_count > 0:
            self.move_cursor(row=self.row_count - 1)


class SeismogramPlotWidget(Widget):
    """Displays CC and context seismograms for a highlighted seismogram.

    Call `update_plots` to load new data, or `clear` to reset the widget
    when no seismogram is selected.
    """

    BORDER_TITLE = "Seismogram"

    def compose(self) -> ComposeResult:
        with TabbedContent(initial="seis-plot-tab-cc"):
            with TabPane("CC", id="seis-plot-tab-cc"):
                yield PlotextPlot(id="seis-cc-plot")
            with TabPane("Context", id="seis-plot-tab-context"):
                yield PlotextPlot(id="seis-context-plot")

    def update_plots(
        self,
        cc_times: list[float],
        cc_data: list[float],
        context_times: list[float],
        context_data: list[float],
    ) -> None:
        """Update both plot tabs with new seismogram data.

        Args:
            cc_times: Time values relative to pick (seconds) for the CC seismogram.
            cc_data: Amplitude data for the CC seismogram.
            context_times: Time values relative to pick (seconds) for the context seismogram.
            context_data: Amplitude data for the context seismogram.
        """
        for plot_id, times, data in (
            ("#seis-cc-plot", cc_times, cc_data),
            ("#seis-context-plot", context_times, context_data),
        ):
            with suppress(NoMatches):
                p = self.query_one(plot_id, PlotextPlot)
                p.plt.clf()
                p.plt.xlabel("Time relative to pick (s)")
                p.plt.yfrequency(0)
                p.plt.plot(times, data, marker="braille")
                p.refresh()

    def clear(self) -> None:
        """Clear both plots."""
        for plot_id in ("#seis-cc-plot", "#seis-context-plot"):
            with suppress(NoMatches):
                p = self.query_one(plot_id, PlotextPlot)
                p.plt.clf()
                p.refresh()


class _NoteTextArea(TextArea):
    """TextArea that posts a bubbling message when it loses focus."""

    class Blurred(Message):
        """Posted when the edit area loses keyboard focus."""

    def on_blur(self) -> None:
        self.post_message(self.Blurred())


class NoteWidget(Widget):
    """View/edit Markdown note for an event, station, seismogram, or snapshot.

    Call `set_entity` to load the note for an entity, or `clear` to reset the
    widget when no entity is selected. Changes are auto-saved whenever the edit
    area loses focus or the View tab is activated.
    """

    BORDER_TITLE = "Note"

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._target_type: str | None = None
        self._target_id: uuid.UUID | None = None
        self._saved_content: str = ""

    def compose(self) -> ComposeResult:
        with TabbedContent(id="note-tabs"):
            with TabPane("View", id="note-tab-view"):
                yield Markdown("", id="note-markdown")
            with TabPane("Edit", id="note-tab-edit"):
                yield _NoteTextArea("", id="note-textarea")

    def set_entity(self, target_type: str, target_id: uuid.UUID) -> None:
        """Load the note for the given entity and display it.

        Args:
            target_type: One of `event`, `station`, `seismogram`, `snapshot`.
            target_id: UUID of the target entity.
        """
        self._target_type = target_type
        self._target_id = target_id
        with Session(engine) as session:
            content = get_note_content(session, target_type, target_id)  # type: ignore[arg-type]
        self._saved_content = content
        with suppress(NoMatches):
            placeholder = "_No note yet. Switch to Edit to add one._"
            self.query_one("#note-markdown", Markdown).update(content or placeholder)
            self.query_one("#note-textarea", _NoteTextArea).load_text(content)
            self.query_one("#note-tabs", TabbedContent).active = "note-tab-view"

    def clear(self) -> None:
        """Clear the note display — call when no entity is selected."""
        self._target_type = None
        self._target_id = None
        self._saved_content = ""
        with suppress(NoMatches):
            self.query_one("#note-markdown", Markdown).update("")
            self.query_one("#note-textarea", _NoteTextArea).load_text("")
            self.query_one("#note-tabs", TabbedContent).active = "note-tab-view"

    @on(_NoteTextArea.Blurred)
    def _on_textarea_blur(self) -> None:
        self._auto_save()

    @on(TabbedContent.TabActivated, "#note-tabs")
    def _on_note_tab_switch(self, event: TabbedContent.TabActivated) -> None:
        if event.pane.id == "note-tab-view":
            self._auto_save()
            with suppress(NoMatches):
                content = self.query_one("#note-textarea", _NoteTextArea).text
                placeholder = "_No note yet. Switch to Edit to add one._"
                self.query_one("#note-markdown", Markdown).update(
                    content or placeholder
                )

    def _auto_save(self) -> None:
        if self._target_type is None or self._target_id is None:
            return
        content = self._saved_content
        with suppress(NoMatches):
            content = self.query_one("#note-textarea", _NoteTextArea).text
        if content != self._saved_content:
            with Session(engine) as session:
                save_note(session, self._target_type, self._target_id, content)  # type: ignore[arg-type]
            self._saved_content = content
