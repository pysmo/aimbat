from __future__ import annotations
from typing import TYPE_CHECKING
from sqlmodel import select
from pysmo.classes import SAC, SacSeismogram
from pysmo import Seismogram
from aimbat.lib.models import AimbatSeismogram
from aimbat.lib.typing import SeismogramFileType
from importlib import reload
import numpy as np
import pytest

if TYPE_CHECKING:
    from pathlib import Path
    from sqlmodel import Session
    from collections.abc import Generator
    from typing import Any


class TestSacBase:
    @pytest.fixture
    def session(
        self, test_db_with_project: tuple[Path, Session]
    ) -> Generator[Session, Any, Any]:
        yield test_db_with_project[1]

    @pytest.fixture
    def aimbat_seismogram_from_sac(
        self,
        session: Session,
        sac_file_good: Path,
    ) -> Generator[AimbatSeismogram, Any, Any]:
        import aimbat.lib.data as data

        reload(data)

        data.add_files_to_project([sac_file_good], SeismogramFileType.SAC)
        aimbat_file = session.exec(select(AimbatSeismogram)).one()
        yield aimbat_file

    @pytest.fixture
    def sac_seismogram(self, sac_file_good: Path) -> Generator[SacSeismogram, Any, Any]:
        sac_seismogram = SAC.from_file(sac_file_good).seismogram
        yield sac_seismogram


class TestSacRead(TestSacBase):
    def test_parameters_are_equal(
        self,
        sac_seismogram: SacSeismogram,
        aimbat_seismogram_from_sac: AimbatSeismogram,
    ) -> None:
        assert isinstance(aimbat_seismogram_from_sac, Seismogram)
        assert sac_seismogram.delta == aimbat_seismogram_from_sac.delta
        assert sac_seismogram.begin_time == aimbat_seismogram_from_sac.begin_time
        assert sac_seismogram.end_time == aimbat_seismogram_from_sac.end_time
        assert len(sac_seismogram) == len(aimbat_seismogram_from_sac)


class TestSacWrite(TestSacBase):
    def test_random_data(
        self,
        sac_file_good: Path,
        aimbat_seismogram_from_sac: AimbatSeismogram,
    ) -> None:
        new_data = np.random.rand(len(aimbat_seismogram_from_sac))
        aimbat_seismogram_from_sac.data = new_data
        assert np.allclose(new_data, aimbat_seismogram_from_sac.data)
        sac_seismogram = SAC.from_file(sac_file_good).seismogram
        assert np.allclose(sac_seismogram.data, aimbat_seismogram_from_sac.data)


class TestSacBadFile(TestSacBase):
    def test_t0_missing(self, sac_file_good: Path) -> None:
        from aimbat.lib.data import add_files_to_project, SeismogramFileType

        sac = SAC.from_file(sac_file_good)
        sac.t0 = None
        sac.write(sac_file_good)
        with pytest.raises(TypeError):
            add_files_to_project([sac_file_good], SeismogramFileType.SAC)
