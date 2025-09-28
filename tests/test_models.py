from aimbat.lib.models import AimbatSeismogram
from typing import Any
from collections.abc import Generator
from sqlmodel import Session
import numpy as np
import pytest
import random


class TestModelsBase:
    @pytest.fixture
    def session(
        self, fixture_session_with_active_event: Session
    ) -> Generator[Session, Any, Any]:
        yield fixture_session_with_active_event


class TestAimbatSeismogram(TestModelsBase):
    @pytest.fixture
    def random_seismogram(
        self, session: Session
    ) -> Generator[AimbatSeismogram, Any, Any]:
        from aimbat.lib.event import get_active_event

        yield random.choice(list(get_active_event(session).seismograms))

    def test_lib_get_seismogram_data_with_no_datasource(
        self, random_seismogram: AimbatSeismogram
    ) -> None:
        _ = random_seismogram.data
        random_seismogram.datasource = None  # type: ignore

        with pytest.raises(ValueError):
            _ = random_seismogram.data

    def test_lib_set_seismogram_data_with_no_datasource(
        self, random_seismogram: AimbatSeismogram
    ) -> None:
        _ = random_seismogram.data
        random_seismogram.datasource = None  # type: ignore

        with pytest.raises(ValueError):
            random_seismogram.data = np.array([1, 2, 3])

    def test_lib_get_seismogram_begin_time_with_zero_length_data(
        self,
        random_seismogram: AimbatSeismogram,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(random_seismogram, "data", np.array([], dtype=np.float32))

        assert random_seismogram.begin_time == random_seismogram.end_time
