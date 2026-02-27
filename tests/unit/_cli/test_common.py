"""Unit tests for aimbat._cli.common."""

import pytest
from aimbat._cli.common import (
    GlobalParameters,
    PlotParameters,
    IccsPlotParameters,
    TableParameters,
    CliHints,
    HINTS,
    simple_exception,
)
from aimbat import settings


class TestGlobalParameters:
    """Tests for the GlobalParameters dataclass."""

    def test_default_debug_is_false(self) -> None:
        """Verifies that debug defaults to False."""
        params = GlobalParameters()
        assert params.debug is False

    def test_debug_true_sets_log_level(self) -> None:
        """Verifies that setting debug=True changes the log level to DEBUG."""
        GlobalParameters(debug=True)
        assert settings.log_level == "DEBUG"

    def test_debug_false_does_not_change_log_level(self) -> None:
        """Verifies that debug=False does not alter the log level."""
        original = settings.log_level
        GlobalParameters(debug=False)
        assert settings.log_level == original


class TestPlotParameters:
    """Tests for the PlotParameters dataclass."""

    def test_default_use_qt_is_false(self) -> None:
        """Verifies that use_qt defaults to False."""
        params = PlotParameters()
        assert params.use_qt is False

    def test_use_qt_can_be_set_true(self) -> None:
        """Verifies that use_qt can be set to True."""
        params = PlotParameters(use_qt=True)
        assert params.use_qt is True


class TestIccsPlotParameters:
    """Tests for the IccsPlotParameters dataclass."""

    def test_default_context_is_true(self) -> None:
        """Verifies that context defaults to True."""
        params = IccsPlotParameters()
        assert params.context is True

    def test_default_all_is_false(self) -> None:
        """Verifies that all defaults to False."""
        params = IccsPlotParameters()
        assert params.all is False

    def test_context_can_be_set_false(self) -> None:
        """Verifies that context can be set to False."""
        params = IccsPlotParameters(context=False)
        assert params.context is False

    def test_all_can_be_set_true(self) -> None:
        """Verifies that all can be set to True."""
        params = IccsPlotParameters(all=True)
        assert params.all is True


class TestTableParameters:
    """Tests for the TableParameters dataclass."""

    def test_default_short_is_true(self) -> None:
        """Verifies that short defaults to True."""
        params = TableParameters()
        assert params.short is True

    def test_short_can_be_set_false(self) -> None:
        """Verifies that short can be set to False."""
        params = TableParameters(short=False)
        assert params.short is False


class TestCliHints:
    """Tests for the CliHints frozen dataclass."""

    def test_activate_event_hint_content(self) -> None:
        """Verifies that ACTIVATE_EVENT hint references the activate command."""
        assert "activate" in CliHints.ACTIVATE_EVENT
        assert "aimbat event activate" in CliHints.ACTIVATE_EVENT

    def test_list_events_hint_content(self) -> None:
        """Verifies that LIST_EVENTS hint references the list command."""
        assert "list" in CliHints.LIST_EVENTS
        assert "aimbat event list" in CliHints.LIST_EVENTS

    def test_hints_instance_is_frozen(self) -> None:
        """Verifies that the CliHints dataclass is frozen (immutable)."""
        with pytest.raises((AttributeError, TypeError)):
            HINTS.ACTIVATE_EVENT = "new value"

    def test_hints_singleton_values(self) -> None:
        """Verifies that the HINTS singleton has the expected attribute values."""
        assert HINTS.ACTIVATE_EVENT == CliHints.ACTIVATE_EVENT
        assert HINTS.LIST_EVENTS == CliHints.LIST_EVENTS


class TestSimpleException:
    """Tests for the simple_exception decorator."""

    def test_returns_value_when_no_exception(self) -> None:
        """Verifies that the decorated function returns its value normally."""

        @simple_exception
        def good() -> int:
            return 42

        assert good() == 42

    def test_passes_args_and_kwargs(self) -> None:
        """Verifies that args and kwargs are forwarded to the wrapped function."""

        @simple_exception
        def add(a: int, b: int = 0) -> int:
            return a + b

        assert add(3, b=4) == 7

    def test_exits_on_exception_in_normal_mode(self) -> None:
        """Verifies that an exception causes SystemExit when not in debug mode."""
        settings.log_level = "INFO"

        @simple_exception
        def boom() -> None:
            raise ValueError("something went wrong")

        with pytest.raises(SystemExit) as exc_info:
            boom()
        assert exc_info.value.code == 1

    def test_reraises_in_debug_mode(self) -> None:
        """Verifies that exceptions propagate normally when in DEBUG mode."""
        settings.log_level = "DEBUG"

        @simple_exception
        def boom() -> None:
            raise ValueError("debug error")

        with pytest.raises(ValueError, match="debug error"):
            boom()

    def test_reraises_in_trace_mode(self) -> None:
        """Verifies that exceptions propagate normally when in TRACE mode."""
        settings.log_level = "TRACE"

        @simple_exception
        def boom() -> None:
            raise RuntimeError("trace error")

        with pytest.raises(RuntimeError, match="trace error"):
            boom()

    def test_preserves_function_name(self) -> None:
        """Verifies that the decorator preserves the original function name."""

        @simple_exception
        def my_function() -> None:
            pass

        assert my_function.__name__ == "my_function"

    def test_preserves_function_docstring(self) -> None:
        """Verifies that the decorator preserves the original function docstring."""

        @simple_exception
        def documented() -> None:
            """My docstring."""

        assert documented.__doc__ == "My docstring."

    def test_exit_prints_error_panel(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Verifies that the exception message is printed before exiting."""
        settings.log_level = "INFO"

        @simple_exception
        def boom() -> None:
            raise RuntimeError("panel message")

        with pytest.raises(SystemExit):
            boom()

        # Rich prints to stderr or stdout; capture via sys.stdout fallback
        captured = capsys.readouterr()
        assert "panel message" in captured.out or "panel message" in captured.err
