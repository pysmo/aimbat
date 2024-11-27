from sqlmodel import SQLModel
from enum import StrEnum
from typing import TypeAlias, get_args
from aimbat.lib.models import (
    AimbatDefault,
    AimbatEventParametersBase,
    AimbatFile,
    AimbatSeismogramParametersBase,
)
from aimbat.lib.types import (
    EventParameter,
    ProjectDefault,
    AimbatFileAttribute,
    SeismogramParameter,
    TDefaultStr,
    TDefaultInt,
    TDefaultBool,
    TDefaultFloat,
    TEventParameterBool,
    TEventParameterTimedelta,
    TSeismogramParameterBool,
    TSeismogramParameterDatetime,
)


def set_from_basemodel(obj: SQLModel) -> set[str]:
    """Returns a set from the basemodel fields and remove "id" from it."""
    my_set = set(obj.model_fields)
    my_set.discard("id")
    return my_set


def set_from_strenum(enum: StrEnum) -> set[str]:
    return set([member.value for member in enum])  # type: ignore


def set_from_type_aliases(*aliases: TypeAlias) -> set[str]:
    my_list = []
    for alias in aliases:
        my_list.extend([v for v in get_args(alias)])

    return set(my_list)


class TestLibTypes:
    """Ensure Default models and types are consistent."""

    def test_default_types(self) -> None:
        assert set_from_basemodel(AimbatDefault) == set_from_strenum(  # type: ignore
            ProjectDefault  # type: ignore
        )
        assert set_from_strenum(ProjectDefault) == set_from_type_aliases(  # type: ignore
            TDefaultFloat,
            TDefaultBool,
            TDefaultInt,
            TDefaultStr,
        )

    def test_aimbatfile_types(self) -> None:
        assert set_from_basemodel(AimbatFile) == set_from_strenum(  # type: ignore
            AimbatFileAttribute  # type: ignore
        )

    def test_event_parameter_types(self) -> None:
        assert set_from_basemodel(AimbatEventParametersBase) == set_from_strenum(  # type: ignore
            EventParameter  # type: ignore
        )
        assert set_from_strenum(EventParameter) == set_from_type_aliases(  # type: ignore
            TEventParameterBool, TEventParameterTimedelta
        )

    def test_seismogram_parameter_types(self) -> None:
        assert set_from_basemodel(AimbatSeismogramParametersBase) == set_from_strenum(  # type: ignore
            SeismogramParameter  # type: ignore
        )
        assert set_from_strenum(SeismogramParameter) == set_from_type_aliases(  # type: ignore
            TSeismogramParameterBool, TSeismogramParameterDatetime
        )
