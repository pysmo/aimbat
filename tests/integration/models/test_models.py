"""Integration tests for AIMBAT SQLModel ORM classes.

Tests cover cascade deletes, the single-default-event constraint,
type validation, and round-trip persistence of custom time types.
"""

from datetime import timezone

import pytest
from pandas import Timedelta, Timestamp
from pydantic import ValidationError
from sqlmodel import Session, select

from aimbat.io import DataType
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
from aimbat.models._parameters import AimbatEventParametersBase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_station(session: Session, *, name: str = "AAK") -> AimbatStation:
    """Insert and return a minimal station.

    Args:
        session (Session): Database session.
        name (str): Station name (default: "AAK").

    Returns:
        AimbatStation: The created station.
    """
    sta = AimbatStation(
        name=name,
        network="II",
        location="00",
        channel="BHZ",
        latitude=42.63,
        longitude=74.49,
    )
    session.add(sta)
    session.flush()
    return sta


def _make_event(
    session: Session,
    *,
    time: str = "2010-02-27T06:34:14",
    is_default: bool | None = None,
) -> AimbatEvent:
    """Insert and return an event together with its mandatory parameters.

    Args:
        session (Session): Database session.
        time (str): Event time string (default: "2010-02-27T06:34:14").
        is_default (bool | None): Whether the event is is_default (default: None).

    Returns:
        AimbatEvent: The created event.
    """
    ev = AimbatEvent(
        time=Timestamp(time, tz=timezone.utc),
        latitude=-36.12,
        longitude=-72.90,
        depth=22.9,
        is_default=is_default,
    )
    session.add(ev)
    session.flush()

    params = AimbatEventParameters(event=ev)
    session.add(params)
    session.flush()
    return ev


def _make_seismogram(
    session: Session,
    event: AimbatEvent,
    station: AimbatStation,
) -> AimbatSeismogram:
    """Insert and return a seismogram (with datasource and parameters).

    Args:
        session (Session): Database session.
        event (AimbatEvent): The associated event.
        station (AimbatStation): The associated station.

    Returns:
        AimbatSeismogram: The created seismogram.
    """
    seis = AimbatSeismogram(
        begin_time=Timestamp("2010-02-27T06:30:00", tz=timezone.utc),
        delta=Timedelta(seconds=0.05),
        t0=Timestamp("2010-02-27T06:40:00", tz=timezone.utc),
        event=event,
        station=station,
    )
    session.add(seis)
    session.flush()

    ds = AimbatDataSource(
        sourcename="/tmp/fake.sac",
        datatype=DataType.SAC,
        seismogram=seis,
    )
    session.add(ds)

    sp = AimbatSeismogramParameters(seismogram=seis)
    session.add(sp)

    session.flush()
    return seis


# ===================================================================
# Cascade delete tests
# ===================================================================


