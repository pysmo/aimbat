"""Integration tests for event management functions in aimbat.core."""

import uuid

import pytest
from sqlalchemy import event as sa_event
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, select

from aimbat.core import (
    delete_event,
    dump_event_table,
    get_completed_events,
    get_events_using_station,
)
from aimbat.models import AimbatEvent, AimbatStation

# ===================================================================
# Deleting events
# ===================================================================


class TestDeleteEvent:
    """Tests for deleting events from the database."""

    def test_delete_event(self, loaded_session: Session) -> None:
        """Verifies that an event is removed from the database after deletion.

        Args:
            loaded_session: The database session.
        """
        events = loaded_session.exec(select(AimbatEvent)).all()
        count_before = len(events)
        to_delete = events[0]

        delete_event(loaded_session, to_delete.id)

        remaining = loaded_session.exec(select(AimbatEvent)).all()
        assert len(remaining) == count_before - 1
        assert to_delete not in remaining

    def test_delete_event_by_id_not_found(self, loaded_session: Session) -> None:
        """Verifies that deleting a non-existent event ID raises NoResultFound.

        Args:
            loaded_session: The database session.
        """
        with pytest.raises(NoResultFound):
            delete_event(loaded_session, uuid.uuid4())


# ===================================================================
# Query events
# ===================================================================


class TestGetCompletedEvents:
    """Tests for retrieving events marked as completed."""

    def test_no_completed_events(self, loaded_session: Session) -> None:
        """Verifies that no events are returned when none are marked as completed.

        Args:
            loaded_session: The database session.
        """
        completed = get_completed_events(loaded_session)
        assert len(completed) == 0

    def test_get_completed_events(self, loaded_session: Session) -> None:
        """Verifies that only events marked as completed are returned.

        Args:
            loaded_session: The database session.
        """
        events = loaded_session.exec(select(AimbatEvent)).all()
        target = events[0]
        target.phases[0].parameters.completed = True
        loaded_session.add(target.phases[0].parameters)
        loaded_session.commit()

        completed = get_completed_events(loaded_session)
        assert len(completed) == 1
        assert target in completed


class TestGetEventsUsingStation:
    """Tests for retrieving events associated with a particular station."""

    def test_get_events_using_station(self, loaded_session: Session) -> None:
        """Verifies that events linked to a station are returned.

        Args:
            loaded_session: The database session.
        """
        station = loaded_session.exec(select(AimbatStation)).first()
        assert station is not None

        events = get_events_using_station(loaded_session, station.id)
        assert len(events) > 0
        for event in events:
            station_ids = [s.station_id for s in event.seismograms]
            assert station.id in station_ids

    def test_get_events_using_station_no_match(self, loaded_session: Session) -> None:
        """Verifies that an empty sequence is returned for a station with no events.

        Args:
            loaded_session: The database session.
        """
        orphan = AimbatStation(
            network="XX",
            name="NONE",
            location="00",
            channel="BHZ",
            latitude=0.0,
            longitude=0.0,
        )
        loaded_session.add(orphan)
        loaded_session.commit()

        events = get_events_using_station(loaded_session, orphan.id)
        assert len(events) == 0


# ===================================================================
# JSON serialisation
# ===================================================================


class TestDumpEventTableToJson:
    """Tests for serialising the event table to JSON."""

    def test_default_returns_list(self, loaded_session: Session) -> None:
        """Verifies that a list of dicts is returned by default.

        Args:
            loaded_session: The database session.
        """
        result = dump_event_table(loaded_session)
        assert isinstance(result, list)
        assert len(result) > 0
        assert "id" in result[0]

    def test_from_read_model_returns_list(self, loaded_session: Session) -> None:
        """Verifies that a list of dicts is returned when from_read_model=True.

        Args:
            loaded_session: The database session.
        """
        result = dump_event_table(loaded_session, from_read_model=True)
        assert isinstance(result, list)
        assert len(result) > 0
        assert "id" in result[0]
        assert "snapshot_count" in result[0]

    def test_from_read_model_with_alias(self, loaded_session: Session) -> None:
        """Verifies that aliases are used when by_alias=True.

        Args:
            loaded_session: The database session.
        """
        result = dump_event_table(loaded_session, from_read_model=True, by_alias=True)
        assert isinstance(result, list)
        assert len(result) > 0
        assert "snapshotCount" in result[0]
        assert "snapshot_count" not in result[0]

    def test_read_model_counts_are_loaded_with_the_events(
        self, loaded_session: Session
    ) -> None:
        """Verifies the counts the read model renders cost no extra queries.

        The count columns are deferred so that the processing paths do not
        pay for them; this path does read them, so it has to undefer them
        rather than let each one load on access, per row.
        """
        statements: list[str] = []

        def record(
            conn: object,
            cursor: object,
            statement: str,
            parameters: object,
            context: object,
            executemany: bool,
        ) -> None:
            statements.append(statement)

        bind = loaded_session.get_bind()
        sa_event.listen(bind, "before_cursor_execute", record)
        try:
            result = dump_event_table(loaded_session, from_read_model=True)
        finally:
            sa_event.remove(bind, "before_cursor_execute", record)

        assert len(result) > 0
        assert all(row["seismogram_count"] > 0 for row in result)
        counting = [s for s in statements if "count(" in s.lower()]
        assert len(counting) == 1, "counts should come from the events query itself"

    def test_orm_dump_does_not_query_counts(self, loaded_session: Session) -> None:
        """Verifies the ORM dump skips the count subqueries it never serialises.

        Args:
            loaded_session: The database session.
        """
        statements: list[str] = []

        def record(
            conn: object,
            cursor: object,
            statement: str,
            parameters: object,
            context: object,
            executemany: bool,
        ) -> None:
            statements.append(statement)

        bind = loaded_session.get_bind()
        sa_event.listen(bind, "before_cursor_execute", record)
        try:
            result = dump_event_table(loaded_session, from_read_model=False)
        finally:
            sa_event.remove(bind, "before_cursor_execute", record)

        assert len(result) > 0
        assert not [s for s in statements if "count(" in s.lower()]
