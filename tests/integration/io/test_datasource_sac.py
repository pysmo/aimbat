"""Integration tests for AIMBAT models backed by SAC files.

Tests verify that SAC.station, SAC.event, and SAC.seismogram map correctly
to AimbatStation, AimbatEvent, and AimbatSeismogram, and that the data
property reads/writes through to the file on disk.

Note that in production we only ever read from the SAC file once to populate
the database, and then rely on the database for all subsequent access. However,
these tests verify that the SAC → Aimbat* mapping is correct and that the data
property correctly proxies through to the file on disk.
"""

from collections.abc import Generator
from datetime import timezone
from pathlib import Path

import numpy as np
import pytest
from pandas import Timestamp
from pysmo.classes import SAC
from sqlmodel import Session

from aimbat.io import DataType
from aimbat.models import (
    AimbatDataSource,
    AimbatEvent,
    AimbatEventParameters,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    AimbatStation,
)


@pytest.fixture
def session(patched_session: Session) -> Generator[Session, None, None]:
    yield patched_session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _persist_sac(session: Session, sac_file: Path) -> AimbatSeismogram:
    """Helper to build a full object graph from a SAC file and persist it.

    Args:
        session (Session): The database session.
        sac_file (Path): The path to the SAC file.

    Returns:
        AimbatSeismogram: The persisted seismogram object.
    """
    sac = SAC.from_file(sac_file)

    event = AimbatEvent.model_validate(
        sac.event,
        update={"parameters": AimbatEventParameters()},
    )
    session.add(event)
    session.flush()

    station = AimbatStation.model_validate(sac.station)
    session.add(station)
    session.flush()

    seismogram = AimbatSeismogram.model_validate(
        sac.seismogram,
        update={
            "t0": sac.timestamps.t0,
            "parameters": AimbatSeismogramParameters(),
            "event": event,
            "station": station,
        },
    )
    session.add(seismogram)
    session.flush()

    datasource = AimbatDataSource(
        sourcename=str(sac_file),
        datatype=DataType.SAC,
        seismogram=seismogram,
    )
    session.add(datasource)
    session.commit()
    return seismogram


# ===================================================================
# SAC → AimbatStation
# ===================================================================


class TestSacStation:
    """Verify SAC.station maps correctly to AimbatStation."""

    def test_station_fields_match_sac(
        self, sac_file_good: Path, session: Session
    ) -> None:
        """Verifies that AimbatStation fields match the source SAC file headers.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
            session (Session): Database session.
        """
        sac = SAC.from_file(sac_file_good)
        station = AimbatStation.model_validate(sac.station)
        session.add(station)
        session.commit()
        session.refresh(station)

        assert station.name == sac.station.name
        assert station.network == sac.station.network
        assert station.location == sac.station.location
        assert station.channel == sac.station.channel
        assert station.latitude == sac.station.latitude
        assert station.longitude == sac.station.longitude
        assert station.elevation == sac.station.elevation

    def test_station_round_trips_through_db(
        self, sac_file_good: Path, session: Session
    ) -> None:
        """Verifies that a Station persisted and re-fetched retains all values.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
            session (Session): Database session.
        """
        sac = SAC.from_file(sac_file_good)
        station = AimbatStation.model_validate(sac.station)
        session.add(station)
        session.commit()

        # Expire in-memory state and reload from DB.
        session.expire(station)
        assert station.name == sac.station.name
        assert station.latitude == pytest.approx(sac.station.latitude)
        assert station.longitude == pytest.approx(sac.station.longitude)


# ===================================================================
# SAC → AimbatEvent
# ===================================================================


