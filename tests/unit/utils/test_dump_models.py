"""Unit tests for the shared dump helpers in aimbat.utils._pydantic."""

import pytest
from pandas import Timestamp
from pydantic import BaseModel, Field

from aimbat.types import PydanticTimestamp
from aimbat.utils import check_field_name_flags, dump_models, get_title_map


class _Record(BaseModel):
    """Stand-in for the models the `dump_*_table` functions serialise."""

    name: str = Field(title="Station Name", serialization_alias="stationName")
    time: PydanticTimestamp = Field(
        title="Origin Time", serialization_alias="originTime"
    )
    secret: str = "hidden"


def _records() -> list[_Record]:
    return [
        _Record(name="ABC", time=Timestamp("2011-03-11T05:46:24Z")),
        _Record(name="DEF", time=Timestamp("2011-03-11T05:47:24Z")),
    ]


class TestCheckFieldNameFlags:
    """Tests for check_field_name_flags."""

    def test_alias_and_title_together_raise(self) -> None:
        """Verifies the two field-naming schemes are mutually exclusive."""
        with pytest.raises(ValueError, match="mutually exclusive"):
            check_field_name_flags(by_alias=True, by_title=True)

    def test_title_without_read_model_raises(self) -> None:
        """Verifies titles are refused when the ORM model is being dumped."""
        with pytest.raises(ValueError, match="only supported when"):
            check_field_name_flags(False, True, from_read_model=False)

    def test_title_with_read_model_is_allowed(self) -> None:
        """Verifies the read-model path accepts titles."""
        check_field_name_flags(False, True, from_read_model=True)

    def test_no_read_model_choice_allows_title(self) -> None:
        """Verifies the functions without the choice are not caught by it."""
        check_field_name_flags(False, True)


class TestDumpModels:
    """Tests for dump_models."""

    def test_one_dict_per_record_in_json_mode(self) -> None:
        """Verifies records are serialised to JSON-compatible dicts."""
        data = dump_models(_records(), _Record)

        assert len(data) == 2
        assert data[0]["name"] == "ABC"
        assert isinstance(data[0]["time"], str)

    def test_by_alias_uses_serialisation_aliases(self) -> None:
        """Verifies the alias naming scheme reaches every record."""
        data = dump_models(_records(), _Record, by_alias=True)

        assert all("stationName" in row and "name" not in row for row in data)

    def test_by_title_uses_the_title_map(self) -> None:
        """Verifies the title naming scheme matches `get_title_map`."""
        data = dump_models(_records(), _Record, by_title=True)

        title_map = get_title_map(_Record)
        assert all(set(row) == set(title_map.values()) for row in data)
        assert data[0]["Station Name"] == "ABC"

    def test_exclude_applies_to_every_record(self) -> None:
        """Verifies excluded fields are dropped from all rows, not just the first."""
        data = dump_models(_records(), _Record, exclude={"secret"})

        assert all("secret" not in row for row in data)

    def test_empty_exclude_drops_nothing(self) -> None:
        """Verifies an empty exclusion set is not read as "exclude everything"."""
        data = dump_models(_records(), _Record, exclude=set())

        assert all("secret" in row for row in data)

    def test_alias_and_title_together_raise(self) -> None:
        """Verifies the flag check applies when called directly, too."""
        with pytest.raises(ValueError, match="mutually exclusive"):
            dump_models(_records(), _Record, by_alias=True, by_title=True)
