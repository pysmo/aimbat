from __future__ import annotations
from typing import TYPE_CHECKING
from sqlmodel import select
from pysmo.tools.iccs import ICCSSeismogram
from aimbat.lib.seismogram import SeismogramParameter
from datetime import timedelta
import pytest
import random

if TYPE_CHECKING:
    from pathlib import Path
    from sqlmodel import Session
    from sqlalchemy.engine import Engine
    from typing import Any
    from collections.abc import Generator
    from aimbat.lib.models import AimbatSeismogram


class TestICCSBase:
    @pytest.fixture
    def session(
        self, test_db_with_active_event: tuple[Path, str, Engine, Session]
    ) -> Generator[Session, Any, Any]:
        yield test_db_with_active_event[3]

    @pytest.fixture
    def db_url(
        self, test_db_with_active_event: tuple[Path, str, Engine, Session]
    ) -> Generator[str, Any, Any]:
        yield test_db_with_active_event[1]

    @pytest.fixture
    def random_aimbat_seismogram(
        self, session: Session
    ) -> Generator[AimbatSeismogram, Any, Any]:
        from aimbat.lib.models import AimbatSeismogram

        yield random.choice(list(session.exec(select(AimbatSeismogram)).all()))


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
