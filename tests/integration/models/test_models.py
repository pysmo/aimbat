"""Integration tests for AIMBAT SQLModel ORM classes.

Tests cover cascade deletes, the single-default-event constraint,
type validation, and round-trip persistence of custom time types.
"""

import pytest
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
from aimbat.io import DataType
from datetime import timezone
from pandas import Timedelta, Timestamp
from pydantic import ValidationError
from sqlmodel import Session, select
from collections.abc import Generator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def session(patched_session: Session) -> Generator[Session, None, None]:
    yield patched_session


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

    def test_delete_event_cascades_to_parameters(self, session: Session) -> None:
        """Verifies that deleting an event also deletes its parameters.

        Args:
            session (Session): Database session.
        """
        ev = _make_event(session)
        session.commit()

        assert session.exec(select(AimbatEventParameters)).one() is not None

        session.delete(ev)
        session.commit()

        assert session.exec(select(AimbatEventParameters)).first() is None

    def test_delete_event_cascades_to_seismograms(self, session: Session) -> None:
        """Verifies that deleting an event also deletes its seismograms.

        Args:
            session (Session): Database session.
        """
        ev = _make_event(session)
        sta = _make_station(session)
        _make_seismogram(session, ev, sta)
        session.commit()

        assert len(session.exec(select(AimbatSeismogram)).all()) == 1

        session.delete(ev)
        session.commit()

        assert len(session.exec(select(AimbatSeismogram)).all()) == 0

    def test_delete_event_cascades_to_datasource(self, session: Session) -> None:
        """Verifies that deleting an event cascades to delete datasources (via seismograms).

        Args:
            session (Session): Database session.
        """
        ev = _make_event(session)
        sta = _make_station(session)
        _make_seismogram(session, ev, sta)
        session.commit()

        assert session.exec(select(AimbatDataSource)).first() is not None

        session.delete(ev)
        session.commit()

        assert session.exec(select(AimbatDataSource)).first() is None

    def test_delete_event_cascades_to_seismogram_parameters(
        self, session: Session
    ) -> None:
        """Verifies that deleting an event cascades to delete seismogram parameters.

        Args:
            session (Session): Database session.
        """
        ev = _make_event(session)
        sta = _make_station(session)
        _make_seismogram(session, ev, sta)
        session.commit()

        assert session.exec(select(AimbatSeismogramParameters)).first() is not None

        session.delete(ev)
        session.commit()

        assert session.exec(select(AimbatSeismogramParameters)).first() is None

    def test_delete_event_cascades_to_snapshots(self, session: Session) -> None:
        """Verifies that deleting an event deletes related snapshots and their parameter copies.

        Args:
            session (Session): Database session.
        """
        ev = _make_event(session, is_default=True)
        sta = _make_station(session)
        _make_seismogram(session, ev, sta)
        session.commit()

        # Create a snapshot via the core helper (uses the default event).
        from aimbat.core import create_snapshot, get_default_event

        default_event = get_default_event(session)
        create_snapshot(session, default_event, comment="before delete")
        assert len(session.exec(select(AimbatSnapshot)).all()) == 1
        assert len(session.exec(select(AimbatEventParametersSnapshot)).all()) == 1
        assert len(session.exec(select(AimbatSeismogramParametersSnapshot)).all()) == 1

        session.delete(ev)
        session.commit()

        assert len(session.exec(select(AimbatSnapshot)).all()) == 0
        assert len(session.exec(select(AimbatEventParametersSnapshot)).all()) == 0
        assert len(session.exec(select(AimbatSeismogramParametersSnapshot)).all()) == 0

    def test_delete_event_does_not_delete_station(self, session: Session) -> None:
        """Stations are shared across events and must survive event deletion.

        Args:
            session (Session): Database session.
        """
        ev = _make_event(session)
        sta = _make_station(session)
        _make_seismogram(session, ev, sta)
        session.commit()

        session.delete(ev)
        session.commit()

        remaining = session.exec(select(AimbatStation)).all()
        assert len(remaining) == 1
        assert remaining[0].id == sta.id


class TestCascadeDeleteStation:
    """Deleting a station must remove its seismograms (and their children)."""

    def test_delete_station_cascades_to_seismograms(self, session: Session) -> None:
        """Verifies that deleting a station removes associated seismograms and their children.

        Args:
            session (Session): Database session.
        """
        ev = _make_event(session)
        sta = _make_station(session)
        _make_seismogram(session, ev, sta)
        session.commit()

        session.delete(sta)
        session.commit()

        assert len(session.exec(select(AimbatSeismogram)).all()) == 0
        assert session.exec(select(AimbatDataSource)).first() is None
        assert session.exec(select(AimbatSeismogramParameters)).first() is None


