from sqlmodel import SQLModel
from enum import StrEnum
from typing import get_args, TypeAliasType
from aimbat.lib.models import AimbatEventParametersBase, AimbatSeismogramParametersBase
from aimbat.lib.typing import (
    EventParameter,
    SeismogramParameter,
    EventParameterBool,
    EventParameterFloat,
    EventParameterTimedelta,
    SeismogramParameterBool,
    SeismogramParameterDatetime,
)


def set_from_basemodel(obj: type[SQLModel]) -> set[str]:
    """Returns a set from the basemodel fields and remove "id" from it."""
    my_set: set[str] = set(obj.model_fields)
    my_set.discard("id")

    return my_set


def set_from_strenum(enum: type[StrEnum]) -> set[str]:

    return set([member.value for member in enum])


def set_from_typealiases(*aliases: TypeAliasType) -> set[str]:
    my_list = []
    for alias in aliases:
        my_list.extend([v for v in get_args(alias.__value__)])

    return set(my_list)


class TestLibTypes:
    """Ensure Default models and types are consistent."""

    def test_event_parameter_types(self) -> None:
        assert set_from_basemodel(AimbatEventParametersBase) == set_from_strenum(
            EventParameter
        )
        assert set_from_strenum(EventParameter) == set_from_typealiases(
            EventParameterBool,
            EventParameterFloat,
            EventParameterTimedelta,
        )

    def test_seismogram_parameter_types(self) -> None:
        assert set_from_basemodel(AimbatSeismogramParametersBase) == set_from_strenum(
            SeismogramParameter
        )
        assert set_from_strenum(SeismogramParameter) == set_from_typealiases(
            SeismogramParameterBool,
            SeismogramParameterDatetime,
        )