class TestCascadeDeleteEvent:
    """Deleting an event must remove all related children."""

    def test_delete_event_cascades_to_parameters(
        self, patched_session: Session
    ) -> None:
        """Verifies that deleting an event also deletes its parameters.

        Args:
            patched_session (Session): Database session.
        """
        ev = _make_event(patched_session)
        patched_session.commit()

        assert patched_session.exec(select(AimbatEventParameters)).one() is not None

        patched_session.delete(ev)
        patched_session.commit()

        assert patched_session.exec(select(AimbatEventParameters)).first() is None

    def test_delete_event_cascades_to_seismograms(
        self, patched_session: Session
    ) -> None:
        """Verifies that deleting an event also deletes its seismograms.

        Args:
            patched_session (Session): Database session.
        """
        ev = _make_event(patched_session)
        sta = _make_station(patched_session)
        _make_seismogram(patched_session, ev, sta)
        patched_session.commit()

        assert len(patched_session.exec(select(AimbatSeismogram)).all()) == 1

        patched_session.delete(ev)
        patched_session.commit()

        assert len(patched_session.exec(select(AimbatSeismogram)).all()) == 0

    def test_delete_event_cascades_to_datasource(
        self, patched_session: Session
    ) -> None:
        """Verifies that deleting an event cascades to delete datasources (via seismograms).

        Args:
            patched_session (Session): Database session.
        """
        ev = _make_event(patched_session)
        sta = _make_station(patched_session)
        _make_seismogram(patched_session, ev, sta)
        patched_session.commit()

        assert patched_session.exec(select(AimbatDataSource)).first() is not None

        patched_session.delete(ev)
        patched_session.commit()

        assert patched_session.exec(select(AimbatDataSource)).first() is None

    def test_delete_event_cascades_to_seismogram_parameters(
        self, patched_session: Session
    ) -> None:
        """Verifies that deleting an event cascades to delete seismogram parameters.

        Args:
            patched_session (Session): Database session.
        """
        ev = _make_event(patched_session)
        sta = _make_station(patched_session)
        _make_seismogram(patched_session, ev, sta)
        patched_session.commit()

        assert (
            patched_session.exec(select(AimbatSeismogramParameters)).first() is not None
        )

        patched_session.delete(ev)
        patched_session.commit()

        assert patched_session.exec(select(AimbatSeismogramParameters)).first() is None

    def test_delete_event_cascades_to_snapshots(self, patched_session: Session) -> None:
        """Verifies that deleting an event deletes related snapshots and their parameter copies.

        Args:
            patched_session (Session): Database session.
        """
        ev = _make_event(patched_session, is_default=True)
        sta = _make_station(patched_session)
        _make_seismogram(patched_session, ev, sta)
        patched_session.commit()

        # Create a snapshot via the core helper (uses the default event).
        from aimbat.core import create_snapshot, get_default_event

        default_event = get_default_event(patched_session)
        assert default_event is not None
        create_snapshot(patched_session, default_event, comment="before delete")
        assert len(patched_session.exec(select(AimbatSnapshot)).all()) == 1
        assert (
            len(patched_session.exec(select(AimbatEventParametersSnapshot)).all()) == 1
        )
        assert (
            len(patched_session.exec(select(AimbatSeismogramParametersSnapshot)).all())
            == 1
        )

        patched_session.delete(ev)
        patched_session.commit()

        assert len(patched_session.exec(select(AimbatSnapshot)).all()) == 0
        assert (
            len(patched_session.exec(select(AimbatEventParametersSnapshot)).all()) == 0
        )
        assert (
            len(patched_session.exec(select(AimbatSeismogramParametersSnapshot)).all())
            == 0
        )

    def test_delete_event_does_not_delete_station(
        self, patched_session: Session
    ) -> None:
        """Stations are shared across events and must survive event deletion.

        Args:
            patched_session (Session): Database session.
        """
        ev = _make_event(patched_session)
        sta = _make_station(patched_session)
        _make_seismogram(patched_session, ev, sta)
        patched_session.commit()

        patched_session.delete(ev)
        patched_session.commit()

        remaining = patched_session.exec(select(AimbatStation)).all()
        assert len(remaining) == 1
        assert remaining[0].id == sta.id


class TestCascadeDeleteStation:
    """Deleting a station must remove its seismograms (and their children)."""

    def test_delete_station_cascades_to_seismograms(
        self, patched_session: Session
    ) -> None:
        """Verifies that deleting a station removes associated seismograms and their children.

        Args:
            patched_session (Session): Database session.
        """
        ev = _make_event(patched_session)
        sta = _make_station(patched_session)
        _make_seismogram(patched_session, ev, sta)
        patched_session.commit()

        patched_session.delete(sta)
        patched_session.commit()

        assert len(patched_session.exec(select(AimbatSeismogram)).all()) == 0
        assert patched_session.exec(select(AimbatDataSource)).first() is None
        assert patched_session.exec(select(AimbatSeismogramParameters)).first() is None


