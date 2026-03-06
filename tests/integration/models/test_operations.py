"""Integration tests for ORM relationships and cascade deletes in AIMBAT models."""

import pytest
from aimbat.core import get_default_event
from aimbat.core._snapshot import create_snapshot
from aimbat.models import (
    AimbatDataSource,
    AimbatEvent,
    AimbatEventParameters,
    AimbatEventParametersSnapshot,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    AimbatSeismogramParametersSnapshot,
    AimbatSnapshot,
    AimbatStation,
)
from sqlmodel import Session, select


@pytest.fixture
def session(loaded_session: Session) -> Session:
    """Provides a session with multi-event data and an default event pre-loaded.

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
    return session.exec(select(AimbatEvent)).first()  # type: ignore[return-value]


@pytest.fixture
def station(session: Session) -> AimbatStation:
    """Provides the first station from the database.

    Args:
        session: The database session.

    Returns:
        An AimbatStation.
    """
    return session.exec(select(AimbatStation)).first()  # type: ignore[return-value]


@pytest.fixture
def seismogram(session: Session) -> AimbatSeismogram:
    """Provides the first seismogram from the database.

    Args:
        session: The database session.

    Returns:
        An AimbatSeismogram.
    """
    return session.exec(select(AimbatSeismogram)).first()  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Relationship traversal
# ---------------------------------------------------------------------------


class TestEventRelationships:
    """Tests for navigating relationships on AimbatEvent."""

    def test_event_has_parameters(self, event: AimbatEvent) -> None:
        """Verifies that an event exposes its parameters via the relationship.

        Args:
            event: An AimbatEvent instance.
        """
        assert isinstance(event.parameters, AimbatEventParameters)

    def test_event_parameters_back_reference(self, event: AimbatEvent) -> None:
        """Verifies that event parameters link back to their parent event.

        Args:
            event: An AimbatEvent instance.
        """
        assert event.parameters.event_id == event.id

    def test_event_has_seismograms(self, event: AimbatEvent) -> None:
        """Verifies that an event exposes its seismograms via the relationship.

        Args:
            event: An AimbatEvent instance.
        """
        assert len(event.seismograms) > 0
        assert all(isinstance(s, AimbatSeismogram) for s in event.seismograms)

    def test_seismogram_back_reference_to_event(self, event: AimbatEvent) -> None:
        """Verifies that each seismogram links back to its parent event.

        Args:
            event: An AimbatEvent instance.
        """
        for seis in event.seismograms:
            assert seis.event_id == event.id

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


class TestStationRelationships:
    """Tests for navigating relationships on AimbatStation."""

    def test_station_has_seismograms(self, station: AimbatStation) -> None:
        """Verifies that a station exposes its seismograms via the relationship.

        Args:
            station: An AimbatStation instance.
        """
        assert len(station.seismograms) > 0
        assert all(isinstance(s, AimbatSeismogram) for s in station.seismograms)

    def test_seismogram_back_reference_to_station(self, station: AimbatStation) -> None:
        """Verifies that each seismogram links back to its parent station.

        Args:
            station: An AimbatStation instance.
        """
        for seis in station.seismograms:
            assert seis.station_id == station.id


class TestSeismogramRelationships:
    """Tests for navigating relationships on AimbatSeismogram."""

    def test_seismogram_has_datasource(self, seismogram: AimbatSeismogram) -> None:
        """Verifies that a seismogram exposes its datasource via the relationship.

        Args:
            seismogram: An AimbatSeismogram instance.
        """
        assert isinstance(seismogram.datasource, AimbatDataSource)

    def test_datasource_back_reference(self, seismogram: AimbatSeismogram) -> None:
        """Verifies that the datasource links back to its parent seismogram.

        Args:
            seismogram: An AimbatSeismogram instance.
        """
        assert seismogram.datasource.seismogram_id == seismogram.id

    def test_seismogram_has_parameters(self, seismogram: AimbatSeismogram) -> None:
        """Verifies that a seismogram exposes its parameters via the relationship.

        Args:
            seismogram: An AimbatSeismogram instance.
        """
        assert isinstance(seismogram.parameters, AimbatSeismogramParameters)

    def test_seismogram_parameters_back_reference(
        self, seismogram: AimbatSeismogram
    ) -> None:
        """Verifies that seismogram parameters link back to their parent seismogram.

        Args:
            seismogram: An AimbatSeismogram instance.
        """
        assert seismogram.parameters.seismogram_id == seismogram.id

    def test_seismogram_has_event(self, seismogram: AimbatSeismogram) -> None:
        """Verifies that a seismogram exposes its parent event via the relationship.

        Args:
            seismogram: An AimbatSeismogram instance.
        """
        assert isinstance(seismogram.event, AimbatEvent)

    def test_seismogram_has_station(self, seismogram: AimbatSeismogram) -> None:
        """Verifies that a seismogram exposes its parent station via the relationship.

        Args:
            seismogram: An AimbatSeismogram instance.
        """
        assert isinstance(seismogram.station, AimbatStation)


class TestSnapshotRelationships:
    """Tests for navigating relationships on AimbatSnapshot."""

    def test_snapshot_has_event_parameters_snapshot(self, session: Session) -> None:
        """Verifies that a snapshot exposes its event parameter snapshot.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        assert default_event is not None
        create_snapshot(session, default_event)
        snapshot = session.exec(select(AimbatSnapshot)).one()
        assert isinstance(
            snapshot.event_parameters_snapshot, AimbatEventParametersSnapshot
        )

    def test_snapshot_has_seismogram_parameter_snapshots(
        self, session: Session
    ) -> None:
        """Verifies that a snapshot exposes its seismogram parameter snapshots.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        assert default_event is not None
        create_snapshot(session, default_event)
        snapshot = session.exec(select(AimbatSnapshot)).one()
        assert len(snapshot.seismogram_parameters_snapshots) > 0
        assert all(
            isinstance(s, AimbatSeismogramParametersSnapshot)
            for s in snapshot.seismogram_parameters_snapshots
        )

    def test_snapshot_back_reference_to_event(self, session: Session) -> None:
        """Verifies that a snapshot links back to its parent event.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        assert default_event is not None
        create_snapshot(session, default_event)
        snapshot = session.exec(select(AimbatSnapshot)).one()
        assert isinstance(snapshot.event, AimbatEvent)

    def test_snapshot_seismogram_count(self, session: Session) -> None:
        """Verifies that seismogram_count matches the number of seismogram parameter snapshots.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        assert default_event is not None
        create_snapshot(session, default_event)
        snapshot = session.exec(select(AimbatSnapshot)).one()
        session.refresh(snapshot)
        assert snapshot.seismogram_count == len(
            snapshot.seismogram_parameters_snapshots
        )

    def test_snapshot_selected_seismogram_count(self, session: Session) -> None:
        """Verifies that selected_seismogram_count reflects snapshots marked as selected.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        assert default_event is not None
        create_snapshot(session, default_event)
        snapshot = session.exec(select(AimbatSnapshot)).one()
        session.refresh(snapshot)
        expected = sum(1 for s in snapshot.seismogram_parameters_snapshots if s.select)
        assert snapshot.selected_seismogram_count == expected

    def test_snapshot_flipped_seismogram_count(self, session: Session) -> None:
        """Verifies that flipped_seismogram_count reflects snapshots marked as flipped.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        assert default_event is not None
        create_snapshot(session, default_event)
        snapshot = session.exec(select(AimbatSnapshot)).one()
        session.refresh(snapshot)
        expected = sum(1 for s in snapshot.seismogram_parameters_snapshots if s.flip)
        assert snapshot.flipped_seismogram_count == expected

    def test_snapshot_counts_reflect_toggled_flip_and_select(
        self, session: Session
    ) -> None:
        """Verifies snapshot counts reflect toggled flip and select on seismograms.

        Flips one seismogram and deselects another, then takes a snapshot and
        checks that flipped_seismogram_count and selected_seismogram_count
        capture the changes.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        assert default_event is not None
        seismograms = default_event.seismograms
        assert len(seismograms) >= 2

        to_flip = seismograms[0]
        to_deselect = seismograms[1]

        to_flip.parameters.flip = True
        to_deselect.parameters.select = False
        session.add(to_flip.parameters)
        session.add(to_deselect.parameters)
        session.commit()

        create_snapshot(session, default_event)
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

    def test_seismograms_deleted(self, session: Session, event: AimbatEvent) -> None:
        """Verifies that deleting an event removes all its seismograms.

        Args:
            session: The database session.
            event: An AimbatEvent to delete.
        """
        seismogram_ids = [s.id for s in event.seismograms]
        assert len(seismogram_ids) > 0

        session.delete(event)
        session.commit()

        remaining = session.exec(select(AimbatSeismogram)).all()
        remaining_ids = {s.id for s in remaining}
        assert not any(sid in remaining_ids for sid in seismogram_ids)

    def test_event_parameters_deleted(
        self, session: Session, event: AimbatEvent
    ) -> None:
        """Verifies that deleting an event removes its parameters.

        Args:
            session: The database session.
            event: An AimbatEvent to delete.
        """
        parameters_id = event.parameters.id

        session.delete(event)
        session.commit()

        assert session.get(AimbatEventParameters, parameters_id) is None

    def test_snapshots_deleted(self, session: Session, event: AimbatEvent) -> None:
        """Verifies that deleting an event removes all its snapshots.

        Args:
            session: The database session.
            event: An AimbatEvent to delete.
        """
        create_snapshot(session, event)
        session.refresh(event)
        assert len(event.snapshots) > 0
        snapshot_ids = [s.id for s in event.snapshots]

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
        create_snapshot(session, event)
        session.refresh(event)

        session.delete(event)
        session.commit()

        assert len(session.exec(select(AimbatEventParametersSnapshot)).all()) == 0
        assert len(session.exec(select(AimbatSeismogramParametersSnapshot)).all()) == 0