class TestCascadeDeleteSnapshot:
    """Deleting a snapshot must remove its parameter snapshots."""

    def test_delete_snapshot_cascades_to_parameter_snapshots(
        self, session: Session
    ) -> None:
        """Verifies that deleting a snapshot removes its associated parameter snapshots.

        Args:
            session (Session): Database session.
        """
        ev = _make_event(session, is_default=True)
        sta = _make_station(session)
        _make_seismogram(session, ev, sta)
        session.commit()

        from aimbat.core import create_snapshot, get_default_event

        default_event = get_default_event(session)
        create_snapshot(session, default_event)

        snapshot = session.exec(select(AimbatSnapshot)).one()
        session.delete(snapshot)
        session.commit()

        assert len(session.exec(select(AimbatEventParametersSnapshot)).all()) == 0
        assert len(session.exec(select(AimbatSeismogramParametersSnapshot)).all()) == 0


# ===================================================================
# Single default event constraint
# ===================================================================


class TestSingleDefaultEvent:
    """The DB trigger ensures at most one event has is_default=True."""

    def test_only_one_default_event_via_insert(self, session: Session) -> None:
        """Inserting a new default event deactivates the previous one.

        Args:
            session (Session): Database session.
        """
        ev1 = _make_event(session, is_default=True)
        session.commit()
        session.refresh(ev1)
        assert ev1.is_default is True

        ev2 = _make_event(session, time="2011-03-11T05:46:24", is_default=True)
        session.commit()

        session.refresh(ev1)
        session.refresh(ev2)
        assert ev1.is_default is None
        assert ev2.is_default is True

    def test_only_one_default_event_via_update(self, session: Session) -> None:
        """Updating an event to the default event replaces the previous one.

        Args:
            session (Session): Database session.
        """
        ev1 = _make_event(session, is_default=True)
        ev2 = _make_event(session, time="2011-03-11T05:46:24")
        session.commit()

        ev2.is_default = True
        session.add(ev2)
        session.commit()

        session.refresh(ev1)
        session.refresh(ev2)
        assert ev1.is_default is None
        assert ev2.is_default is True

    def test_multiple_non_default_events_allowed(self, session: Session) -> None:
        """Multiple events may exist without any being the default.

        Args:
            session (Session): Database session.
        """
        _make_event(session, time="2010-01-01T00:00:00")
        _make_event(session, time="2011-01-01T00:00:00")
        _make_event(session, time="2012-01-01T00:00:00")
        session.commit()

        is_default_events = session.exec(
            select(AimbatEvent).where(AimbatEvent.is_default == True)  # noqa: E712
        ).all()
        assert len(is_default_events) == 0

    def test_cycling_default_through_three_events(self, session: Session) -> None:
        """Verifies cycling default status through multiple events ensures only one is the default at a time.

        Args:
            session (Session): Database session.
        """
        ev1 = _make_event(session, time="2010-01-01T00:00:00", is_default=True)
        ev2 = _make_event(session, time="2011-01-01T00:00:00")
        ev3 = _make_event(session, time="2012-01-01T00:00:00")
        session.commit()

        for target in [ev2, ev3, ev1]:
            target.is_default = True
            session.add(target)
            session.commit()

            is_default_events = session.exec(
                select(AimbatEvent).where(AimbatEvent.is_default == True)  # noqa: E712
            ).all()
            assert len(is_default_events) == 1
            session.refresh(target)
            assert target.is_default is True


# ===================================================================
# Type validation
# ===================================================================


class TestEventValidation:
    """Pydantic validation on AimbatEvent fields."""

    def test_event_time_accepts_string(self, session: Session) -> None:
        """Verifies that the event time field accepts ISO format strings and converts them to Timestamp.

        Args:
            session (Session): Database session.
        """
        ev = AimbatEvent(
            time="2010-02-27T06:34:14+00:00",
            latitude=0.0,
            longitude=0.0,
        )
        session.add(ev)
        session.flush()
        params = AimbatEventParameters(event=ev)
        session.add(params)
        session.commit()

        session.refresh(ev)
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

    def test_min_ccnorm_rejects_out_of_range(self) -> None:
        """Verifies that min_ccnorm rejects values > 1.0."""
        with pytest.raises(ValidationError):
            AimbatEventParametersBase(min_ccnorm=1.5)

    def test_min_ccnorm_rejects_negative(self) -> None:
        """Verifies that min_ccnorm rejects negative values."""
        with pytest.raises(ValidationError):
            AimbatEventParametersBase(min_ccnorm=-0.1)

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
            AimbatEventParameters.model_validate({"min_ccnorm": 1.5})

    def test_valid_parameters_accepted(self, session: Session) -> None:
        """Verifies that valid parameters are accepted.

        Args:
            session (Session): Database session.
        """
        ev = _make_event(session)
        session.commit()
        session.refresh(ev)

        params = ev.parameters
        assert params.completed is False
        assert params.min_ccnorm >= 0
        assert params.min_ccnorm <= 1
        assert params.window_pre.total_seconds() < 0
        assert params.window_post.total_seconds() > 0


