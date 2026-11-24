import pytest
from sqlmodel import Session, select

from aimbat.core._snapshot import create_snapshot
from aimbat.core._validity import Validity
from aimbat.models import (
    AimbatEvent,
    AimbatSeismogram,
    AimbatSeismogramRead,
    AimbatSnapshot,
    AimbatSnapshotRead,
    AimbatStation,
    AimbatStationRead,
)
from aimbat.models._readers import SnapshotSeismogramResult

from testsupport.project import first


@pytest.fixture
def mock_station(loaded_session: Session) -> AimbatStation:
    """Returns the first station from the loaded session."""
    return first(loaded_session, AimbatStation)


@pytest.fixture
def mock_seismogram(loaded_session: Session) -> AimbatSeismogram:
    """Returns the first seismogram from the loaded session."""
    return first(loaded_session, AimbatSeismogram)


@pytest.fixture
def mock_snapshot(loaded_session: Session) -> AimbatSnapshot:
    """Creates and returns a snapshot for the first event."""
    event = first(loaded_session, AimbatEvent)
    create_snapshot(loaded_session, event.phases[0].id, comment="test snapshot")
    snapshot = loaded_session.exec(select(AimbatSnapshot)).one_or_none()
    assert snapshot is not None
    return snapshot


def test_station_read_short_id(
    loaded_session: Session, mock_station: AimbatStation
) -> None:
    # Without session
    read = AimbatStationRead.from_station(mock_station, Validity.read(loaded_session))
    assert read.short_id is None

    # With session
    read_with_session = AimbatStationRead.from_station(
        mock_station, Validity.read(loaded_session), session=loaded_session
    )
    assert read_with_session.short_id is not None
    assert len(read_with_session.short_id) >= 2


def test_seismogram_read_short_id(
    loaded_session: Session, mock_seismogram: AimbatSeismogram
) -> None:
    # Without session
    read = AimbatSeismogramRead.from_seismogram(
        mock_seismogram, Validity.read(loaded_session)
    )
    assert read.short_id is None

    # With session
    read_with_session = AimbatSeismogramRead.from_seismogram(
        mock_seismogram, Validity.read(loaded_session), session=loaded_session
    )
    assert read_with_session.short_id is not None
    assert len(read_with_session.short_id) >= 2


def test_snapshot_read_short_id(
    loaded_session: Session, mock_snapshot: AimbatSnapshot
) -> None:
    # Without session
    read = AimbatSnapshotRead.from_snapshot(mock_snapshot)
    assert read.short_id is None

    # With session
    read_with_session = AimbatSnapshotRead.from_snapshot(
        mock_snapshot, session=loaded_session
    )
    assert read_with_session.short_id is not None
    assert len(read_with_session.short_id) >= 2


def test_seismogram_read_location(
    loaded_session: Session, mock_seismogram: AimbatSeismogram
) -> None:
    """Rows carry the location code, so streams at one site can be told apart."""
    mock_seismogram.station.location = "10"
    read = AimbatSeismogramRead.from_seismogram(
        mock_seismogram, Validity.read(loaded_session)
    )
    assert read.location == "10"


def test_snapshot_seismogram_result_location(mock_snapshot: AimbatSnapshot) -> None:
    """Snapshot rows read the location from the live station, empty once deleted."""
    param_snap = mock_snapshot.seismogram_parameters_snapshots[0]
    assert param_snap.parameters is not None
    seismogram = param_snap.parameters.seismogram
    seismogram.station.location = "10"
    live = SnapshotSeismogramResult.from_snapshot_records(param_snap, None, seismogram)
    deleted = SnapshotSeismogramResult.from_snapshot_records(param_snap, None, None)
    assert live.location == "10"
    assert deleted.location == ""
