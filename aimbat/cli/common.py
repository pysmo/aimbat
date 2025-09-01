from aimbat.lib.common import ic
from aimbat.lib.db import AIMBAT_DB_URL
from aimbat.lib.typing import (
    ProjectDefault,
    ProjectDefaultBool,
    ProjectDefaultInt,
    ProjectDefaultStr,
    ProjectDefaultTimedelta,
    EventParameter,
    EventParameterBool,
    EventParameterTimedelta,
    SeismogramParameter,
    SeismogramParameterBool,
    SeismogramParameterDatetime,
)
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import overload, get_args
from cyclopts import Parameter


@Parameter(name="*")
@dataclass
class CommonParameters:
    db_url: str = AIMBAT_DB_URL
    "Database connection URL."

    debug: bool = False
    "Run in debugging mode."

    use_qt: bool = False
    "Use pyqtgraph instead of matplotlib for plots (where applicable)."

    def __post_init__(self) -> None:
        if self.debug:
            ic.enable()


def _should_be_type(name: ProjectDefault | EventParameter | SeismogramParameter) -> str:
    if name in get_args(ProjectDefaultBool) + get_args(EventParameterBool) + get_args(
        SeismogramParameterBool
    ):
        return "bool"
    if name in get_args(ProjectDefaultStr):
        return "str"
    if name in get_args(ProjectDefaultInt):
        return "int"
    if name in get_args(SeismogramParameterDatetime):
        return "datetime"
    if name in get_args(ProjectDefaultTimedelta) + get_args(EventParameterTimedelta):
        return "timedelta"
    raise ValueError(f"Unknown parameter {name=}.")


@dataclass
class _RegexEqual:
    string: str

    def __eq__(self, pattern: object | str) -> bool:
        import re

        if isinstance(pattern, str):
            match = re.search(pattern, self.string)
            return match is not None

        raise NotImplementedError


@overload
def convert_to_type(
    name: ProjectDefaultBool | EventParameterBool | SeismogramParameterBool,
    value: bool | int | float | str,
) -> bool: ...


@overload
def convert_to_type(name: ProjectDefaultInt, value: int | float | str) -> int: ...


@overload
def convert_to_type(
    name: ProjectDefaultTimedelta | EventParameterTimedelta,
    value: int | float | timedelta,
) -> timedelta: ...


@overload
def convert_to_type(
    name: SeismogramParameterDatetime, value: str | datetime
) -> datetime: ...


@overload
def convert_to_type(name: ProjectDefaultStr, value: int | float | str) -> str: ...


@overload
def convert_to_type(
    name: ProjectDefault | EventParameter,
    value: bool | int | float | str | timedelta,
) -> bool | int | timedelta | str: ...


@overload
def convert_to_type(
    name: SeismogramParameter,
    value: bool | int | float | str | datetime,
) -> bool | datetime: ...


def convert_to_type(
    name: ProjectDefault | EventParameter | SeismogramParameter,
    value: bool | int | float | str | datetime | timedelta,
) -> bool | int | str | timedelta | datetime | float:
    match [_should_be_type(name), _RegexEqual(str(value))]:
        case ["bool", r"^[T,t]rue$" | r"^[Y,y]es$" | r"^[Y,y]$" | r"^1$"]:
            return True
        case ["bool", r"^[F,f]alse$" | r"^[N,n]o$" | r"^[N,n]$" | r"^0$"]:
            return False
        case ["bool", _]:
            raise ValueError(f"Unable to determine bool from {value=}.")
        case ["int", r"^[+-]?\d+$"]:
            return int(str(value))
        case ["int", _]:
            raise ValueError(f"Unable to determine int from {value=}.")
        case ["float", r"^[+-]?(\d*\.)?\d+$"]:
            return float(str(value))
        case ["float", _]:
            raise ValueError(f"Unable to determine float from {value=}.")
        case ["datetime", r"\d\d\d\d[W,T,0-9,\-,:,\.,\s]+"]:
            return datetime.fromisoformat(str(value))
        case ["datetime", _]:
            raise ValueError(f"Unable to determine datetime from {value=}.")
        case ["timedelta", r"^[+-]?(\d*\.)?\d+"]:
            return timedelta(seconds=float(str(value)))
        case ["timedelta", _]:
            raise ValueError(f"Unable to determine timedelta from {value=}.")
        case ["str", _]:
            return str(value)
    raise NotImplementedError  # pragma: no cover
