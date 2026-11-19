"""Integration tests for looking up phases and setting their parameters."""

import uuid

import pytest
from pandas import Timedelta, Timestamp
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, select

from aimbat import settings
from aimbat.core import (
    AmbiguousPhaseError,
    IccsValidationError,
    default_phase_parameters,
    dump_phase_parameter_table,
    dump_phase_quality_table,
    dump_phase_table,
    get_completed_phases,
    get_phase_quality,
    get_phases,
    rename_phase,
    resolve_phase,
    set_phase_parameter,
    set_phase_parameters,
    toggle_phase_completed,
)
from aimbat.core import _iccs as core_iccs
from aimbat.core._validity import compute_digests
from aimbat.models import (
    AimbatEvent,
    AimbatPhase,
    AimbatPhaseParameters,
    AimbatPhaseQuality,
    AimbatPick,
    PickOrigin,
)
from aimbat.models._parameters import PHASE_PARAMETER_SPECS
from aimbat.types import PhaseParameter
from aimbat.utils import format_validation_error


def _event(session: Session, *names: str, minute: int = 0) -> AimbatEvent:
    event = AimbatEvent(
        time=Timestamp("2020-01-01T00:00:00", tz="UTC") + Timedelta(minutes=minute),
        latitude=0.0,
        longitude=0.0,
    )
    for name in names:
        event.phases.append(
            AimbatPhase(name=name, parameters=default_phase_parameters(name))
        )
    session.add(event)
    session.commit()
    return event


class TestResolvePhase:
    """Tests for `resolve_phase`."""

    def test_only_phase(self, engine: Engine) -> None:
        with Session(engine) as session:
            event = _event(session, "P")
            assert resolve_phase(session, event.id).name == "P"

    def test_by_name(self, engine: Engine) -> None:
        with Session(engine) as session:
            event = _event(session, "P", "PKP")
            assert resolve_phase(session, event.id, "PKP").name == "PKP"

    def test_unknown_name_lists_phases(self, engine: Engine) -> None:
        with Session(engine) as session:
            event = _event(session, "S", "P")
            with pytest.raises(NoResultFound, match="Its phases: P, S"):
                resolve_phase(session, event.id, "PKP")

    def test_several_phases_without_name(self, engine: Engine) -> None:
        with Session(engine) as session:
            event = _event(session, "S", "P")
            with pytest.raises(AmbiguousPhaseError) as raised:
                resolve_phase(session, event.id)
            assert raised.value.names == ("P", "S")

    def test_no_phase(self, engine: Engine) -> None:
        with Session(engine) as session:
            event = _event(session)
            with pytest.raises(NoResultFound, match="no phases"):
                resolve_phase(session, event.id)

    def test_unknown_event(self, engine: Engine) -> None:
        with Session(engine) as session:
            with pytest.raises(NoResultFound, match="No event"):
                resolve_phase(session, uuid.uuid4())


class TestDefaultPhaseParameters:
    """Tests for `default_phase_parameters`."""

    @pytest.mark.parametrize("name", ["P", "PKIKP"])
    def test_settings_defaults(self, name: str) -> None:
        parameters = default_phase_parameters(name)
        assert parameters.window_pre == settings.window_pre
        assert parameters.window_post == settings.window_post
        assert parameters.min_cc == settings.min_cc
        assert parameters.completed is False

    def test_every_parameter_from_settings(self) -> None:
        parameters = default_phase_parameters("P")
        for name, spec in PHASE_PARAMETER_SPECS.items():
            if not spec.bookkeeping:
                assert getattr(parameters, name) == getattr(settings, name), name

    def test_current_settings_apply(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "window_post", Timedelta(seconds=42))
        monkeypatch.setattr(settings, "min_cc", 0.33)
        parameters = default_phase_parameters("P")
        assert parameters.window_post == Timedelta(seconds=42)
        assert parameters.min_cc == 0.33

    def test_new_instance_each_call(self, engine: Engine) -> None:
        with Session(engine) as session:
            event = _event(session)
            event.phases.append(
                AimbatPhase(name="P", parameters=default_phase_parameters("P"))
            )
            event.phases.append(
                AimbatPhase(name="S", parameters=default_phase_parameters("S"))
            )
            session.commit()
            assert len(session.exec(select(AimbatPhaseParameters)).all()) == 2


# ===================================================================
# Phase parameters
# ===================================================================


