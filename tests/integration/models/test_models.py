"""Integration tests for AIMBAT SQLModel ORM classes.

Tests cover cascade deletes, the single-default-event constraint,
type validation, and round-trip persistence of custom time types.
"""

from collections.abc import Callable
from datetime import UTC
from typing import Any

import pytest
from pandas import Timedelta, Timestamp
from pydantic import ValidationError
from sqlalchemy import event
from sqlmodel import Session, SQLModel, select

from aimbat.core import default_phase_parameters
from aimbat.io import DataType
from aimbat.models import (
    AimbatDataSource,
    AimbatEvent,
    AimbatPhase,
    AimbatPhaseParameters,
    AimbatPhaseParametersSnapshot,
    AimbatPhaseQuality,
    AimbatPick,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    AimbatSeismogramParametersSnapshot,
    AimbatSeismogramQuality,
    AimbatSeismogramQualitySnapshot,
    AimbatSnapshot,
    AimbatStation,
    PickOrigin,
)
from aimbat.models._parameters import AimbatPhaseParametersBase

from testsupport.project import add_station

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(
    session: Session,
    *,
    time: str = "2010-02-27T06:34:14",
) -> AimbatEvent:
    """Insert and return an event with one phase and its parameters.

    Args:
        session (Session): Database session.
        time (str): Event time string (default: "2010-02-27T06:34:14").

    Returns:
        AimbatEvent: The created event.
    """
    ev = AimbatEvent(
        time=Timestamp(time, tz=UTC),
        latitude=-36.12,
        longitude=-72.90,
        depth=22.9,
    )
    session.add(ev)
    session.flush()

    phase = AimbatPhase(event=ev, name="P", parameters=default_phase_parameters("P"))
    session.add(phase)
    session.flush()
    return ev


