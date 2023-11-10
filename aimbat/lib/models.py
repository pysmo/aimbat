from sqlmodel import SQLModel, Field

TAimbatDefaults = float | int | bool | str


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

    def __init__(self, **kwargs: TAimbatDefaults) -> None:
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


class Station(SQLModel, table=True):
    """Class to store station information."""

    id: int | None = Field(primary_key=True)
    name: str = Field(unique=True)
    latitude: float
    longitude: float
    network: str | None = None
    elevation: float | None = None
