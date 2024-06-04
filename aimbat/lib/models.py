from sqlmodel import Relationship, SQLModel, Field
from datetime import datetime, timedelta
from aimbat.lib.common import AimbatFileType
import aimbat.lib.io as io
import numpy as np

TAimbatDefault = float | int | bool | str


class AimbatDefault(SQLModel, table=True):
    """Class to store AIMBAT defaults."""

    id: int | None = Field(primary_key=True)
    name: str = Field(unique=True)
    is_of_type: str
    description: str
    initial_value: str
    fvalue: float | None = None
    ivalue: int | None = None
    bvalue: bool | None = None
    svalue: str | None = None

    def __init__(self, **kwargs: TAimbatDefault) -> None:
        super().__init__(**kwargs)
        if self.is_of_type == "float":
            self.fvalue = float(self.initial_value)
        elif self.is_of_type == "int":
            self.ivalue = int(self.initial_value)
        elif self.is_of_type == "bool":
            self.bvalue = bool(self.initial_value)
        elif self.is_of_type == "str":
            self.svalue = self.initial_value
        # we really shouldn't ever end up here...
        else:
            raise RuntimeError(
                "Unable to assign {self.name} with value: {self.initial_value}."
            )  # pragma: no cover


class AimbatFileBase(SQLModel):
    """Class to store data file information."""

    filename: str = Field(unique=True)


class AimbatFileCreate(AimbatFileBase):
    """Class to store data file information."""

    filetype: AimbatFileType = "sac"


class AimbatFile(AimbatFileBase, table=True):
    """Class to store data file information."""

    id: int | None = Field(default=None, primary_key=True)
    filetype: str
    seismogram: "AimbatSeismogram" = Relationship(back_populates="file")


class AimbatStation(SQLModel, table=True):
    """Class to store station information."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(allow_mutation=False)
    latitude: float
    longitude: float
    network: str | None = Field(default=None, allow_mutation=False)
    elevation: float | None = None
    seismograms: list["AimbatSeismogram"] = Relationship(back_populates="station")


class AimbatEvent(SQLModel, table=True):
    """Class to store event information."""

    id: int | None = Field(default=None, primary_key=True)
    time: datetime = Field(unique=True)
    latitude: float
    longitude: float
    depth: float | None = None
    seismograms: list["AimbatSeismogram"] = Relationship(back_populates="event")
    # snapshots: list["AimbatSnapshot"] = Relationship(back_populates="event")


class AimbatSeismogram(SQLModel, table=True):
    """Class to store seismogram data"""

    id: int | None = Field(default=None, primary_key=True)

    begin_time: datetime
    delta: float
    t0: datetime
    cached_length: int | None = None

    file_id: int | None = Field(default=None, foreign_key="aimbatfile.id")
    file: AimbatFile = Relationship(back_populates="seismogram")
    station_id: int | None = Field(foreign_key="aimbatstation.id")
    station: AimbatStation = Relationship(back_populates="seismograms")
    event_id: int | None = Field(foreign_key="aimbatevent.id")
    event: AimbatEvent = Relationship(back_populates="seismograms")
    parameter_id: int | None = Field(default=None, foreign_key="aimbatparameterset.id")
    parameter: "AimbatParameterSet" = Relationship(back_populates="seismogram")

    def __len__(self) -> int:
        if self.cached_length is None:
            self.cached_length = np.size(self.data)
        return self.cached_length

    @property
    def end_time(self) -> datetime:
        if len(self) == 0:
            return self.begin_time
        return self.begin_time + timedelta(seconds=self.delta * (len(self) - 1))

    @property
    def data(self) -> np.ndarray:
        if self.file_id is None:
            raise RuntimeError("I don't know which file to read data from")
        return io.read_seismogram_data_from_file(self.file.filename, self.file.filetype)

    @data.setter
    def data(self, value: np.ndarray) -> None:
        if self.file_id is None:
            raise RuntimeError("I don't know which file to write data to")
        io.write_seismogram_data_to_file(self.file.filename, self.file.filetype, value)
        self.cached_length = np.size(value)


class AimbatEventParameter(SQLModel, table=True):
    """Processing parameter common to all seismograms of a particular event."""

    id: int | None = Field(default=None, primary_key=True)
    event_id: int | None = Field(foreign_key="aimbatevent.id")
    parameter_sets: list["AimbatParameterSet"] = Relationship(
        back_populates="event_parameter"
    )
    window_pre: timedelta
    window_post: timedelta


class AimbatSeismogramParameter(SQLModel, table=True):
    """Class to store ICCS processing parameters of a single seismogram."""

    id: int | None = Field(default=None, primary_key=True)
    select: bool = True
    t1: datetime | None = None
    t2: datetime | None = None
    parameter_set: "AimbatParameterSet" = Relationship(
        back_populates="seismogram_parameter"
    )


class AimbatParameterSet(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    seismogram: AimbatSeismogram = Relationship(back_populates="parameter")
    event_parameter_id: int | None = Field(
        default=None, foreign_key="aimbateventparameter.id"
    )
    event_parameter: AimbatEventParameter = Relationship(
        back_populates="parameter_sets"
    )
    seismogram_parameter_id: int | None = Field(
        default=None, foreign_key="aimbatseismogramparameter.id"
    )
    seismogram_parameter: AimbatSeismogramParameter = Relationship(
        back_populates="parameter_set"
    )

    @property
    def select(self) -> bool:
        return self.seismogram_parameter.select

    @select.setter
    def select(self, value: bool) -> None:
        self.seismogram_parameter.select = value

    @property
    def t1(self) -> datetime | None:
        return self.seismogram_parameter.t1

    @t1.setter
    def t1(self, value: datetime) -> None:
        self.seismogram_parameter.t1 = value

    @property
    def t2(self) -> datetime | None:
        return self.seismogram_parameter.t2

    @t2.setter
    def t2(self, value: datetime) -> None:
        self.seismogram_parameter.t2 = value

    @property
    def window_pre(self) -> timedelta | None:
        return self.event_parameter.window_pre

    @window_pre.setter
    def window_pre(self, value: timedelta) -> None:
        self.event_parameter.window_pre = value

    @property
    def window_post(self) -> timedelta | None:
        return self.event_parameter.window_post

    @window_post.setter
    def window_post(self, value: timedelta) -> None:
        self.event_parameter.window_post = value


# class AimbatSnapshot(SQLModel, table=True):
#     """Class to store parameter snapshots."""
#
#     id: int | None = Field(default=None, primary_key=True)
#     parameter_id: int = Field(foreign_key="aimbatcommonparameter.id")
#     date: datetime = Field(
#         default_factory=datetime.now, unique=True, allow_mutation=False
#     )
#     comment: str | None = None
#     event: AimbatEvent = Relationship(back_populates="snapshots")
