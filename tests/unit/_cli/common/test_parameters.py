"""Unit tests for aimbat._cli.common."""

import warnings

import pytest

from aimbat import settings
from aimbat._cli.common import (
    IccsPlotParameters,
    TableParameters,
    handle_issues,
)
from aimbat.core._migrations import SchemaStaleWarning


class TestIccsPlotParameters:
    """Tests for the IccsPlotParameters dataclass."""

    def test_default_context_is_true(self) -> None:
        """Verifies that context defaults to True."""
        params = IccsPlotParameters()
        assert params.context is True

    def test_default_all_seismograms_is_false(self) -> None:
        """Verifies that all_seismograms defaults to False."""
        params = IccsPlotParameters()
        assert params.all_seismograms is False

    def test_context_can_be_set_false(self) -> None:
        """Verifies that context can be set to False."""
        params = IccsPlotParameters(context=False)
        assert params.context is False

    def test_all_seismograms_can_be_set_true(self) -> None:
        """Verifies that all_seismograms can be set to True."""
        params = IccsPlotParameters(all_seismograms=True)
        assert params.all_seismograms is True


class TestTableParameters:
    """Tests for the TableParameters dataclass."""

    def test_default_raw_is_false(self) -> None:
        """Verifies that raw defaults to False."""
        params = TableParameters()
        assert params.raw is False

    def test_raw_can_be_set_true(self) -> None:
        """Verifies that raw can be set to True."""
        params = TableParameters(raw=True)
        assert params.raw is True


class TestHandleIssues:
    """Tests for the handle_issues decorator."""

    def test_returns_value_when_no_exception(self) -> None:
        """Verifies that the decorated function returns its value normally."""

        @handle_issues
        def good() -> int:
            return 42

        assert good() == 42

    def test_passes_args_and_kwargs(self) -> None:
        """Verifies that args and kwargs are forwarded to the wrapped function."""

        @handle_issues
        def add(a: int, b: int = 0) -> int:
            return a + b

        assert add(3, b=4) == 7

    def test_exits_on_exception_in_normal_mode(self) -> None:
        """Verifies that an exception causes SystemExit when not in debug mode."""
        settings.log_level = "INFO"

        @handle_issues
        def boom() -> None:
            raise ValueError("something went wrong")

        with pytest.raises(SystemExit) as exc_info:
            boom()
        assert exc_info.value.code == 1

    def test_reraises_in_debug_mode(self) -> None:
        """Verifies that exceptions propagate normally when in DEBUG mode."""
        settings.log_level = "DEBUG"

        @handle_issues
        def boom() -> None:
            raise ValueError("debug error")

        with pytest.raises(ValueError, match="debug error"):
            boom()

    def test_reraises_in_trace_mode(self) -> None:
        """Verifies that exceptions propagate normally when in TRACE mode."""
        settings.log_level = "TRACE"

        @handle_issues
        def boom() -> None:
            raise RuntimeError("trace error")

        with pytest.raises(RuntimeError, match="trace error"):
            boom()

    def test_preserves_function_name(self) -> None:
        """Verifies that the decorator preserves the original function name."""

        @handle_issues
        def my_function() -> None:
            pass

        assert my_function.__name__ == "my_function"

    def test_preserves_function_docstring(self) -> None:
        """Verifies that the decorator preserves the original function docstring."""

        @handle_issues
        def documented() -> None:
            """My docstring."""

        assert documented.__doc__ == "My docstring."

    def test_exit_prints_error_panel(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Verifies that the exception message is printed before exiting."""
        settings.log_level = "INFO"

        @handle_issues
        def boom() -> None:
            raise RuntimeError("panel message")

        with pytest.raises(SystemExit):
            boom()

        # Rich prints to stderr or stdout; capture via sys.stdout fallback
        captured = capsys.readouterr()
        assert "panel message" in captured.out or "panel message" in captured.err

    def test_schema_stale_warning_always_exits_with_error_panel(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A `SchemaStaleWarning` raised during the call always aborts the
        command through the same red-panel/exit(1) path as any other
        exception - unlike other warnings, it's unconditionally promoted to
        an error rather than displayed and allowed to continue, so a stale
        schema never lets a command silently proceed on drifted data.
        """
        settings.log_level = "INFO"

        @handle_issues
        def stale() -> str:
            warnings.warn(SchemaStaleWarning("schema is stale", "abc", "def"))
            return "done"

        with pytest.raises(SystemExit) as exc_info:
            stale()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "schema is stale" in captured.out or "schema is stale" in captured.err

    def test_schema_stale_warning_promoted_even_in_debug_mode(self) -> None:
        """Unlike every other exception (which propagates untouched in
        DEBUG/TRACE mode - see `test_reraises_in_debug_mode`), a stale
        schema must still be promoted to an error even then: the promoting
        filter is installed unconditionally, only the try/except that turns
        it into a styled panel is skipped in debugging mode.
        """
        settings.log_level = "DEBUG"

        @handle_issues
        def stale() -> None:
            warnings.warn(SchemaStaleWarning("schema is stale", "abc", "def"))

        with pytest.raises(SchemaStaleWarning):
            stale()

    def test_unrelated_warning_passes_through(
        self, recwarn: pytest.WarningsRecorder
    ) -> None:
        """A warning that isn't `SchemaStaleWarning` must reach the
        previously active `showwarning`, not be swallowed by this decorator.
        """
        settings.log_level = "INFO"

        @handle_issues
        def emits_unrelated_warning() -> str:
            warnings.warn("something else entirely", UserWarning)
            return "done"

        result = emits_unrelated_warning()

        assert result == "done"
        assert any("something else entirely" in str(w.message) for w in recwarn.list)

    def test_strict_schema_check_still_exits_via_exception_path(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """If a warning has been promoted to an error (as
        `AIMBAT_STRICT_SCHEMA_CHECK` does), it must still exit 1 with an
        error panel - promotion happens during filter matching, before this
        decorator's own warning-capturing logic would ever see it.
        """
        settings.log_level = "INFO"

        @handle_issues
        def stale() -> None:
            warnings.warn(SchemaStaleWarning("schema is stale", "abc", "def"))

        with warnings.catch_warnings():
            warnings.simplefilter("error", SchemaStaleWarning)
            with pytest.raises(SystemExit) as exc_info:
                stale()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "schema is stale" in captured.out or "schema is stale" in captured.err