class TestSacEvent:
    """Verify SAC.event maps correctly to AimbatEvent."""

    def test_event_fields_match_sac(
        self, sac_file_good: Path, session: Session
    ) -> None:
        """Verifies that AimbatEvent fields match the source SAC file headers.

        Note: SAPandasTimestamp truncates to microsecond precision.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
            session (Session): Database session.
        """
        sac = SAC.from_file(sac_file_good)
        event = AimbatEvent.model_validate(
            sac.event,
            update={"parameters": AimbatEventParameters()},
        )
        session.add(event)
        session.commit()
        session.refresh(event)

        assert event.time == sac.event.time.floor("us")
        assert event.latitude == sac.event.latitude
        assert event.longitude == sac.event.longitude
        assert event.depth == sac.event.depth

    def test_event_round_trips_through_db(
        self, sac_file_good: Path, session: Session
    ) -> None:
        """Verifies that an Event persisted and re-fetched retains all values.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
            session (Session): Database session.
        """
        sac = SAC.from_file(sac_file_good)
        event = AimbatEvent.model_validate(
            sac.event,
            update={"parameters": AimbatEventParameters()},
        )
        session.add(event)
        session.commit()

        session.expire(event)
        assert event.latitude == pytest.approx(sac.event.latitude)
        assert event.longitude == pytest.approx(sac.event.longitude)
        assert isinstance(event.time, Timestamp)


# ===================================================================
# SAC → AimbatSeismogram
# ===================================================================


class TestSacSeismogram:
    """AimbatSeismogram backed by a real SAC file on disk."""

    def test_metadata_matches_sac(self, sac_file_good: Path, session: Session) -> None:
        """Verify that seismogram model fields correspond to the SAC file.

        SAPandasTimestamp truncates to microsecond precision when storing
        in SQLite, so Timestamp comparisons use floor("us").

        Args:
            sac_file_good (Path): Path to a valid SAC file.
            session (Session): Database session.
        """
        sac = SAC.from_file(sac_file_good)
        seis = _persist_sac(session, sac_file_good)
        session.refresh(seis)

        assert seis.begin_time == sac.seismogram.begin_time.floor("us")
        assert seis.delta == sac.seismogram.delta
        assert seis.t0 == sac.timestamps.t0.floor("us")  # type: ignore

    def test_read_data_from_sac(self, sac_file_good: Path, session: Session) -> None:
        """Verifies that AimbatSeismogram.data returns the waveform from the SAC file.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
            session (Session): Database session.
        """
        sac = SAC.from_file(sac_file_good)
        seis = _persist_sac(session, sac_file_good)
        session.refresh(seis)

        np.testing.assert_array_equal(seis.data, sac.seismogram.data)

    def test_len_matches_data(self, sac_file_good: Path, session: Session) -> None:
        """Verifies that len(seismogram) equals the number of data samples.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
            session (Session): Database session.
        """
        sac = SAC.from_file(sac_file_good)
        seis = _persist_sac(session, sac_file_good)
        session.refresh(seis)

        assert len(seis.data) == len(sac.seismogram.data)

    def test_end_time_computed(self, sac_file_good: Path, session: Session) -> None:
        """Verifies that end_time is correctly computed from begin_time, delta, and npts.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
            session (Session): Database session.
        """
        seis = _persist_sac(session, sac_file_good)
        session.refresh(seis)

        expected = seis.begin_time + seis.delta * (len(seis.data) - 1)
        assert seis.end_time == expected

    def test_write_data_to_sac(self, sac_file_good: Path, session: Session) -> None:
        """Verifies that writing to AimbatSeismogram.data updates the SAC file on disk.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
            session (Session): Database session.
        """
        seis = _persist_sac(session, sac_file_good)
        session.refresh(seis)

        original_data = seis.data.copy()
        new_data = np.zeros_like(original_data)
        seis.data = new_data

        # Re-read from disk to confirm the file was updated.
        reread = SAC.from_file(sac_file_good).seismogram.data
        np.testing.assert_array_equal(reread, new_data)
        assert not np.array_equal(reread, original_data)

    def test_proxy_properties(self, sac_file_good: Path, session: Session) -> None:
        """Verifies that properties like flip, select, and t1 proxy through to parameters.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
            session (Session): Database session.
        """
        seis = _persist_sac(session, sac_file_good)
        session.refresh(seis)

        assert seis.select is True
        seis.select = False
        assert seis.parameters.select is False

        assert seis.flip is False
        seis.flip = True
        assert seis.parameters.flip is True

        assert seis.t1 is None
        new_t1 = Timestamp("2011-09-15T19:42:25", tz=timezone.utc)
        seis.t1 = new_t1
        assert seis.parameters.t1 == new_t1