class TestCascadeDeleteSnapshot:
    """Deleting a snapshot must remove its parameter snapshots."""

    def test_delete_snapshot_cascades_to_parameter_snapshots(
        self, patched_session: Session
    ) -> None:
        """Verifies that deleting a snapshot removes its associated parameter snapshots.

        Args:
            patched_session (Session): Database session.
        """
        ev = _make_event(patched_session, is_default=True)
        sta = _make_station(patched_session)
        _make_seismogram(patched_session, ev, sta)
        patched_session.commit()

        from aimbat.core import create_snapshot, get_default_event

        default_event = get_default_event(patched_session)
        assert default_event is not None
        create_snapshot(patched_session, default_event)

        snapshot = patched_session.exec(select(AimbatSnapshot)).one()
        patched_session.delete(snapshot)
        patched_session.commit()

        assert (
            len(patched_session.exec(select(AimbatEventParametersSnapshot)).all()) == 0
        )
        assert (
            len(patched_session.exec(select(AimbatSeismogramParametersSnapshot)).all())
            == 0
        )


# ===================================================================
# Single default event constraint
# ===================================================================


class TestSingleDefaultEvent:
    """The DB trigger ensures at most one event has is_default=True."""

    def test_only_one_default_event_via_insert(self, patched_session: Session) -> None:
        """Inserting a new default event deactivates the previous one.

        Args:
            patched_session (Session): Database session.
        """
        ev1 = _make_event(patched_session, is_default=True)
        patched_session.commit()
        patched_session.refresh(ev1)
        assert ev1.is_default is True

        ev2 = _make_event(patched_session, time="2011-03-11T05:46:24", is_default=True)
        patched_session.commit()

        patched_session.refresh(ev1)
        patched_session.refresh(ev2)
        assert ev1.is_default is None
        assert ev2.is_default is True

    def test_only_one_default_event_via_update(self, patched_session: Session) -> None:
        """Updating an event to the default event replaces the previous one.

        Args:
            patched_session (Session): Database session.
        """
        ev1 = _make_event(patched_session, is_default=True)
        ev2 = _make_event(patched_session, time="2011-03-11T05:46:24")
        patched_session.commit()

        ev2.is_default = True
        patched_session.add(ev2)
        patched_session.commit()

        patched_session.refresh(ev1)
        patched_session.refresh(ev2)
        assert ev1.is_default is None
        assert ev2.is_default is True

    def test_multiple_non_default_events_allowed(
        self, patched_session: Session
    ) -> None:
        """Multiple events may exist without any being the default.

        Args:
            patched_session (Session): Database session.
        """
        _make_event(patched_session, time="2010-01-01T00:00:00")
        _make_event(patched_session, time="2011-01-01T00:00:00")
        _make_event(patched_session, time="2012-01-01T00:00:00")
        patched_session.commit()

        is_default_events = patched_session.exec(
            select(AimbatEvent).where(AimbatEvent.is_default == True)  # noqa: E712
        ).all()
        assert len(is_default_events) == 0

    def test_cycling_default_through_three_events(
        self, patched_session: Session
    ) -> None:
        """Verifies cycling default status through multiple events ensures only one is the default at a time.

        Args:
            patched_session (Session): Database session.
        """
        ev1 = _make_event(patched_session, time="2010-01-01T00:00:00", is_default=True)
        ev2 = _make_event(patched_session, time="2011-01-01T00:00:00")
        ev3 = _make_event(patched_session, time="2012-01-01T00:00:00")
        patched_session.commit()

        for target in [ev2, ev3, ev1]:
            target.is_default = True
            patched_session.add(target)
            patched_session.commit()

            is_default_events = patched_session.exec(
                select(AimbatEvent).where(AimbatEvent.is_default == True)  # noqa: E712
            ).all()
            assert len(is_default_events) == 1
            patched_session.refresh(target)
            assert target.is_default is True


# ===================================================================
# Type validation
# ===================================================================


class TestEventValidation:
    """Pydantic validation on AimbatEvent fields."""

    def test_event_time_accepts_string(self, patched_session: Session) -> None:
        """Verifies that the event time field accepts ISO format strings and converts them to Timestamp.

        Args:
            patched_session (Session): Database session.
        """
        ev = AimbatEvent(
            time="2010-02-27T06:34:14+00:00",
            latitude=0.0,
            longitude=0.0,
        )
        patched_session.add(ev)
        patched_session.flush()
        params = AimbatEventParameters(event=ev)
        patched_session.add(params)
        patched_session.commit()

        patched_session.refresh(ev)
        assert isinstance(ev.time, Timestamp)

    def test_event_rejects_invalid_time(self) -> None:
        """model_validate enforces Pydantic type coercion for table models."""
        with pytest.raises(ValidationError):
            AimbatEvent.model_validate(
                {"time": "not-a-date", "latitude": 0.0, "longitude": 0.0}
            )