def _record_statements(session: Session, run: Callable[[], object]) -> list[str]:
    """Return the SQL statements `run` causes `session` to execute.

    Args:
        session (Session): Database session.
        run (Callable): The work to record statements for.

    Returns:
        list[str]: The recorded statements, in the order they were executed.
    """
    statements: list[str] = []
    bind = session.get_bind()

    def record(
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        statements.append(statement)

    event.listen(bind, "before_cursor_execute", record)
    try:
        run()
    finally:
        event.remove(bind, "before_cursor_execute", record)
    return statements


def _make_seismogram(
    session: Session,
    event: AimbatEvent,
    station: AimbatStation,
) -> AimbatSeismogram:
    """Insert and return a seismogram, with its datasource, pick and row.

    Args:
        session (Session): Database session.
        event (AimbatEvent): The associated event.
        station (AimbatStation): The associated station.

    Returns:
        AimbatSeismogram: The created seismogram.
    """
    seis = AimbatSeismogram(
        begin_time=Timestamp("2010-02-27T06:30:00", tz=UTC),
        delta=Timedelta(seconds=0.05),
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

    pick = AimbatPick(
        time=Timestamp("2010-02-27T06:40:00", tz=UTC),
        phase_name="P",
        origin=PickOrigin.MANUAL,
        seismogram=seis,
    )
    sp = AimbatSeismogramParameters(seismogram=seis, phase=event.phases[0], pick=pick)
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

        assert patched_session.exec(select(AimbatPhaseParameters)).one() is not None

        patched_session.delete(ev)
        patched_session.commit()

        assert patched_session.exec(select(AimbatPhaseParameters)).first() is None

    def test_delete_event_cascades_to_seismograms(
        self, patched_session: Session
    ) -> None:
        """Verifies that deleting an event also deletes its seismograms.

        Args:
            patched_session (Session): Database session.
        """
        ev = _make_event(patched_session)
        sta = add_station(patched_session)
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
        sta = add_station(patched_session)
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
        sta = add_station(patched_session)
        _make_seismogram(patched_session, ev, sta)
        patched_session.commit()

        assert (
            patched_session.exec(select(AimbatSeismogramParameters)).first() is not None
        )

        patched_session.delete(ev)
        patched_session.commit()

        assert patched_session.exec(select(AimbatSeismogramParameters)).first() is None

    def test_delete_event_does_not_delete_station(
        self, patched_session: Session
    ) -> None:
        """Stations are shared across events and must survive event deletion.

        Args:
            patched_session (Session): Database session.
        """
        ev = _make_event(patched_session)
        sta = add_station(patched_session)
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
        sta = add_station(patched_session)
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
        ev = _make_event(patched_session)
        sta = add_station(patched_session)
        _make_seismogram(patched_session, ev, sta)
        patched_session.commit()

        from aimbat.core import create_snapshot

        create_snapshot(patched_session, ev.phases[0].id)

        snapshot = patched_session.exec(select(AimbatSnapshot)).one()
        patched_session.delete(snapshot)
        patched_session.commit()

        assert (
            len(patched_session.exec(select(AimbatPhaseParametersSnapshot)).all()) == 0
        )
        assert (
            len(patched_session.exec(select(AimbatSeismogramParametersSnapshot)).all())
            == 0
        )


class TestSnapshotDurability:
    """Snapshots are frozen history: deleting a live seismogram nulls the
    references but leaves the frozen rows and their own `seismogram_id`."""

    def test_delete_seismogram_keeps_snapshot_rows(
        self, patched_session: Session
    ) -> None:
        ev = _make_event(patched_session)
        sta = add_station(patched_session)
        seis = _make_seismogram(patched_session, ev, sta)
        from aimbat.core import create_snapshot, delete_seismogram
        from aimbat.core._validity import compute_digests

        phase_id = ev.phases[0].id
        digests = compute_digests(patched_session, phase_id)[phase_id]
        patched_session.add(
            AimbatSeismogramQuality(
                parameters=seis.phase_rows[0],
                iccs_cc=0.8,
                iccs_fingerprint=digests.seismogram_cc[seis.phase_rows[0].id],
            )
        )
        patched_session.add(
            AimbatPhaseQuality(phase=ev.phases[0], mccc_rmse=Timedelta(milliseconds=1))
        )
        patched_session.commit()

        create_snapshot(patched_session, ev.phases[0].id)
        delete_seismogram(patched_session, seis.id)

        param_snaps = patched_session.exec(
            select(AimbatSeismogramParametersSnapshot)
        ).all()
        quality_snaps = patched_session.exec(
            select(AimbatSeismogramQualitySnapshot)
        ).all()

        assert len(param_snaps) == 1
        assert param_snaps[0].seismogram_id == seis.id
        assert param_snaps[0].seismogram_parameters_id is None
        assert len(quality_snaps) == 1
        assert quality_snaps[0].seismogram_id == seis.id
        assert quality_snaps[0].iccs_cc == 0.8
        assert quality_snaps[0].seismogram_parameters_id is None


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
            time="2010-02-27T06:34:14+00:00",  # type: ignore[arg-type]
            latitude=0.0,
            longitude=0.0,
        )
        patched_session.add(ev)
        patched_session.flush()
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
    """Validation rules on AimbatPhaseParametersBase (non-table base class).

    SQLModel table models skip Pydantic validation on __init__, so we test
    via the base class and via model_validate on the table class.
    """

    @staticmethod
    def _errors(model: type[AimbatPhaseParametersBase], **overrides: Any) -> list[Any]:
        """Return the validation errors of complete parameters with `overrides`."""
        values = default_phase_parameters("P").model_dump(exclude={"id", "phase_id"})
        with pytest.raises(ValidationError) as excinfo:
            model.model_validate(values | overrides)
        return excinfo.value.errors()

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("min_cc", 1.5),
            ("min_cc", -0.1),
            ("window_pre", Timedelta(seconds=5)),
            ("window_post", Timedelta(seconds=-5)),
            ("ramp_width", -0.1),
            ("bandpass_fmin", 0),
        ],
    )
    def test_field_rejects_value(self, field: str, value: Any) -> None:
        """Verifies that a value out of a field's bounds is rejected for that field."""
        errors = self._errors(AimbatPhaseParametersBase, **{field: value})
        assert [error["loc"] for error in errors] == [(field,)]

    @pytest.mark.parametrize("fmax", [1.0, 0.5])
    def test_bandpass_fmax_must_exceed_fmin(self, fmax: float) -> None:
        """Verifies that bandpass_fmax must be greater than bandpass_fmin."""
        errors = self._errors(
            AimbatPhaseParameters, bandpass_fmin=1.0, bandpass_fmax=fmax
        )
        assert "bandpass_fmax" in errors[0]["msg"]

    def test_model_validate_enforces_rules_on_table_class(self) -> None:
        """model_validate on the table class must also reject invalid values."""
        errors = self._errors(AimbatPhaseParameters, min_cc=1.5)
        assert [error["loc"] for error in errors] == [("min_cc",)]

    def test_every_field_but_completed_required(self) -> None:
        """Verifies that the parameters have no defaults apart from `completed`."""
        with pytest.raises(ValidationError) as excinfo:
            AimbatPhaseParametersBase.model_validate({})
        missing = {error["loc"][0] for error in excinfo.value.errors()}
        assert missing == set(AimbatPhaseParametersBase.model_fields) - {"completed"}

    def test_valid_parameters_accepted(self, patched_session: Session) -> None:
        """Verifies that valid parameters are accepted.

        Args:
            patched_session (Session): Database session.
        """
        ev = _make_event(patched_session)
        patched_session.commit()
        patched_session.refresh(ev)

        params = ev.phases[0].parameters
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
        sta = add_station(patched_session)
        seis = _make_seismogram(patched_session, ev, sta)
        patched_session.commit()
        patched_session.refresh(seis)

        assert seis.phase_rows[0].select is True

    def test_default_flip_is_false(self, patched_session: Session) -> None:
        """Verifies that the default 'flip' parameter is False.

        Args:
            patched_session (Session): Database session.
        """
        ev = _make_event(patched_session)
        sta = add_station(patched_session)
        seis = _make_seismogram(patched_session, ev, sta)
        patched_session.commit()
        patched_session.refresh(seis)

        assert seis.phase_rows[0].flip is False

    def test_default_refined_pick_is_none(self, patched_session: Session) -> None:
        """Verifies that the default 'refined_pick' parameter is None.

        Args:
            patched_session (Session): Database session.
        """
        ev = _make_event(patched_session)
        sta = add_station(patched_session)
        seis = _make_seismogram(patched_session, ev, sta)
        patched_session.commit()
        patched_session.refresh(seis)

        assert seis.phase_rows[0].refined_pick is None

    def test_seismogram_delta_must_be_positive(self) -> None:
        """model_validate enforces Pydantic type constraints for table models."""
        with pytest.raises(ValidationError):
            AimbatSeismogram.model_validate(
                {
                    "begin_time": Timestamp("2010-01-01", tz=UTC),
                    "delta": Timedelta(seconds=-1),
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
        ts = Timestamp("2010-02-27T06:34:14", tz=UTC)
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
        sta = add_station(patched_session)
        seis = _make_seismogram(patched_session, ev, sta)
        patched_session.commit()

        patched_session.refresh(seis)
        assert isinstance(seis.begin_time, Timestamp)


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
        params = ev.phases[0].parameters
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
        sta = add_station(patched_session)
        seis = _make_seismogram(patched_session, ev, sta)
        patched_session.commit()

        patched_session.refresh(seis)
        assert isinstance(seis.delta, Timedelta)
        assert seis.delta == Timedelta(seconds=0.05)

    def test_explicit_window_values_round_trip(self, patched_session: Session) -> None:
        """An explicitly-set window Timedelta survives write→read unchanged.

        Args:
            patched_session (Session): Database session.
        """
        ev = _make_event(patched_session)
        ev.phases[0].parameters.window_pre = Timedelta(seconds=-12.5)
        ev.phases[0].parameters.window_post = Timedelta(seconds=17.25)
        patched_session.commit()

        patched_session.expire_all()
        params = patched_session.exec(select(AimbatPhaseParameters)).one()
        assert params.window_pre == Timedelta(seconds=-12.5)
        assert params.window_post == Timedelta(seconds=17.25)

    def test_timedelta_column_reads_bare_number_as_seconds(
        self, patched_session: Session
    ) -> None:
        """A bare number written straight to a Timedelta column is seconds.

        Table models skip Pydantic validation, so a bare number can be
        assigned directly and reaches `SAPandasTimedelta` unconverted. It must
        be stored as seconds (matching `PydanticTimedelta`), not as pandas'
        nanosecond default - the 1e9 mismatch this guards against.

        Args:
            patched_session (Session): Database session.
        """
        ev = _make_event(patched_session)
        sta = add_station(patched_session)
        seis = _make_seismogram(patched_session, ev, sta)
        seis.delta = 0.05  # type: ignore[assignment]  # bare seconds, no validation
        patched_session.commit()

        patched_session.expire_all()
        reloaded = patched_session.get(AimbatSeismogram, seis.id)
        assert reloaded is not None
        assert reloaded.delta == Timedelta(seconds=0.05)


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
            time=Timestamp(same_time, tz=UTC),
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

    def test_duplicate_station_codes_rejected(self, patched_session: Session) -> None:
        """Two stations with the same four codes raise an IntegrityError."""
        from sqlalchemy.exc import IntegrityError

        for _ in range(2):
            patched_session.add(
                AimbatStation(
                    name="ABC",
                    network="XX",
                    location="00",
                    channel="BHZ",
                    latitude=0.0,
                    longitude=0.0,
                )
            )
        with pytest.raises(IntegrityError):
            patched_session.flush()

    def test_second_seismogram_of_a_station_rejected(
        self, patched_session: Session
    ) -> None:
        """Two seismograms of one event and station raise an IntegrityError."""
        from sqlalchemy.exc import IntegrityError

        event = _make_event(patched_session)
        station = add_station(patched_session)
        for _ in range(2):
            patched_session.add(
                AimbatSeismogram(
                    begin_time=Timestamp("2010-02-27T06:30:00", tz=UTC),
                    delta=Timedelta(seconds=0.05),
                    event=event,
                    station=station,
                )
            )
        with pytest.raises(IntegrityError):
            patched_session.flush()


class TestOneToOneLinkConstraints:
    """The parameters/quality tables are one row per parent - a unique index
    on the link column enforces it."""

    def test_second_row_for_seismogram_and_phase_rejected(
        self, patched_session: Session
    ) -> None:
        from sqlalchemy.exc import IntegrityError

        ev = _make_event(patched_session)
        sta = add_station(patched_session)
        seis = _make_seismogram(patched_session, ev, sta)
        patched_session.commit()

        pick = AimbatPick(
            time=seis.phase_rows[0].initial_pick,
            phase_name="P",
            origin=PickOrigin.MANUAL,
            seismogram=seis,
        )
        patched_session.add(
            AimbatSeismogramParameters(seismogram=seis, phase=ev.phases[0], pick=pick)
        )
        with pytest.raises(IntegrityError):
            patched_session.flush()

    def test_pick_of_two_rows_rejected(self, patched_session: Session) -> None:
        from sqlalchemy.exc import IntegrityError

        ev = _make_event(patched_session)
        sta = add_station(patched_session)
        seis = _make_seismogram(patched_session, ev, sta)
        other = AimbatPhase(
            event=ev, name="S", parameters=default_phase_parameters("S")
        )
        patched_session.add(other)
        patched_session.commit()

        patched_session.add(
            AimbatSeismogramParameters(
                seismogram=seis, phase=other, pick=seis.phase_rows[0].pick
            )
        )
        with pytest.raises(IntegrityError):
            patched_session.flush()

    def test_second_seismogram_quality_rejected(self, patched_session: Session) -> None:
        from sqlalchemy.exc import IntegrityError

        ev = _make_event(patched_session)
        sta = add_station(patched_session)
        seis = _make_seismogram(patched_session, ev, sta)
        row = seis.phase_rows[0]
        patched_session.add(AimbatSeismogramQuality(parameters=row, iccs_cc=0.8))
        patched_session.commit()

        patched_session.add(AimbatSeismogramQuality(parameters=row, iccs_cc=0.5))
        with pytest.raises(IntegrityError):
            patched_session.flush()

    def test_second_phase_parameters_rejected(self, patched_session: Session) -> None:
        from sqlalchemy.exc import IntegrityError

        ev = _make_event(patched_session)
        patched_session.commit()

        second = default_phase_parameters("P")
        second.phase_id = ev.phases[0].id
        patched_session.add(second)
        with pytest.raises(IntegrityError):
            patched_session.flush()

    def test_second_phase_of_same_name_rejected(self, patched_session: Session) -> None:
        from sqlalchemy.exc import IntegrityError

        ev = _make_event(patched_session)
        patched_session.commit()

        patched_session.add(
            AimbatPhase(event=ev, name="P", parameters=default_phase_parameters("P"))
        )
        with pytest.raises(IntegrityError):
            patched_session.flush()

    def test_second_data_source_rejected(self, patched_session: Session) -> None:
        from sqlalchemy.exc import IntegrityError

        ev = _make_event(patched_session)
        sta = add_station(patched_session)
        seis = _make_seismogram(patched_session, ev, sta)
        patched_session.commit()

        patched_session.add(
            AimbatDataSource(
                sourcename="/tmp/other.sac",
                datatype=DataType.SAC,
                seismogram_id=seis.id,
            )
        )
        with pytest.raises(IntegrityError):
            patched_session.flush()


# ===================================================================
# Count column_property / TYPE_CHECKING sync
# ===================================================================


class TestCountColumnPropertiesMatchTypeCheckingStubs:
    """`AimbatEvent`/`AimbatStation`/`AimbatSnapshot` redeclare their count
    `column_property` attributes under `if TYPE_CHECKING` (with dummy int
    defaults) purely so type checkers see them; the real values are assigned
    via `column_property(...)` further down the module. Nothing keeps the two
    in sync - this pins the actual mapped `column_property` names per model
    so an edit to one without the other fails a test instead of drifting
    silently.
    """

    @pytest.mark.parametrize(
        "model, expected_count_attrs",
        [
            (
                AimbatEvent,
                {"seismogram_count", "site_count", "phase_count", "snapshot_count"},
            ),
            (AimbatPhase, {"snapshot_count"}),
            (AimbatStation, {"seismogram_count", "event_count"}),
            (
                AimbatSnapshot,
                {
                    "seismogram_count",
                    "selected_seismogram_count",
                    "flipped_seismogram_count",
                },
            ),
        ],
    )
    def test_mapped_column_properties_match_expected(
        self,
        model: type[SQLModel],
        expected_count_attrs: set[str],
    ) -> None:
        from sqlalchemy import inspect
        from sqlalchemy.orm import ColumnProperty

        mapper = inspect(model)
        assert mapper is not None
        table_column_names = set(model.__table__.columns.keys())  # type: ignore[attr-defined]
        derived_column_properties = {
            prop.key
            for prop in mapper.iterate_properties
            if isinstance(prop, ColumnProperty) and prop.key not in table_column_names
        }
        assert derived_column_properties == expected_count_attrs

    def test_counts_are_left_out_of_an_ordinary_select(
        self, patched_session: Session
    ) -> None:
        """Verifies a plain `select` of an event carries no count subquery.

        Regression test: the counts used to be attached to every `SELECT`
        of the owning model, so the processing paths that load an event to
        run ICCS paid for correlated subqueries they never read.
        """
        _make_event(patched_session)
        statements = _record_statements(
            patched_session,
            lambda: patched_session.exec(select(AimbatEvent)).all(),
        )
        assert statements, "expected the select itself to be recorded"
        assert not any("count(" in s.lower() for s in statements)

    def test_undefer_counts_loads_them_in_the_same_query(
        self, patched_session: Session
    ) -> None:
        """Verifies the opt-in brings the counts back into the main query."""
        from aimbat.models import undefer_counts

        _make_event(patched_session)
        statements = _record_statements(
            patched_session,
            lambda: patched_session.exec(
                select(AimbatEvent).options(*undefer_counts(AimbatEvent))
            ).all(),
        )
        assert len(statements) == 1
        assert statements[0].lower().count("count(") == 4

    def test_second_event_quality_rejected(self, patched_session: Session) -> None:
        from sqlalchemy.exc import IntegrityError

        ev = _make_event(patched_session)
        patched_session.add(
            AimbatPhaseQuality(phase=ev.phases[0], mccc_rmse=Timedelta(milliseconds=1))
        )
        patched_session.commit()

        patched_session.add(
            AimbatPhaseQuality(phase=ev.phases[0], mccc_rmse=Timedelta(milliseconds=2))
        )
        with pytest.raises(IntegrityError):
            patched_session.flush()