class TestCascadeDeleteStation:
    """Tests that deleting a station cascades to all its dependants."""

    def test_seismograms_deleted(
        self, session: Session, station: AimbatStation
    ) -> None:
        """Verifies that deleting a station removes all its seismograms.

        Args:
            session: The database session.
            station: An AimbatStation to delete.
        """
        seismogram_ids = [s.id for s in station.seismograms]
        assert len(seismogram_ids) > 0

        session.delete(station)
        session.commit()

        remaining_ids = {s.id for s in session.exec(select(AimbatSeismogram)).all()}
        assert not any(sid in remaining_ids for sid in seismogram_ids)

    def test_seismogram_parameters_deleted(
        self, session: Session, station: AimbatStation
    ) -> None:
        """Verifies that deleting a station also removes seismogram parameters.

        Args:
            session: The database session.
            station: An AimbatStation to delete.
        """
        param_ids = [s.parameters.id for s in station.seismograms]
        assert len(param_ids) > 0

        session.delete(station)
        session.commit()

        for pid in param_ids:
            assert session.get(AimbatSeismogramParameters, pid) is None

    def test_datasources_deleted(
        self, session: Session, station: AimbatStation
    ) -> None:
        """Verifies that deleting a station also removes all seismogram datasources.

        Args:
            session: The database session.
            station: An AimbatStation to delete.
        """
        datasource_ids = [s.datasource.id for s in station.seismograms]
        assert len(datasource_ids) > 0

        session.delete(station)
        session.commit()

        for did in datasource_ids:
            assert session.get(AimbatDataSource, did) is None


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
        parameters_id = seismogram.parameters.id

        session.delete(seismogram)
        session.commit()

        assert session.get(AimbatSeismogramParameters, parameters_id) is None

    def test_parameter_snapshots_deleted(
        self, session: Session, seismogram: AimbatSeismogram
    ) -> None:
        """Verifies that deleting a seismogram removes its parameter snapshots.

        Args:
            session: The database session.
            seismogram: An AimbatSeismogram to delete.
        """
        default_event = get_default_event(session)
        assert default_event is not None
        create_snapshot(session, default_event)
        parameters_id = seismogram.parameters.id

        session.delete(seismogram)
        session.commit()

        assert session.get(AimbatSeismogramParameters, parameters_id) is None
        remaining = session.exec(select(AimbatSeismogramParametersSnapshot)).all()
        assert not any(s.seismogram_parameters_id == parameters_id for s in remaining)


class TestCascadeDeleteSnapshot:
    """Tests that deleting a snapshot cascades to all its dependants."""

    def test_event_parameters_snapshot_deleted(self, session: Session) -> None:
        """Verifies that deleting a snapshot removes its event parameter snapshot.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        assert default_event is not None
        create_snapshot(session, default_event)
        snapshot = session.exec(select(AimbatSnapshot)).one()
        ep_snapshot_id = snapshot.event_parameters_snapshot.id

        session.delete(snapshot)
        session.commit()

        assert session.get(AimbatEventParametersSnapshot, ep_snapshot_id) is None

    def test_seismogram_parameters_snapshots_deleted(self, session: Session) -> None:
        """Verifies that deleting a snapshot removes all its seismogram parameter snapshots.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        assert default_event is not None
        create_snapshot(session, default_event)
        snapshot = session.exec(select(AimbatSnapshot)).one()
        sp_snapshot_ids = [s.id for s in snapshot.seismogram_parameters_snapshots]
        assert len(sp_snapshot_ids) > 0

        session.delete(snapshot)
        session.commit()

        for sid in sp_snapshot_ids:
            assert session.get(AimbatSeismogramParametersSnapshot, sid) is None
