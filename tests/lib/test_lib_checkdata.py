from aimbat.lib.common import AimbatDataError
from pysmo import SAC
import pytest
import numpy as np


class TestLibCheckData:
    def test_check_station_no_name(self, sac_instance_good: SAC) -> None:
        from aimbat.lib.checkdata import checkdata_station

        assert sac_instance_good.station.name
        checkdata_station(sac_instance_good.station)
        sac_instance_good.kstnm = None
        with pytest.raises(AimbatDataError):
            checkdata_station(sac_instance_good.station)

    def test_check_station_no_latitude(self, sac_instance_good: SAC) -> None:
        from aimbat.lib.checkdata import checkdata_station

        assert sac_instance_good.station.latitude
        checkdata_station(sac_instance_good.station)
        sac_instance_good.stla = None
        with pytest.raises(AimbatDataError):
            checkdata_station(sac_instance_good.station)

    def test_check_station_no_longitude(self, sac_instance_good: SAC) -> None:
        from aimbat.lib.checkdata import checkdata_station

        assert sac_instance_good.station.longitude
        checkdata_station(sac_instance_good.station)
        sac_instance_good.stlo = None
        with pytest.raises(AimbatDataError):
            checkdata_station(sac_instance_good.station)

    def test_check_event_no_latitude(self, sac_instance_good: SAC) -> None:
        from aimbat.lib.checkdata import checkdata_event

        assert sac_instance_good.event.latitude
        checkdata_event(sac_instance_good.event)
        sac_instance_good.evla = None
        with pytest.raises(AimbatDataError):
            checkdata_event(sac_instance_good.event)

    def test_check_event_no_longitude(self, sac_instance_good: SAC) -> None:
        from aimbat.lib.checkdata import checkdata_event

        assert sac_instance_good.event.longitude
        checkdata_event(sac_instance_good.event)
        sac_instance_good.evlo = None
        with pytest.raises(AimbatDataError):
            checkdata_event(sac_instance_good.event)

    def test_check_event_no_time(self, sac_instance_good: SAC) -> None:
        from aimbat.lib.checkdata import checkdata_event

        assert sac_instance_good.event.time
        checkdata_event(sac_instance_good.event)
        sac_instance_good.o = None
        with pytest.raises(AimbatDataError):
            checkdata_event(sac_instance_good.event)

    def test_check_seismogram_no_begin_time(self, sac_instance_good: SAC) -> None:
        from aimbat.lib.checkdata import checkdata_seismogram

        assert len(sac_instance_good.seismogram.data) > 0
        checkdata_seismogram(sac_instance_good.seismogram)
        sac_instance_good.seismogram.data = np.array([])
        with pytest.raises(AimbatDataError):
            checkdata_seismogram(sac_instance_good.seismogram)
