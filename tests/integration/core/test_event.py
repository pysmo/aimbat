"""Integration tests for event management functions in aimbat.core."""

import uuid

import pytest
from pandas import Timedelta
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlalchemy import event as sa_event
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, select

from aimbat.core import (
    IccsValidationError,
    delete_event,
    dump_event_parameter_table,
    dump_event_table,
    get_completed_events,
    get_events_using_station,
    set_event_parameter,
    set_event_parameters,
    toggle_event_completed,
)
from aimbat.core import _iccs as core_iccs
from aimbat.models import AimbatEvent, AimbatEventQuality, AimbatStation
from aimbat.types import EventParameter
from aimbat.utils import format_validation_error

# ===================================================================
# Default event
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
        target.parameters.completed = True
        loaded_session.add(target)
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
# Event parameters
# ===================================================================


class TestSetEventParameter:
    """Tests for writing parameter values to the default event."""

    def test_set_timedelta_parameter(self, loaded_session: Session) -> None:
        """Verifies that a Timedelta parameter is persisted correctly.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        new_value = Timedelta(seconds=20)
        set_event_parameter(
            loaded_session, event.id, EventParameter.WINDOW_POST, new_value
        )
        assert event.parameters.window_post == new_value

    def test_set_float_parameter(self, loaded_session: Session) -> None:
        """Verifies that a float parameter is persisted correctly.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        new_value = 0.75
        set_event_parameter(loaded_session, event.id, EventParameter.MIN_CC, new_value)
        assert event.parameters.min_cc == new_value

    def test_set_bool_parameter(self, loaded_session: Session) -> None:
        """Verifies that a bool parameter is persisted correctly.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        set_event_parameter(loaded_session, event.id, EventParameter.COMPLETED, True)
        assert event.parameters.completed is True

    def test_set_parameter_with_validate_iccs(self, loaded_session: Session) -> None:
        """Verifies that validate_iccs=True triggers ICCS validation.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None

        # Test valid change
        new_value = Timedelta(seconds=1.5)
        set_event_parameter(
            loaded_session,
            event.id,
            EventParameter.WINDOW_POST,
            new_value,
            validate_iccs=True,
        )
        assert event.parameters.window_post == new_value

        # Test invalid change (e.g., window that would result in no data)
        # Very large window might fail construction if it exceeds data bounds
        with pytest.raises(IccsValidationError, match="ICCS validation failed"):
            set_event_parameter(
                loaded_session,
                event.id,
                EventParameter.WINDOW_POST,
                Timedelta(seconds=10000),
                validate_iccs=True,
            )
        assert event.parameters.window_post == new_value

    def test_validate_iccs_does_not_relabel_a_bug(
        self, loaded_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifies a non-parameter failure propagates instead of becoming a ValueError.

        Args:
            loaded_session: The database session.
            monkeypatch: Pytest monkeypatch fixture.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None

        def _boom(*args: object, **kwargs: object) -> None:
            raise TypeError("not a parameter problem")

        monkeypatch.setattr(core_iccs, "_build_iccs", _boom)

        with pytest.raises(TypeError, match="not a parameter problem"):
            set_event_parameter(
                loaded_session,
                event.id,
                EventParameter.WINDOW_POST,
                Timedelta(seconds=2),
                validate_iccs=True,
            )

    def test_set_parameter_persists_across_sessions(
        self, loaded_engine: Engine
    ) -> None:
        """Verifies a change survives the session it was made in being closed.

        Callers (TUI, CLI) always call `set_event_parameter` inside a
        `with Session(engine) as session:` block and never commit
        themselves, so the write must be durable by the time that session
        closes — whether via this function's own commit or one it triggers
        indirectly (e.g. `clear_mccc_quality`). Guards against the change
        (and the `last_modified` DB trigger it fires) being silently rolled
        back on session close.
        """
        with Session(loaded_engine) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            event_id = event.id
            assert event.last_modified is None
            new_value = Timedelta(seconds=20)
            set_event_parameter(
                session, event_id, EventParameter.WINDOW_POST, new_value
            )

        with Session(loaded_engine) as session:
            event = session.get(AimbatEvent, event_id)
            assert event is not None
            assert event.parameters.window_post == new_value
            assert event.last_modified is not None

    def test_rejected_bandpass_bound_names_the_order_that_works(
        self, loaded_session: Session
    ) -> None:
        """Verifies a rejected bandpass bound says how to move the band.

        The TUI parameters modal and the CLI both write one bound at a time,
        so moving the band up fails if `bandpass_fmin` is set first. That is
        recoverable - widening before narrowing always validates - but only
        if the message says so.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        set_event_parameters(
            loaded_session,
            event.id,
            {
                EventParameter.BANDPASS_FMIN: 0.5,
                EventParameter.BANDPASS_FMAX: 1.0,
            },
        )

        with pytest.raises(ValidationError) as excinfo:
            set_event_parameter(
                loaded_session, event.id, EventParameter.BANDPASS_FMIN, 1.5
            )
        message = format_validation_error(excinfo.value)
        assert "bandpass_fmax (1 Hz)" in message
        assert "bandpass_fmin (1.5 Hz)" in message
        assert "raise bandpass_fmax before bandpass_fmin" in message

        # The order the message gives: widen first, then narrow.
        set_event_parameter(loaded_session, event.id, EventParameter.BANDPASS_FMAX, 2.0)
        set_event_parameter(loaded_session, event.id, EventParameter.BANDPASS_FMIN, 1.5)
        assert event.parameters.bandpass_fmin == 1.5
        assert event.parameters.bandpass_fmax == 2.0


class TestSetEventParameters:
    """Tests for the batched multi-parameter writer."""

    def test_batch_crosses_the_fmax_over_fmin_boundary(
        self, loaded_session: Session
    ) -> None:
        """A new fmin above the old fmax fails one field at a time but is fine
        as a batch (validated against the merged state)."""
        from aimbat.core import set_event_parameters

        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        event.parameters.bandpass_fmin = 0.5
        event.parameters.bandpass_fmax = 2.0
        loaded_session.add(event.parameters)
        loaded_session.commit()

        # One field at a time: raising fmin to 5 fails against the old fmax=2.
        with pytest.raises(ValueError):
            set_event_parameter(
                loaded_session, event.id, EventParameter.BANDPASS_FMIN, 5.0
            )

        # As a batch it validates against fmin=5, fmax=10 together.
        set_event_parameters(
            loaded_session,
            event.id,
            {
                EventParameter.BANDPASS_FMIN: 5.0,
                EventParameter.BANDPASS_FMAX: 10.0,
            },
        )
        assert event.parameters.bandpass_fmin == 5.0
        assert event.parameters.bandpass_fmax == 10.0

    def test_empty_mapping_is_a_noop(self, loaded_session: Session) -> None:
        from aimbat.core import set_event_parameters

        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        set_event_parameters(loaded_session, event.id, {})
        loaded_session.refresh(event)
        assert event.last_modified is None

    def test_unknown_event_raises_even_with_empty_mapping(
        self, loaded_session: Session
    ) -> None:
        from aimbat.core import set_event_parameters

        with pytest.raises(NoResultFound):
            set_event_parameters(loaded_session, uuid.uuid4(), {})


class TestToggleEventCompleted:
    """Tests for flipping an event's `completed` flag."""

    def test_toggle_flips_false_to_true(self, loaded_session: Session) -> None:
        """Verifies the flag flips and the new value is returned.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        assert event.parameters.completed is False

        result = toggle_event_completed(loaded_session, event.id)

        assert result is True
        assert event.parameters.completed is True

    def test_toggle_twice_returns_to_original(self, loaded_session: Session) -> None:
        """Verifies a second toggle flips the flag back.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None

        toggle_event_completed(loaded_session, event.id)
        result = toggle_event_completed(loaded_session, event.id)

        assert result is False
        assert event.parameters.completed is False

    def test_toggle_not_found_raises(self, loaded_session: Session) -> None:
        """Verifies a missing event ID raises NoResultFound.

        Args:
            loaded_session: The database session.
        """
        with pytest.raises(NoResultFound):
            toggle_event_completed(loaded_session, uuid.uuid4())

    def test_toggle_does_not_clear_mccc_quality(self, loaded_session: Session) -> None:
        """Verifies toggling `completed` leaves MCCC quality untouched.

        `completed` is deliberately excluded from both parameter hashes used
        for snapshot matching (see `compute_iccs_hash` / `compute_mccc_hash`),
        so this must not go through `set_event_parameter`'s
        snapshot-sync/MCCC-invalidation path the way real processing
        parameters do.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        rmse = Timedelta(milliseconds=1)
        loaded_session.add(
            AimbatEventQuality(id=uuid.uuid4(), event_id=event.id, mccc_rmse=rmse)
        )
        loaded_session.commit()

        toggle_event_completed(loaded_session, event.id)

        loaded_session.refresh(event)
        assert event.quality is not None
        assert event.quality.mccc_rmse == rmse

    def test_toggle_does_not_bump_last_modified(self, loaded_session: Session) -> None:
        """Verifies toggling `completed` leaves `last_modified` untouched.

        Regression test: the `event_modified_on_params_update` trigger must
        exclude `completed`, the same way the parameter hashes do, so that a
        bookkeeping-only change does not force a live ICCS instance to be
        treated as stale (see core/_project.py trigger 1).

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        event.parameters.ramp_width = event.parameters.ramp_width + 0.5
        loaded_session.add(event.parameters)
        loaded_session.commit()
        loaded_session.refresh(event)
        last_modified_before = event.last_modified
        assert last_modified_before is not None

        toggle_event_completed(loaded_session, event.id)

        loaded_session.refresh(event)
        assert event.last_modified == last_modified_before


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
        assert "last_modified" in result[0]

    def test_from_read_model_with_alias(self, loaded_session: Session) -> None:
        """Verifies that aliases are used when by_alias=True.

        Args:
            loaded_session: The database session.
        """
        result = dump_event_table(loaded_session, from_read_model=True, by_alias=True)
        assert isinstance(result, list)
        assert len(result) > 0
        assert "lastModified" in result[0]
        assert "last_modified" not in result[0]

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


class TestDumpEventParameterTableToJson:
    """Tests for serialising the event parameter table to JSON."""

    def test_all_events_as_list(self, loaded_session: Session) -> None:
        """Verifies that a list of dicts of all event parameters is returned.

        Args:
            loaded_session: The database session.
        """
        result = dump_event_parameter_table(loaded_session)
        assert isinstance(result, list)
        assert len(result) > 0
        assert "min_cc" in result[0]
        assert "window_pre" in result[0]
        assert "window_post" in result[0]

    def test_all_events_with_alias(self, loaded_session: Session) -> None:
        """Verifies that aliases are used when by_alias=True.

        Args:
            loaded_session: The database session.
        """
        result = dump_event_parameter_table(loaded_session, by_alias=True)
        assert isinstance(result, list)
        assert len(result) > 0
        assert "minCc" in result[0]
        assert "windowPre" in result[0]
        assert "windowPost" in result[0]
        assert "min_cc" not in result[0]