class TestEventParametersValidation:
    """Validation rules on AimbatEventParametersBase (non-table base class).

    SQLModel table models skip Pydantic validation on __init__, so we test
    via the base class and via model_validate on the table class.
    """

    def test_min_cc_rejects_out_of_range(self) -> None:
        """Verifies that min_cc rejects values > 1.0."""
        with pytest.raises(ValidationError):
            AimbatEventParametersBase(min_cc=1.5)

    def test_min_cc_rejects_negative(self) -> None:
        """Verifies that min_cc rejects negative values."""
        with pytest.raises(ValidationError):
            AimbatEventParametersBase(min_cc=-0.1)

    def test_window_pre_must_be_negative(self) -> None:
        """Verifies that window_pre must be a negative Timedelta."""
        with pytest.raises(ValidationError):
            AimbatEventParametersBase(window_pre=Timedelta(seconds=5))

    def test_window_post_must_be_positive(self) -> None:
        """Verifies that window_post must be a positive Timedelta."""
        with pytest.raises(ValidationError):
            AimbatEventParametersBase(window_post=Timedelta(seconds=-5))

    def test_bandpass_fmax_must_exceed_fmin(self) -> None:
        """The bandpass validator mixin is on AimbatEventParameters (table model),
        so we must use model_validate to trigger it."""
        with pytest.raises(ValidationError):
            AimbatEventParameters.model_validate(
                {"bandpass_fmin": 2.0, "bandpass_fmax": 1.0}
            )

    def test_bandpass_fmax_must_not_equal_fmin(self) -> None:
        """Verifies that bandpass_fmax cannot equal bandpass_fmin."""
        with pytest.raises(ValidationError):
            AimbatEventParameters.model_validate(
                {"bandpass_fmin": 1.0, "bandpass_fmax": 1.0}
            )

    def test_model_validate_enforces_rules_on_table_class(self) -> None:
        """model_validate on the table class must also reject invalid values."""
        with pytest.raises(ValidationError):
            AimbatEventParameters.model_validate({"min_cc": 1.5})

    def test_valid_parameters_accepted(self, patched_session: Session) -> None:
        """Verifies that valid parameters are accepted.

        Args:
            patched_session (Session): Database session.
        """
        ev = _make_event(patched_session)
        patched_session.commit()
        patched_session.refresh(ev)

        params = ev.parameters
        assert params.completed is False
        assert params.min_cc >= 0
        assert params.min_cc <= 1
        assert params.window_pre.total_seconds() < 0
        assert params.window_post.total_seconds() > 0


class TestSeismogramParametersValidation:
    """Validation rules on seismogram-related models."""

    def test_default_select_is_true(self, patched_session: Session) -> None:
        """Verifies that the default 'select' parameter is True.

        Args:
            patched_session (Session): Database session.
        """
        ev = _make_event(patched_session)
        sta = _make_station(patched_session)
        seis = _make_seismogram(patched_session, ev, sta)
        patched_session.commit()
        patched_session.refresh(seis)

        assert seis.parameters.select is True

    def test_default_flip_is_false(self, patched_session: Session) -> None:
        """Verifies that the default 'flip' parameter is False.

        Args:
            patched_session (Session): Database session.
        """
        ev = _make_event(patched_session)
        sta = _make_station(patched_session)
        seis = _make_seismogram(patched_session, ev, sta)
        patched_session.commit()
        patched_session.refresh(seis)

        assert seis.parameters.flip is False

    def test_default_t1_is_none(self, patched_session: Session) -> None:
        """Verifies that the default 't1' parameter is None.

        Args:
            patched_session (Session): Database session.
        """
        ev = _make_event(patched_session)
        sta = _make_station(patched_session)
        seis = _make_seismogram(patched_session, ev, sta)
        patched_session.commit()
        patched_session.refresh(seis)

        assert seis.parameters.t1 is None

    def test_seismogram_delta_must_be_positive(self) -> None:
        """model_validate enforces Pydantic type constraints for table models."""
        with pytest.raises(ValidationError):
            AimbatSeismogram.model_validate(
                {
                    "begin_time": Timestamp("2010-01-01", tz=timezone.utc),
                    "delta": Timedelta(seconds=-1),
                    "t0": Timestamp("2010-01-01", tz=timezone.utc),
                }
            )


