from sqlmodel import SQLModel
from enum import StrEnum
from typing import TypeAlias, get_args
from aimbat.lib.models import (
    AimbatDefaults,
    AimbatEventParametersBase,
    AimbatSeismogramParametersBase,
)
from aimbat.lib.typing import (
    EventParameter,
    SeismogramParameter,
    EventParameterBool,
    EventParameterFloat,
    EventParameterTimedelta,
    SeismogramParameterBool,
    SeismogramParameterDatetime,
    ProjectDefault,
    ProjectDefaultStr,
    ProjectDefaultBool,
    ProjectDefaultTimedelta,
)


def set_from_basemodel(obj: SQLModel) -> set[str]:
    """Returns a set from the basemodel fields and remove "id" from it."""
    my_set = set(obj.model_fields)
    my_set.discard("id")
    return my_set


def set_from_strenum(enum: StrEnum) -> set[str]:
    return set([member.value for member in enum])  # type: ignore


def set_from_typealiases(*aliases: list[TypeAlias]) -> set[str]:
    my_list = []
    for alias in aliases:
        my_list.extend([v for v in get_args(alias)])

    return set(my_list)


class TestLibTypes:
    """Ensure Default models and types are consistent."""

    def test_default_types(self) -> None:
        assert set_from_basemodel(AimbatDefaults) == set_from_strenum(  # type: ignore
            ProjectDefault  # type: ignore
        )
        assert set_from_strenum(ProjectDefault) == set_from_typealiases(  # type: ignore
            ProjectDefaultTimedelta,  # type: ignore
            ProjectDefaultBool,  # type: ignore
            ProjectDefaultStr,  # type: ignore
        )

    def test_event_parameter_types(self) -> None:
        assert set_from_basemodel(AimbatEventParametersBase) == set_from_strenum(  # type: ignore
            EventParameter  # type: ignore
        )
        assert set_from_strenum(EventParameter) == set_from_typealiases(  # type: ignore
            EventParameterBool,  # type: ignore
            EventParameterFloat,  # type: ignore
            EventParameterTimedelta,  # type: ignore
        )

    def test_seismogram_parameter_types(self) -> None:
        assert set_from_basemodel(AimbatSeismogramParametersBase) == set_from_strenum(  # type: ignore
            SeismogramParameter  # type: ignore
        )
        assert set_from_strenum(SeismogramParameter) == set_from_typealiases(  # type: ignore
            SeismogramParameterBool,  # type: ignore
            SeismogramParameterDatetime,  # type: ignore
        )
