"""Unit tests for aimbat._cli.common._decorators."""

import pytest

from aimbat._cli.common import print_error_panel


class TestPrintErrorPanel:
    """Tests for the error panel shown when a command fails."""

    def test_notes_are_shown_alongside_the_message(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verifies that context attached as a note reaches the user.

        Ingestion attaches the offending data source this way, so a panel
        that only rendered `str(exc)` would drop it.

        Args:
            capsys: The pytest capsys fixture.
        """
        exc = ValueError("something failed")
        exc.add_note("Data source: somefile.sac")
        print_error_panel(exc)
        captured = capsys.readouterr().err
        assert "something failed" in captured
        assert "Data source: somefile.sac" in captured