class TestSetPhaseParameter:
    """Tests for writing parameter values to a phase."""

    def test_set_timedelta_parameter(self, loaded_session: Session) -> None:
        """Verifies that a Timedelta parameter is persisted correctly.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        new_value = Timedelta(seconds=20)
        set_phase_parameter(
            loaded_session, event.phases[0].id, PhaseParameter.WINDOW_POST, new_value
        )
        assert event.phases[0].parameters.window_post == new_value

    def test_set_float_parameter(self, loaded_session: Session) -> None:
        """Verifies that a float parameter is persisted correctly.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        new_value = 0.75
        set_phase_parameter(
            loaded_session, event.phases[0].id, PhaseParameter.MIN_CC, new_value
        )
        assert event.phases[0].parameters.min_cc == new_value

    def test_set_bool_parameter(self, loaded_session: Session) -> None:
        """Verifies that a bool parameter is persisted correctly.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        set_phase_parameter(
            loaded_session, event.phases[0].id, PhaseParameter.COMPLETED, True
        )
        assert event.phases[0].parameters.completed is True

    def test_set_parameter_with_validate_iccs(self, loaded_session: Session) -> None:
        """Verifies that validate_iccs=True triggers ICCS validation.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None

        # Test valid change
        new_value = Timedelta(seconds=1.5)
        set_phase_parameter(
            loaded_session,
            event.phases[0].id,
            PhaseParameter.WINDOW_POST,
            new_value,
            validate_iccs=True,
        )
        assert event.phases[0].parameters.window_post == new_value

        # Test invalid change (e.g., window that would result in no data)
        # Very large window might fail construction if it exceeds data bounds
        with pytest.raises(IccsValidationError, match="ICCS validation failed"):
            set_phase_parameter(
                loaded_session,
                event.phases[0].id,
                PhaseParameter.WINDOW_POST,
                Timedelta(seconds=10000),
                validate_iccs=True,
            )
        assert event.phases[0].parameters.window_post == new_value

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
            set_phase_parameter(
                loaded_session,
                event.phases[0].id,
                PhaseParameter.WINDOW_POST,
                Timedelta(seconds=2),
                validate_iccs=True,
            )

    @pytest.mark.parametrize("commit", [False, True])
    def test_change_is_kept_only_if_the_caller_commits(
        self, loaded_engine: Engine, commit: bool
    ) -> None:
        """`set_phase_parameter` leaves committing to the caller."""
        with Session(loaded_engine) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            phase_id, before = (
                event.phases[0].id,
                event.phases[0].parameters.window_post,
            )
            new_value = Timedelta(seconds=20)
            set_phase_parameter(
                session, phase_id, PhaseParameter.WINDOW_POST, new_value
            )
            if commit:
                session.commit()

        with Session(loaded_engine) as session:
            phase = session.get(AimbatPhase, phase_id)
            assert phase is not None
            expected = new_value if commit else before
            assert phase.parameters.window_post == expected

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
        set_phase_parameters(
            loaded_session,
            event.phases[0].id,
            {
                PhaseParameter.BANDPASS_FMIN: 0.5,
                PhaseParameter.BANDPASS_FMAX: 1.0,
            },
        )

        with pytest.raises(ValidationError) as excinfo:
            set_phase_parameter(
                loaded_session, event.phases[0].id, PhaseParameter.BANDPASS_FMIN, 1.5
            )
        message = format_validation_error(excinfo.value)
        assert "bandpass_fmax (1 Hz)" in message
        assert "bandpass_fmin (1.5 Hz)" in message
        assert "raise bandpass_fmax before bandpass_fmin" in message

        # The order the message gives: widen first, then narrow.
        set_phase_parameter(
            loaded_session, event.phases[0].id, PhaseParameter.BANDPASS_FMAX, 2.0
        )
        set_phase_parameter(
            loaded_session, event.phases[0].id, PhaseParameter.BANDPASS_FMIN, 1.5
        )
        assert event.phases[0].parameters.bandpass_fmin == 1.5
        assert event.phases[0].parameters.bandpass_fmax == 2.0


