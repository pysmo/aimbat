"""Integration tests for count properties and cascade deletes in AIMBAT models."""

import pytest
from sqlmodel import Session, select

from aimbat.core._snapshot import create_snapshot
from aimbat.models import (
    AimbatDataSource,
    AimbatEvent,
    AimbatPhaseParametersSnapshot,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    AimbatSeismogramParametersSnapshot,
    AimbatSnapshot,
)

from testsupport.project import first


@pytest.fixture
def session(loaded_session: Session) -> Session:
    """Provides a session with multi-event data pre-loaded.

    Args:
        loaded_session: A SQLModel Session with data populated.

    Returns:
        The database session.
    """
    return loaded_session


@pytest.fixture
def event(session: Session) -> AimbatEvent:
    """Provides the first event from the database.

    Args:
        session: The database session.

    Returns:
        An AimbatEvent.
    """
    return first(session, AimbatEvent)


@pytest.fixture
def seismogram(session: Session) -> AimbatSeismogram:
    """Provides the first seismogram from the database.

    Args:
        session: The database session.

    Returns:
        An AimbatSeismogram.
    """
    return first(session, AimbatSeismogram)


# ---------------------------------------------------------------------------
# Count properties
# ---------------------------------------------------------------------------


class TestEventCounts:
    """Tests for the count properties on AimbatEvent."""

    def test_event_seismogram_count(self, event: AimbatEvent) -> None:
        """Verifies that seismogram_count matches the number of related seismograms.

        Args:
            event: An AimbatEvent instance.
        """
        assert event.seismogram_count == len(event.seismograms)

    def test_event_station_count(self, event: AimbatEvent) -> None:
        """Verifies that station_count reflects the number of unique stations.

        Args:
            event: An AimbatEvent instance.
        """
        unique_stations = {s.station_id for s in event.seismograms}
        assert event.station_count == len(unique_stations)


class TestSnapshotCounts:
    """Tests for the count properties on AimbatSnapshot."""

    def test_snapshot_seismogram_count(
        self, session: Session, event: AimbatEvent
    ) -> None:
        """Verifies that seismogram_count matches the number of seismogram parameter snapshots.

        Args:
            session: The database session.
            event: An AimbatEvent instance.
        """
        create_snapshot(session, event.phases[0].id)
        snapshot = session.exec(select(AimbatSnapshot)).one()
        session.refresh(snapshot)
        assert snapshot.seismogram_count == len(
            snapshot.seismogram_parameters_snapshots
        )

    def test_snapshot_counts_reflect_toggled_flip_and_select(
        self, session: Session, event: AimbatEvent
    ) -> None:
        """Verifies snapshot counts reflect toggled flip and select on seismograms.

        Flips one seismogram and deselects another, then takes a snapshot and
        checks that flipped_seismogram_count and selected_seismogram_count
        capture the changes.

        Args:
            session: The database session.
            event: An AimbatEvent instance.
        """
        seismograms = event.seismograms
        assert len(seismograms) >= 2

        to_flip = seismograms[0]
        to_deselect = seismograms[1]

        to_flip.phase_rows[0].flip = True
        to_deselect.phase_rows[0].select = False
        session.add(to_flip.phase_rows[0])
        session.add(to_deselect.phase_rows[0])
        session.commit()

        create_snapshot(session, event.phases[0].id)
        snapshot = session.exec(select(AimbatSnapshot)).one()
        session.refresh(snapshot)

        total = len(snapshot.seismogram_parameters_snapshots)
        assert snapshot.flipped_seismogram_count == 1
        assert snapshot.selected_seismogram_count == total - 1


# ---------------------------------------------------------------------------
# Cascade delete
# ---------------------------------------------------------------------------


class TestCascadeDeleteEvent:
    """Tests that deleting an event cascades to all its dependants."""

    def test_snapshots_deleted(self, session: Session, event: AimbatEvent) -> None:
        """Verifies that deleting an event removes all its snapshots.

        Args:
            session: The database session.
            event: An AimbatEvent to delete.
        """
        create_snapshot(session, event.phases[0].id)
        session.refresh(event)
        snapshot_ids = [s.id for phase in event.phases for s in phase.snapshots]
        assert snapshot_ids

        session.delete(event)
        session.commit()

        for sid in snapshot_ids:
            assert session.get(AimbatSnapshot, sid) is None

    def test_snapshot_parameter_snapshots_deleted(
        self, session: Session, event: AimbatEvent
    ) -> None:
        """Verifies that deleting an event removes all descendant parameter snapshots.

        Args:
            session: The database session.
            event: An AimbatEvent to delete.
        """
        create_snapshot(session, event.phases[0].id)
        session.refresh(event)

        session.delete(event)
        session.commit()

        assert len(session.exec(select(AimbatPhaseParametersSnapshot)).all()) == 0
        assert len(session.exec(select(AimbatSeismogramParametersSnapshot)).all()) == 0


class TestCascadeDeleteSeismogram:
    """Tests that deleting a seismogram cascades to all its dependants."""

    def test_datasource_deleted(
        self, session: Session, seismogram: AimbatSeismogram
    ) -> None:
        """Verifies that deleting a seismogram removes its datasource.

        Args:
            session: The database session.
            seismogram: An AimbatSeismogram to delete.
        """
        datasource_id = seismogram.datasource.id

        session.delete(seismogram)
        session.commit()

        assert session.get(AimbatDataSource, datasource_id) is None

    def test_parameters_deleted(
        self, session: Session, seismogram: AimbatSeismogram
    ) -> None:
        """Verifies that deleting a seismogram removes its parameters.

        Args:
            session: The database session.
            seismogram: An AimbatSeismogram to delete.
        """
        parameters_id = seismogram.phase_rows[0].id

        session.delete(seismogram)
        session.commit()

        assert session.get(AimbatSeismogramParameters, parameters_id) is None
