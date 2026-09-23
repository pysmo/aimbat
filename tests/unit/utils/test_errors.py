"""Unit tests for aimbat.utils._errors."""

from aimbat.utils import exception_message


class TestExceptionMessage:
    """Tests for the exception_message function."""

    def test_plain_exception_is_unchanged(self) -> None:
        """Verifies that an exception without notes renders as its message."""
        assert exception_message(ValueError("boom")) == "boom"

    def test_notes_are_appended_in_order(self) -> None:
        """Verifies that notes follow the message, one per line, in order."""
        exc = ValueError("boom")
        exc.add_note("first note")
        exc.add_note("second note")
        assert exception_message(exc) == "boom\nfirst note\nsecond note"
