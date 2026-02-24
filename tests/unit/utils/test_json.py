"""Unit tests for aimbat.utils._json."""

import io
from typing import Any, Callable
import pytest
from rich.console import Console
from aimbat.utils._json import json_to_table


def _capture_table(
    monkeypatch: pytest.MonkeyPatch,
    data: dict[str, Any] | list[dict[str, Any]],
    title: str | None = None,
    formatters: dict[str, Callable[[Any], str]] | None = None,
    skip_keys: list[str] | None = None,
    column_order: list[str] | None = None,
    column_kwargs: dict[str, dict[str, Any]] | None = None,
    common_column_kwargs: dict[str, Any] | None = None,
) -> str:
    """Call json_to_table and return the rendered output as a plain string.

    Args:
        monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
        data (dict[str, Any] | list[dict[str, Any]]): The data to render.
        title (str | None): Optional table title.
        formatters (dict[str, Callable[[Any], str]] | None): Optional value formatters.
        skip_keys (list[str] | None): Keys to exclude from the table.
        column_order (list[str] | None): Explicit order of columns.
        column_kwargs (dict[str, dict[str, Any]] | None): Column-specific arguments.
        common_column_kwargs (dict[str, Any] | None): Arguments applied to all columns.

    Returns:
        str: The captured table output.
    """
    buffer = io.StringIO()
    console = Console(file=buffer, highlight=False, no_color=True, width=200)
    monkeypatch.setattr("aimbat.utils._json.Console", lambda: console)
    json_to_table(
        data,
        title=title,
        formatters=formatters,
        skip_keys=skip_keys,
        column_order=column_order,
        column_kwargs=column_kwargs,
        common_column_kwargs=common_column_kwargs,
    )
    return buffer.getvalue()


class TestJsonToTableSingleDict:
    """Tests json_to_table with a single dictionary input."""

    def test_basic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies basic key-value rendering.

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
        """
        output = _capture_table(monkeypatch, {"name": "Alice", "age": 30})
        assert "name" in output
        assert "Alice" in output
        assert "age" in output
        assert "30" in output

    def test_title(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that the title is rendered.

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
        """
        output = _capture_table(monkeypatch, {"name": "Alice"}, title="Person")
        assert "Person" in output

    def test_default_column_headers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies default headers for dictionary input.

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
        """
        output = _capture_table(monkeypatch, {"x": "y"})
        assert "Key" in output
        assert "Value" in output

    def test_formatter_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that value formatters are applied.

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
        """
        output = _capture_table(
            monkeypatch,
            {"score": 0.123456},
            formatters={"score": lambda v: f"{v:.2f}"},
        )
        assert "0.12" in output
        assert "0.123456" not in output

    def test_skip_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that specified keys are skipped.

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
        """
        output = _capture_table(
            monkeypatch,
            {"name": "Alice", "secret": "hidden"},
            skip_keys=["secret"],
        )
        assert "name" in output
        assert "secret" not in output
        assert "hidden" not in output

    def test_column_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that column order is respected (row order for dicts).

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
        """
        output = _capture_table(
            monkeypatch,
            {"b": "2", "a": "1"},
            column_order=["a", "b"],
        )
        pos_a = output.index("a")
        pos_b = output.index("b")
        assert pos_a < pos_b

    def test_column_kwargs_header_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifies that column headers can be overridden via column_kwargs.

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
        """
        output = _capture_table(
            monkeypatch,
            {"name": "Alice"},
            column_kwargs={"Key": {"header": "Field"}, "Value": {"header": "Data"}},
        )
        assert "Field" in output
        assert "Data" in output
        assert "Key" not in output

    def test_common_column_kwargs_applied(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifies that common_column_kwargs are accepted.

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
        """
        # Ensures no exception is raised when common_column_kwargs is provided.
        output = _capture_table(
            monkeypatch,
            {"x": "1"},
            common_column_kwargs={"min_width": 5},
        )
        assert "x" in output

    def test_per_column_kwargs_override_common(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifies that column-specific kwargs override common kwargs.

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
        """
        output = _capture_table(
            monkeypatch,
            {"x": "1"},
            common_column_kwargs={"header": "Common"},
            column_kwargs={"Key": {"header": "Specific"}},
        )
        assert "Specific" in output


class TestJsonToTableListOfDicts:
    """Tests json_to_table with a list of dictionaries."""

    def test_basic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies basic table rendering for list of dicts.

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
        """
        output = _capture_table(
            monkeypatch,
            [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
        )
        assert "id" in output
        assert "name" in output
        assert "Alice" in output
        assert "Bob" in output
        assert "1" in output
        assert "2" in output

    def test_empty_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that an empty list produces valid output (empty table).

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
        """
        # Should not raise and should print an empty table.
        output = _capture_table(monkeypatch, [])
        assert output is not None

    def test_title(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that the title is rendered.

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
        """
        output = _capture_table(
            monkeypatch, [{"description": "test item"}], title="Results"
        )
        assert "Results" in output

    def test_formatter_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that value formatters are applied.

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
        """
        output = _capture_table(
            monkeypatch,
            [{"value": 3.14159}],
            formatters={"value": lambda v: f"{v:.1f}"},
        )
        assert "3.1" in output
        assert "3.14159" not in output

    def test_skip_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that specified keys are skipped.

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
        """
        output = _capture_table(
            monkeypatch,
            [{"name": "Alice", "secret": "x"}],
            skip_keys=["secret"],
        )
        assert "name" in output
        assert "secret" not in output

    def test_column_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that column order is respected.

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
        """
        output = _capture_table(
            monkeypatch,
            [{"b": "2", "a": "1"}],
            column_order=["a", "b"],
        )
        pos_a = output.index("a")
        pos_b = output.index("b")
        assert pos_a < pos_b

    def test_column_order_partial(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Keys not listed in column_order should be appended after.

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
        """
        output = _capture_table(
            monkeypatch,
            [{"c": "3", "b": "2", "a": "1"}],
            column_order=["a"],
        )
        pos_a = output.index("a")
        pos_b = output.index("b")
        pos_c = output.index("c")
        assert pos_a < pos_b
        assert pos_a < pos_c

    def test_column_kwargs_header_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifies that column headers can be overridden.

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
        """
        output = _capture_table(
            monkeypatch,
            [{"id": 1}],
            column_kwargs={"id": {"header": "Identifier"}},
        )
        assert "Identifier" in output
        assert "id" not in output

    def test_missing_key_in_row(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Rows missing a key should render 'None' for that cell.

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
        """
        output = _capture_table(
            monkeypatch,
            [{"a": 1, "b": 2}, {"a": 3}],
        )
        assert "None" in output

    def test_common_column_kwargs_applied(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifies that common_column_kwargs are applied to list columns.

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
        """
        output = _capture_table(
            monkeypatch,
            [{"x": "1"}],
            common_column_kwargs={"min_width": 5},
        )
        assert "x" in output