class TestSetPhaseParameters:
    """Tests for the batched multi-parameter writer."""

    def test_batch_crosses_the_fmax_over_fmin_boundary(
        self, loaded_session: Session
    ) -> None:
        """A new fmin above the old fmax fails one field at a time but is fine
        as a batch (validated against the merged state)."""
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        event.phases[0].parameters.bandpass_fmin = 0.5
        event.phases[0].parameters.bandpass_fmax = 2.0
        loaded_session.add(event.phases[0].parameters)
        loaded_session.commit()

        # One field at a time: raising fmin to 5 fails against the old fmax=2.
        with pytest.raises(ValueError):
            set_phase_parameter(
                loaded_session, event.phases[0].id, PhaseParameter.BANDPASS_FMIN, 5.0
            )

        # As a batch it validates against fmin=5, fmax=10 together.
        set_phase_parameters(
            loaded_session,
            event.phases[0].id,
            {
                PhaseParameter.BANDPASS_FMIN: 5.0,
                PhaseParameter.BANDPASS_FMAX: 10.0,
            },
        )
        assert event.phases[0].parameters.bandpass_fmin == 5.0
        assert event.phases[0].parameters.bandpass_fmax == 10.0

    def test_empty_mapping_is_a_noop(self, loaded_session: Session) -> None:
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        before = compute_digests(loaded_session, event.phases[0].id)[
            event.phases[0].id
        ].tracked
        set_phase_parameters(loaded_session, event.phases[0].id, {})
        assert (
            compute_digests(loaded_session, event.phases[0].id)[
                event.phases[0].id
            ].tracked
            == before
        )

    def test_unknown_phase_raises_even_with_empty_mapping(
        self, loaded_session: Session
    ) -> None:
        with pytest.raises(NoResultFound):
            set_phase_parameters(loaded_session, uuid.uuid4(), {})