class TestSeismogramParametersValidation:
    """Validation rules on seismogram-related models."""

    def test_default_select_is_true(self, session: Session) -> None:
        """Verifies that the default 'select' parameter is True.

        Args:
            session (Session): Database session.
        """
        ev = _make_event(session)
        sta = _make_station(session)
        seis = _make_seismogram(session, ev, sta)
        session.commit()
        session.refresh(seis)

        assert seis.parameters.select is True

    def test_default_flip_is_false(self, session: Session) -> None:
        """Verifies that the default 'flip' parameter is False.

        Args:
            session (Session): Database session.
        """
        ev = _make_event(session)
        sta = _make_station(session)
        seis = _make_seismogram(session, ev, sta)
        session.commit()
        session.refresh(seis)

        assert seis.parameters.flip is False

    def test_default_t1_is_none(self, session: Session) -> None:
        """Verifies that the default 't1' parameter is None.

        Args:
            session (Session): Database session.
        """
        ev = _make_event(session)
        sta = _make_station(session)
        seis = _make_seismogram(session, ev, sta)
        session.commit()
        session.refresh(seis)

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

    def test_event_time_round_trip(self, session: Session) -> None:
        """Verifies round-trip persistence of event time as a Timestamp.

        Args:
            session (Session): Database session.
        """
        ts = Timestamp("2010-02-27T06:34:14", tz=timezone.utc)
        ev = _make_event(session, time="2010-02-27T06:34:14")
        session.commit()

        session.refresh(ev)
        assert isinstance(ev.time, Timestamp)
        assert ev.time == ts

    def test_seismogram_times_round_trip(self, session: Session) -> None:
        """Verifies round-trip persistence of seismogram times as Timestamps.

        Args:
            session (Session): Database session.
        """
        ev = _make_event(session)
        sta = _make_station(session)
        seis = _make_seismogram(session, ev, sta)
        session.commit()

        session.refresh(seis)
        assert isinstance(seis.begin_time, Timestamp)
        assert isinstance(seis.t0, Timestamp)


class TestTimedeltaRoundTrip:
    """Pandas Timedelta values survive a write→read cycle via SQLAlchemy."""

    def test_event_parameters_window_round_trip(self, session: Session) -> None:
        """Verifies round-trip persistence of event parameter windows as Timedeltas.

        Args:
            session (Session): Database session.
        """
        ev = _make_event(session)
        session.commit()

        session.refresh(ev)
        params = ev.parameters
        assert isinstance(params.window_pre, Timedelta)
        assert isinstance(params.window_post, Timedelta)
        assert params.window_pre.total_seconds() < 0
        assert params.window_post.total_seconds() > 0

    def test_seismogram_delta_round_trip(self, session: Session) -> None:
        """Verifies round-trip persistence of seismogram delta as Timedelta.

        Args:
            session (Session): Database session.
        """
        ev = _make_event(session)
        sta = _make_station(session)
        seis = _make_seismogram(session, ev, sta)
        session.commit()

        session.refresh(seis)
        assert isinstance(seis.delta, Timedelta)
        assert seis.delta == Timedelta(seconds=0.05)


# ===================================================================
# Unique constraints
# ===================================================================


class TestUniqueConstraints:
    """Verify that unique column constraints are enforced."""

    def test_duplicate_event_time_rejected(self, session: Session) -> None:
        """Verifies that creating two events with the same time raises an IntegrityError.

        Args:
            session (Session): Database session.
        """
        from sqlalchemy.exc import IntegrityError

        same_time = "2010-02-27T06:34:14"
        _make_event(session, time=same_time)
        session.commit()

        # Manually insert a second event with the same time (bypass helper flush).
        ev2 = AimbatEvent(
            time=Timestamp(same_time, tz=timezone.utc),
            latitude=0.0,
            longitude=0.0,
        )
        session.add(ev2)
        with pytest.raises(IntegrityError):
            session.flush()

    def test_different_event_times_allowed(self, session: Session) -> None:
        """Verifies that events with different times are allowed.

        Args:
            session (Session): Database session.
        """
        _make_event(session, time="2010-01-01T00:00:00")
        _make_event(session, time="2011-01-01T00:00:00")
        session.commit()

        events = session.exec(select(AimbatEvent)).all()
        assert len(events) == 2
