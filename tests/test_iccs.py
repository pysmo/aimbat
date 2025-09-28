from aimbat.lib.models import AimbatSeismogram
from aimbat.lib.seismogram import SeismogramParameter
from pysmo.tools.iccs import ICCSSeismogram
from sqlmodel import Session, select
from datetime import timedelta
from typing import Any
from collections.abc import Generator
import pytest
import random


class TestICCSBase:
    @pytest.fixture
    def random_aimbat_seismogram(
        self, fixture_session_with_active_event: Session
    ) -> Generator[AimbatSeismogram, Any, Any]:
        from aimbat.lib.models import AimbatSeismogram

        yield random.choice(
            list(fixture_session_with_active_event.exec(select(AimbatSeismogram)).all())
        )


class TestAimbatSeismogramIsICCSSeismogram(TestICCSBase):
    def test_is_iccs_seismogram_instance(
        self, random_aimbat_seismogram: AimbatSeismogram
    ) -> None:
        assert isinstance(random_aimbat_seismogram, ICCSSeismogram)

    @pytest.mark.parametrize(
        "parameter, expected",
        [
            (SeismogramParameter.SELECT, True),
            (SeismogramParameter.FLIP, False),
            (SeismogramParameter.T1, None),
        ],
    )
    def test_read_iccs_parameters(
        self,
        random_aimbat_seismogram: AimbatSeismogram,
        parameter: SeismogramParameter,
        expected: Any,
    ) -> None:
        assert getattr(random_aimbat_seismogram, parameter) == expected

    @pytest.mark.parametrize(
        "parameter, new_value",
        [
            (SeismogramParameter.SELECT, False),
            (SeismogramParameter.FLIP, True),
            (SeismogramParameter.T1, timedelta(seconds=2)),
        ],
    )
    def test_write_iccs_parameters(
        self,
        random_aimbat_seismogram: AimbatSeismogram,
        parameter: SeismogramParameter,
        new_value: Any,
    ) -> None:
        setattr(random_aimbat_seismogram, parameter, new_value)
        assert getattr(random_aimbat_seismogram, parameter) == new_value
