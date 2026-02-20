from pydantic import BaseModel, model_validator
from typing import Self


class EventParametersValidatorMixin(BaseModel):
    bandpass_fmin: float
    bandpass_fmax: float

    @model_validator(mode="after")
    def check_freq_range(self) -> Self:
        if self.bandpass_fmax <= self.bandpass_fmin:
            raise ValueError("bandpass_fmax must be > bandpass_fmin")
        return self
