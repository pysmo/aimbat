from typing import Any, Optional
from sqlmodel import SQLModel, Field


class AimbatDefault(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True)
    name: str = Field(unique=True)
    is_of_type: str
    description: str
    initial_value: str
    fvalue: Optional[float] = Field(default=None)
    ivalue: Optional[int] = Field(default=None)
    bvalue: Optional[bool] = Field(default=None)
    svalue: Optional[str] = Field(default=None)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if self.is_of_type == "float":
            self.fvalue = float(self.initial_value)
        elif self.is_of_type == "int":
            self.ivalue = int(self.initial_value)
        elif self.is_of_type == "bool":
            self.bvalue = bool(self.initial_value)
        elif self.is_of_type == "str":
            self.svalue = self.initial_value
        # we really shouldn't ever end up here..
        else:
            raise RuntimeError(
                "Unable to assign {self.name} with value: {self.initial_value}."
            )  # pragma: no cover
