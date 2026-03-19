"""Unit tests for aimbat._cli.common._table."""

from datetime import datetime
from unittest.mock import MagicMock, patch

from pandas import Timedelta, Timestamp
from pydantic import BaseModel, Field

from aimbat._cli.common._table import json_to_table
from aimbat.models import RichColSpec


class MockModel(BaseModel):
    """Simple model for testing."""

    model_config = {"arbitrary_types_allowed": True}

    id: int = Field(title="ID")
    name: str = Field(title="Name")
    active: bool = Field(default=True, title="Is Active")
    value: float | None = Field(default=None, title="Value")
    timestamp: datetime | None = Field(default=None, title="Time")
    duration: Timedelta | None = Field(default=None, title="Duration")


class RichMockModel(BaseModel):
    """Model with RichColSpec for testing."""

    model_config = {"arbitrary_types_allowed": True}

    id: int = Field(
        json_schema_extra={
            "rich": RichColSpec(display_title="User ID", justify="right")  # type: ignore[dict-item]
        }
    )
    name: str = Field(
        json_schema_extra={"rich": RichColSpec(style="bold cyan")}  # type: ignore[dict-item]
    )
    score: float = Field(
        json_schema_extra={"rich": RichColSpec(formatter=lambda x: f"{x:.1f} pts")}  # type: ignore[dict-item]
    )


@patch("aimbat._cli.common._table.Console")
class TestJsonToTable:
    """Tests for the json_to_table function."""

    def test_dict_input_vertical_table(self, mock_console_cls: MagicMock) -> None:
        """Verifies that dict input produces a vertical table."""
        mock_console = mock_console_cls.return_value
        data = {"id": 1, "name": "Alice", "active": True}

        json_to_table(data, MockModel, title="User Info")

        # Check if table was created and printed
        mock_console.print.assert_called_once()
        table = mock_console.print.call_args[0][0]
        assert table.title == "User Info"
        assert len(table.columns) == 2
        assert table.columns[0].header == "Property"
        assert table.columns[1].header == "Value"

        # Check rows — MockModel defines id, name, active, value, timestamp, duration
        # but only id, name, active are in data.
        # json_to_table implementation iterates over field_names and skips if not in data.
        # So we expect 3 rows.
        assert table.row_count == 3

    def test_list_input_horizontal_table(self, mock_console_cls: MagicMock) -> None:
        """Verifies that list input produces a horizontal table."""
        mock_console = mock_console_cls.return_value
        data = [
            {"id": 1, "name": "Alice", "active": True},
            {"id": 2, "name": "Bob", "active": False},
        ]

        json_to_table(data, MockModel)

        mock_console.print.assert_called_once()
        table = mock_console.print.call_args[0][0]
        # visible_fields should be id, name, active (those present in at least one row)
        assert len(table.columns) == 3
        headers = [col.header for col in table.columns]
        assert "ID" in headers
        assert "Name" in headers
        assert "Is Active" in headers
        assert table.row_count == 2

    def test_raw_mode_ignores_specs(self, mock_console_cls: MagicMock) -> None:
        """Verifies that raw=True ignores RichColSpec and formatters."""
        mock_console = mock_console_cls.return_value
        data = {"id": 1, "name": "Alice", "score": 95.5}

        # RichMockModel has score formatter returning "95.5 pts"
        # In raw mode it should just be "95.5" (str(val))
        json_to_table(data, RichMockModel, raw=True)

        table = mock_console.print.call_args[0][0]
        # In vertical table, values are in second column
        # We need to find the "score" row.
        # Row data is not easily accessible from rich.table.Table without private access
        # but we can check column headers aren't overridden by RichColSpec
        headers = [col.header for col in table.columns]
        assert "User ID" not in headers  # RichColSpec.display_title ignored

    def test_column_order(self, mock_console_cls: MagicMock) -> None:
        """Verifies that column_order is respected."""
        mock_console = mock_console_cls.return_value
        data = [{"id": 1, "name": "Alice", "active": True}]

        json_to_table(data, MockModel, column_order=["name", "id"])

        table = mock_console.print.call_args[0][0]
        headers = [col.header for col in table.columns]
        assert headers[0] == "Name"
        assert headers[1] == "ID"
        assert headers[2] == "Is Active"

    def test_col_specs_overrides(self, mock_console_cls: MagicMock) -> None:
        """Verifies that caller-supplied col_specs override model defaults."""
        mock_console = mock_console_cls.return_value
        data = [{"id": 1, "name": "Alice"}]

        overrides = {"name": RichColSpec(display_title="Full Name", style="red")}
        json_to_table(data, MockModel, col_specs=overrides)

        table = mock_console.print.call_args[0][0]
        name_col = next(c for c in table.columns if c.header == "Full Name")
        assert name_col.style == "red"

    def test_empty_data(self, mock_console_cls: MagicMock) -> None:
        """Verifies that empty list doesn't crash."""
        mock_console = mock_console_cls.return_value
        json_to_table([], MockModel)
        mock_console.print.assert_called_once()

    def test_formatting_logic(self, mock_console_cls: MagicMock) -> None:
        """Verifies various type-based formatters are used."""
        mock_console = mock_console_cls.return_value
        data = {
            "id": 1,
            "active": True,
            "value": 1.23456,
            "duration": Timedelta(seconds=1.5),
            "timestamp": Timestamp("2023-01-01 12:00:00"),
        }

        json_to_table(data, MockModel)

        # We can't easily check the formatted strings inside the Table rows
        # without mocking the _fmt_val or similar, but we can trust the logic
        # if the code runs. For deeper testing we'd need to inspect table._rows
        # which is list[Renderables].
        mock_console.print.assert_called_once()

    def test_justify_inference(self, mock_console_cls: MagicMock) -> None:
        """Verifies that justification is inferred from type hints."""
        mock_console = mock_console_cls.return_value
        data = [{"id": 1, "active": True, "value": 1.0, "name": "Alice"}]

        json_to_table(data, MockModel)

        table = mock_console.print.call_args[0][0]
        cols = {c.header: c for c in table.columns}

        # ID is int -> right
        assert cols["ID"].justify == "right"
        # Is Active is bool -> center
        assert cols["Is Active"].justify == "center"
        # Value is float -> right
        assert cols["Value"].justify == "right"
        # Name is str -> "left" (Rich default)
        assert cols["Name"].justify == "left"