# ===================================================================
# Round-trip persistence of custom time types
# ===================================================================


class TestTimestampRoundTrip:
    """Pandas Timestamp values survive a write→read cycle via SQLAlchemy."""

    def test_event_time_round_trip(self, patched_session: Session) -> None:
        """Verifies round-trip persistence of event time as a Timestamp.

        Args:
            patched_session (Session): Database session.
        """
        ts = Timestamp("2010-02-27T06:34:14", tz=timezone.utc)
        ev = _make_event(patched_session, time="2010-02-27T06:34:14")
        patched_session.commit()

        patched_session.refresh(ev)
        assert isinstance(ev.time, Timestamp)
        assert ev.time == ts

    def test_seismogram_times_round_trip(self, patched_session: Session) -> None:
        """Verifies round-trip persistence of seismogram times as Timestamps.

        Args:
            patched_session (Session): Database session.
        """
        ev = _make_event(patched_session)
        sta = _make_station(patched_session)
        seis = _make_seismogram(patched_session, ev, sta)
        patched_session.commit()

        patched_session.refresh(seis)
        assert isinstance(seis.begin_time, Timestamp)
        assert isinstance(seis.t0, Timestamp)


class TestTimedeltaRoundTrip:
    """Pandas Timedelta values survive a write→read cycle via SQLAlchemy."""

    def test_event_parameters_window_round_trip(self, patched_session: Session) -> None:
        """Verifies round-trip persistence of event parameter windows as Timedeltas.

        Args:
            patched_session (Session): Database session.
        """
        ev = _make_event(patched_session)
        patched_session.commit()

        patched_session.refresh(ev)
        params = ev.parameters
        assert isinstance(params.window_pre, Timedelta)
        assert isinstance(params.window_post, Timedelta)
        assert params.window_pre.total_seconds() < 0
        assert params.window_post.total_seconds() > 0

    def test_seismogram_delta_round_trip(self, patched_session: Session) -> None:
        """Verifies round-trip persistence of seismogram delta as Timedelta.

        Args:
            patched_session (Session): Database session.
        """
        ev = _make_event(patched_session)
        sta = _make_station(patched_session)
        seis = _make_seismogram(patched_session, ev, sta)
        patched_session.commit()

        patched_session.refresh(seis)
        assert isinstance(seis.delta, Timedelta)
        assert seis.delta == Timedelta(seconds=0.05)


# ===================================================================
# Unique constraints
# ===================================================================


class TestUniqueConstraints:
    """Verify that unique column constraints are enforced."""

    def test_duplicate_event_time_rejected(self, patched_session: Session) -> None:
        """Verifies that creating two events with the same time raises an IntegrityError.

        Args:
            patched_session (Session): Database session.
        """
        from sqlalchemy.exc import IntegrityError

        same_time = "2010-02-27T06:34:14"
        _make_event(patched_session, time=same_time)
        patched_session.commit()

        # Manually insert a second event with the same time (bypass helper flush).
        ev2 = AimbatEvent(
            time=Timestamp(same_time, tz=timezone.utc),
            latitude=0.0,
            longitude=0.0,
        )
        patched_session.add(ev2)
        with pytest.raises(IntegrityError):
            patched_session.flush()

    def test_different_event_times_allowed(self, patched_session: Session) -> None:
        """Verifies that events with different times are allowed.

        Args:
            patched_session (Session): Database session.
        """
        _make_event(patched_session, time="2010-01-01T00:00:00")
        _make_event(patched_session, time="2011-01-01T00:00:00")
        patched_session.commit()

        events = patched_session.exec(select(AimbatEvent)).all()
        assert len(events) == 2