class TestTogglePhaseCompleted:
    """Tests for flipping a phase's `completed` flag."""

    def test_toggle_flips_false_to_true(self, loaded_session: Session) -> None:
        """Verifies the flag flips and the new value is returned.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        assert event.phases[0].parameters.completed is False

        result = toggle_phase_completed(loaded_session, event.phases[0].id)

        assert result is True
        assert event.phases[0].parameters.completed is True

    def test_toggle_twice_returns_to_original(self, loaded_session: Session) -> None:
        """Verifies a second toggle flips the flag back.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None

        toggle_phase_completed(loaded_session, event.phases[0].id)
        result = toggle_phase_completed(loaded_session, event.phases[0].id)

        assert result is False
        assert event.phases[0].parameters.completed is False

    def test_toggle_not_found_raises(self, loaded_session: Session) -> None:
        """Verifies a missing phase ID raises NoResultFound.

        Args:
            loaded_session: The database session.
        """
        with pytest.raises(NoResultFound):
            toggle_phase_completed(loaded_session, uuid.uuid4())

    def test_toggle_does_not_clear_mccc_quality(self, loaded_session: Session) -> None:
        """Verifies toggling `completed` leaves MCCC quality untouched.

        `completed` is deliberately excluded from both parameter hashes used
        for snapshot matching (see `compute_iccs_hash` / `compute_mccc_hash`),
        so this must not go through `set_phase_parameter`'s
        snapshot-sync/MCCC-invalidation path the way real processing
        parameters do.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        rmse = Timedelta(milliseconds=1)
        loaded_session.add(
            AimbatPhaseQuality(
                id=uuid.uuid4(), phase_id=event.phases[0].id, mccc_rmse=rmse
            )
        )
        loaded_session.commit()

        toggle_phase_completed(loaded_session, event.phases[0].id)

        loaded_session.refresh(event)
        assert event.phases[0].quality is not None
        assert event.phases[0].quality.mccc_rmse == rmse

    def test_toggle_leaves_the_tracked_digest_unchanged(
        self, loaded_session: Session
    ) -> None:
        """`completed` is bookkeeping, so toggling it moves no digest and does
        not repaint or rebuild anything."""
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        before = compute_digests(loaded_session, event.phases[0].id)[event.phases[0].id]

        toggle_phase_completed(loaded_session, event.phases[0].id)

        after = compute_digests(loaded_session, event.phases[0].id)[event.phases[0].id]
        assert (after.tracked, after.instance) == (before.tracked, before.instance)


# ===================================================================
# Listing, quality and renaming
# ===================================================================


class TestGetPhases:
    """Tests for `get_phases`."""

    def test_event_and_name_filters(self, engine: Engine) -> None:
        with Session(engine) as session:
            first = _event(session, "S", "P")
            second = _event(session, "P", minute=1)
            assert [p.name for p in get_phases(session, first.id)] == ["P", "S"]
            assert {p.event_id for p in get_phases(session, name="P")} == {
                first.id,
                second.id,
            }
            assert len(get_phases(session)) == 3


class TestGetCompletedPhases:
    """Tests for `get_completed_phases`."""

    def test_only_completed_phases(self, engine: Engine) -> None:
        with Session(engine) as session:
            event = _event(session, "P", "S")
            event.phases[0].parameters.completed = True
            session.commit()
            assert [p.id for p in get_completed_phases(session)] == [event.phases[0].id]


class TestGetPhaseQuality:
    """Tests for `get_phase_quality`."""

    def test_counts_the_rows_of_the_phase(self, loaded_session: Session) -> None:
        phase = loaded_session.exec(select(AimbatPhase)).first()
        assert phase is not None
        stats = get_phase_quality(loaded_session, phase.id)
        assert stats.phase_id == phase.id
        assert stats.phase_name == phase.name
        assert stats.event_id == phase.event_id
        assert stats.count == len(phase.seismogram_parameters)

    def test_unknown_phase(self, loaded_session: Session) -> None:
        with pytest.raises(NoResultFound):
            get_phase_quality(loaded_session, uuid.uuid4())


class TestRenamePhase:
    """Tests for `rename_phase`."""

    def test_renames_the_phase_and_the_picks_of_its_event(self, engine: Engine) -> None:
        with Session(engine) as session:
            event = _event(session, "P")
            other = _event(session, "P", minute=1)
            time = Timestamp("2020-01-01T00:10:00", tz="UTC")
            ours = AimbatPick(
                time=time, phase_name="P", origin=PickOrigin.MANUAL, event_id=event.id
            )
            theirs = AimbatPick(
                time=time, phase_name="P", origin=PickOrigin.MANUAL, event_id=other.id
            )
            session.add_all([ours, theirs])
            session.commit()

            rename_phase(session, event.phases[0].id, "Pdiff")
            session.commit()

            assert event.phases[0].name == "Pdiff"
            assert ours.phase_name == "Pdiff"
            assert theirs.phase_name == "P"
            assert other.phases[0].name == "P"

    def test_name_taken_by_another_phase(self, engine: Engine) -> None:
        with Session(engine) as session:
            event = _event(session, "P", "S")
            with pytest.raises(ValueError, match="already has a phase 'S'"):
                rename_phase(session, event.phases[0].id, "S")

    def test_invalid_name(self, engine: Engine) -> None:
        with Session(engine) as session:
            event = _event(session, "P")
            with pytest.raises(ValueError, match="whitespace"):
                rename_phase(session, event.phases[0].id, "P K P")

    def test_unknown_phase(self, engine: Engine) -> None:
        with Session(engine) as session:
            with pytest.raises(NoResultFound):
                rename_phase(session, uuid.uuid4(), "P")


class TestDumpPhaseTables:
    """Tests for `dump_phase_table`, `dump_phase_parameter_table` and `dump_phase_quality_table`."""

    def test_read_model(self, loaded_session: Session) -> None:
        result = dump_phase_table(loaded_session, from_read_model=True)
        assert len(result) == len(loaded_session.exec(select(AimbatPhase)).all())
        assert {"name", "seismogram_count", "mccc", "event_id"} <= result[0].keys()

    def test_name_filter(self, engine: Engine) -> None:
        with Session(engine) as session:
            _event(session, "P", "S")
            _event(session, "P", minute=1)
            result = dump_phase_table(session, from_read_model=True, name="S")
            assert [row["name"] for row in result] == ["S"]

    def test_parameters_carry_the_phase_name(self, loaded_session: Session) -> None:
        result = dump_phase_parameter_table(loaded_session)
        assert len(result) > 0
        assert {"min_cc", "window_pre", "phase_id", "phase_name"} <= result[0].keys()
        keys = list(result[0])
        assert keys.index("phase_name") == keys.index("phase_id") + 1

    def test_parameters_with_alias(self, loaded_session: Session) -> None:
        result = dump_phase_parameter_table(loaded_session, by_alias=True)
        assert {"minCc", "windowPre", "phaseId", "phaseName"} <= result[0].keys()
        assert "min_cc" not in result[0]

    def test_quality_per_phase(self, loaded_session: Session) -> None:
        result = dump_phase_quality_table(loaded_session)
        assert len(result) == len(loaded_session.exec(select(AimbatPhase)).all())
        assert {"phase_id", "phase_name", "event_id"} <= result[0].keys()
        assert "station_id" not in result[0]
