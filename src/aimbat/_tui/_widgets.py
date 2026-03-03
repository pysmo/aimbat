"""Reusable Textual widgets for the AIMBAT TUI."""

from textual.binding import Binding
from textual.widgets import DataTable

__all__ = ["VimDataTable"]


class VimDataTable(DataTable):
    """DataTable with vim-style navigation keys.

    Adds j/k for cursor down/up, h/l for cursor left/right (aliases for the
    existing cursor actions) and g/G for jumping to the first/last row.
    """

    BINDINGS = [
        Binding("h", "cursor_left", "Cursor left", show=False),
        Binding("j", "cursor_down", "Cursor down", show=False),
        Binding("k", "cursor_up", "Cursor up", show=False),
        Binding("l", "cursor_right", "Cursor right", show=False),
        Binding("g", "scroll_home", "Scroll to top", show=False),
        Binding("G", "scroll_end", "Scroll to bottom", show=False),
    ]

    def action_scroll_home(self) -> None:
        self.move_cursor(row=0)

    def action_scroll_end(self) -> None:
        if self.row_count > 0:
            self.move_cursor(row=self.row_count - 1)
