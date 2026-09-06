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
from pathlib import Path

import numpy as np
import numpy.typing as npt
import pytest
from pandas import Timestamp
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from pysmo.classes import SAC

from aimbat.core import create_project
from aimbat.io import DataType
from aimbat.io import _base as io_base
from aimbat.models import (
    AimbatDataSource,
    AimbatEvent,
    AimbatEventParameters,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    AimbatStation,
)


@pytest.fixture
def session(patched_session: Session) -> Generator[Session]:
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

    def test_write_data_to_sac_deferred_until_commit(
        self, sac_file_good: Path, session: Session
    ) -> None:
        """Assigning `data` stages the write; the SAC file changes only on commit.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
            session (Session): Database session.
        """
        seis = _persist_sac(session, sac_file_good)
        session.refresh(seis)

        original_data = seis.data.copy()
        new_data = np.zeros_like(original_data)
        seis.data = new_data

        # File on disk is untouched, but this session sees the staged value.
        on_disk = SAC.from_file(sac_file_good).seismogram.data
        np.testing.assert_array_equal(on_disk, original_data)
        np.testing.assert_array_equal(seis.data, new_data)

        session.commit()

        reread = SAC.from_file(sac_file_good).seismogram.data
        np.testing.assert_array_equal(reread, new_data)
        assert not np.array_equal(reread, original_data)

    def test_write_data_to_sac_discarded_on_rollback(
        self, sac_file_good: Path, session: Session
    ) -> None:
        """A staged `data` write is dropped when the session rolls back.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
            session (Session): Database session.
        """
        seis = _persist_sac(session, sac_file_good)
        session.refresh(seis)
        original_data = seis.data.copy()

        seis.data = np.zeros_like(original_data)
        session.rollback()

        np.testing.assert_array_equal(
            SAC.from_file(sac_file_good).seismogram.data, original_data
        )
        # The next read (staging gone) returns the on-disk value.
        np.testing.assert_array_equal(seis.data, original_data)

    def test_staged_write_not_flushed_by_another_session(
        self, sac_file_good: Path, engine_from_file: Engine
    ) -> None:
        """A second session committing does not flush the first session's stage.

        This exercises `_pending` isolation between sessions, not concurrency
        of the underlying SQLite store. A file-backed engine is used so the
        two sessions get independent connections.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
            engine_from_file (Engine): File-backed test database engine.
        """
        create_project(engine_from_file)
        # WAL so session B can commit a write while session A holds a read txn.
        with engine_from_file.connect() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL")

        with Session(engine_from_file) as session_a:
            seis = _persist_sac(session_a, sac_file_good)
            session_a.commit()
            seismogram_id = seis.id
            original_data = seis.data.copy()

            seis.data = np.zeros_like(original_data)

            with Session(engine_from_file) as session_b:
                other = session_b.get(AimbatSeismogram, seismogram_id)
                assert other is not None
                other.t0 = other.begin_time
                session_b.commit()

            # Session B's commit did not flush session A's staged write.
            np.testing.assert_array_equal(
                SAC.from_file(sac_file_good).seismogram.data, original_data
            )

            session_a.commit()
            np.testing.assert_array_equal(
                SAC.from_file(sac_file_good).seismogram.data,
                np.zeros_like(original_data),
            )

    def test_end_time_reflects_staged_sample_count(
        self, sac_file_good: Path, session: Session
    ) -> None:
        """`end_time` uses the staged waveform length before commit.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
            session (Session): Database session.
        """
        seis = _persist_sac(session, sac_file_good)
        session.refresh(seis)

        shorter = seis.data[:10].copy()
        seis.data = shorter
        assert seis.end_time == seis.begin_time + seis.delta * 9

    def test_clear_cache_keeps_staged_write(
        self, sac_file_good: Path, session: Session
    ) -> None:
        """`clear_seismogram_data_cache` does not drop a staged `data` write.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
            session (Session): Database session.
        """
        from aimbat.io import clear_seismogram_data_cache

        seis = _persist_sac(session, sac_file_good)
        session.refresh(seis)
        original_data = seis.data.copy()

        seis.data = np.zeros_like(original_data)
        clear_seismogram_data_cache()
        session.commit()

        np.testing.assert_array_equal(
            SAC.from_file(sac_file_good).seismogram.data,
            np.zeros_like(original_data),
        )

    def test_write_data_on_detached_instance_is_eager(
        self, sac_file_good: Path, session: Session
    ) -> None:
        """With no owning session there is no transaction, so the write is eager.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
            session (Session): Database session.
        """
        seis = _persist_sac(session, sac_file_good)
        session.commit()
        original_data = seis.data.copy()
        session.expunge(seis)
        assert seis.datasource is not None  # loaded before expunge

        seis.data = np.zeros_like(original_data)

        # Written straight away, no commit needed.
        np.testing.assert_array_equal(
            SAC.from_file(sac_file_good).seismogram.data,
            np.zeros_like(original_data),
        )

    def test_staged_write_survives_savepoint_rollback(
        self, sac_file_good: Path, session: Session
    ) -> None:
        """A `begin_nested()` rollback keeps a write staged on the outer transaction.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
            session (Session): Database session.
        """
        seis = _persist_sac(session, sac_file_good)
        session.commit()
        original_data = seis.data.copy()

        seis.data = np.zeros_like(original_data)

        with pytest.raises(RuntimeError, match="abort savepoint"):
            with session.begin_nested():
                seis.t0 = seis.begin_time
                raise RuntimeError("abort savepoint")

        # Savepoint rolled back; the staged write is still pending.
        np.testing.assert_array_equal(
            SAC.from_file(sac_file_good).seismogram.data, original_data
        )

        session.commit()
        np.testing.assert_array_equal(
            SAC.from_file(sac_file_good).seismogram.data,
            np.zeros_like(original_data),
        )

    def test_commit_failure_leaves_the_staged_write_retryable(
        self,
        sac_file_good: Path,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A failed flush aborts the commit; the staged write survives for a retry.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
            session (Session): Database session.
            monkeypatch (pytest.MonkeyPatch): Fixture used to make the SAC
                writer fail once.
        """
        seis = _persist_sac(session, sac_file_good)
        session.commit()
        original_data = seis.data.copy()
        seis.data = np.zeros_like(original_data)

        real_writer = io_base._seismogram_data_writers[DataType.SAC]
        calls = {"n": 0}

        def flaky_writer(src: str | Path, data: npt.NDArray[np.floating]) -> None:
            calls["n"] += 1
            if calls["n"] == 1:
                raise OSError("disk full")
            real_writer(src, data)

        monkeypatch.setitem(
            io_base._seismogram_data_writers, DataType.SAC, flaky_writer
        )

        with pytest.raises(OSError, match="disk full"):
            session.commit()

        # First commit aborted: file untouched, write still staged.
        np.testing.assert_array_equal(
            SAC.from_file(sac_file_good).seismogram.data, original_data
        )

        session.commit()  # retry
        np.testing.assert_array_equal(
            SAC.from_file(sac_file_good).seismogram.data,
            np.zeros_like(original_data),
        )

    def test_orm_flush_failure_leaves_the_data_source_untouched(
        self, sac_file_good: Path, session: Session
    ) -> None:
        """A constraint failure at commit aborts before any file is written.

        The flush listener flushes the ORM unit of work before touching a
        data source, so an unrelated `IntegrityError` cannot leave the SAC
        file ahead of the database.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
            session (Session): Database session.
        """
        seis = _persist_sac(session, sac_file_good)
        session.commit()
        original_data = seis.data.copy()

        seis.data = np.zeros_like(original_data)
        # A duplicate 1:1 parameters row trips the unique index at flush.
        session.add(AimbatSeismogramParameters(seismogram_id=seis.id))

        with pytest.raises(IntegrityError):
            session.commit()

        np.testing.assert_array_equal(
            SAC.from_file(sac_file_good).seismogram.data, original_data
        )

        session.rollback()
        np.testing.assert_array_equal(seis.data, original_data)
