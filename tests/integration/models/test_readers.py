import pytest
from sqlmodel import Session, select

from aimbat.core._snapshot import create_snapshot
from aimbat.models import (
    AimbatEvent,
    AimbatSeismogram,
    AimbatSeismogramRead,
    AimbatSnapshot,
    AimbatSnapshotRead,
    AimbatStation,
    AimbatStationRead,
)


@pytest.fixture
def mock_station(loaded_session: Session) -> AimbatStation:
    """Returns the first station from the loaded session."""
    station = loaded_session.exec(select(AimbatStation)).first()
    assert station is not None
    return station


@pytest.fixture
def mock_seismogram(loaded_session: Session) -> AimbatSeismogram:
    """Returns the first seismogram from the loaded session."""
    seismogram = loaded_session.exec(select(AimbatSeismogram)).first()
    assert seismogram is not None
    return seismogram


@pytest.fixture
def mock_snapshot(loaded_session: Session) -> AimbatSnapshot:
    """Creates and returns a snapshot for the default event."""
    event = loaded_session.exec(select(AimbatEvent)).first()
    assert event is not None
    create_snapshot(loaded_session, event, comment="test snapshot")
    snapshot = loaded_session.exec(select(AimbatSnapshot)).one_or_none()
    assert snapshot is not None
    return snapshot


def test_station_read_short_id(
    loaded_session: Session, mock_station: AimbatStation
) -> None:
    # Without session
    read = AimbatStationRead.from_station(mock_station)
    assert read.short_id is None

    # With session
    read_with_session = AimbatStationRead.from_station(
        mock_station, session=loaded_session
    )
    assert read_with_session.short_id is not None
    assert len(read_with_session.short_id) >= 2


def test_seismogram_read_short_id(
    loaded_session: Session, mock_seismogram: AimbatSeismogram
) -> None:
    # Without session
    read = AimbatSeismogramRead.from_seismogram(mock_seismogram)
    assert read.short_id is None

    # With session
    read_with_session = AimbatSeismogramRead.from_seismogram(
        mock_seismogram, session=loaded_session
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
