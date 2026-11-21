"""Integration tests for actions on one of several phases of an event."""

import uuid
from dataclasses import dataclass

import pytest
from pandas import Timedelta
from sqlalchemy import Engine
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, col, select

from aimbat import actions
from aimbat.core._validity import Validity
from aimbat.models import (
    AimbatEvent,
    AimbatPhase,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    AimbatSnapshot,
)
from aimbat.types import PhaseParameter, SeismogramParameter

from testsupport.project import add_phase_from_picks, phase_state


@dataclass(frozen=True)
class _Phases:
    p: uuid.UUID
    pkp: uuid.UUID
    left_out: uuid.UUID
    """The seismogram with a P row but no PKP row."""


@pytest.fixture
def phases(loaded_engine: Engine) -> _Phases:
    """Add a PKP phase to all but one seismogram of the first event."""
    with Session(loaded_engine) as session:
        event = session.exec(
            select(AimbatEvent).order_by(col(AimbatEvent.time))
        ).first()
        assert event is not None
        (p,) = event.phases
        seismograms = sorted(event.seismograms, key=lambda s: str(s.id))
        add_phase_from_picks(session, seismograms[1:], "PKP")
        session.commit()
        pkp = session.exec(
            select(AimbatPhase)
            .where(AimbatPhase.event_id == event.id)
            .where(AimbatPhase.name == "PKP")
        ).one()
        return _Phases(p=p.id, pkp=pkp.id, left_out=seismograms[0].id)


def _seismograms_of(engine: Engine, phase_id: uuid.UUID) -> list[uuid.UUID]:
    with Session(engine) as session:
        return sorted(
            session.exec(
                select(AimbatSeismogramParameters.seismogram_id).where(
                    AimbatSeismogramParameters.phase_id == phase_id
                )
            ).all(),
            key=str,
        )


class TestIsolation:
    """Processing one phase leaves the other phases of the event untouched."""

    def test_alignment_and_snapshot(
        self, loaded_engine: Engine, phases: _Phases
    ) -> None:
        before = phase_state(loaded_engine, phases.pkp)

        actions.run_iccs(phases.p, autoflip=True, autoselect=True)
        actions.run_mccc(phases.p)
        actions.create_snapshot(phases.p, "P only")

        assert phase_state(loaded_engine, phases.pkp) == before
        with Session(loaded_engine) as session:
            assert Validity.read(session, phases.p).mccc(phases.p)

    def test_parameter_changes(self, loaded_engine: Engine, phases: _Phases) -> None:
        before = phase_state(loaded_engine, phases.pkp)
        shared = _seismograms_of(loaded_engine, phases.pkp)

        actions.set_phase_parameters(phases.p, {PhaseParameter.MIN_CC: 0.2})
        actions.set_seismogram_parameters(
            phases.p, shared, {SeismogramParameter.FLIP: True}
        )
        with Session(loaded_engine) as session:
            picks = {
                row.seismogram_id: row.initial_pick + Timedelta(seconds=0.5)
                for row in session.get_one(AimbatPhase, phases.p).seismogram_parameters
            }
        actions.set_refined_picks(phases.p, picks)
        actions.reset_seismogram_parameters(phases.p, shared[:1])

        assert phase_state(loaded_engine, phases.pkp) == before

    def test_seismogram_without_a_row_is_refused(
        self, loaded_engine: Engine, phases: _Phases
    ) -> None:
        before = phase_state(loaded_engine, phases.pkp)

        with pytest.raises(NoResultFound, match=str(phases.left_out)):
            actions.set_seismogram_parameters(
                phases.pkp, [phases.left_out], {SeismogramParameter.FLIP: True}
            )

        assert phase_state(loaded_engine, phases.pkp) == before


class TestRollbackKeepsRowsAddedSince:
    """A row created after a snapshot keeps its parameters on rollback."""

    def test_row_added_since(self, loaded_engine: Engine, phases: _Phases) -> None:
        actions.run_mccc(phases.pkp)
        actions.create_snapshot(phases.pkp, "before")
        with Session(loaded_engine) as session:
            snapshot_id = session.exec(
                select(AimbatSnapshot.id).where(AimbatSnapshot.phase_id == phases.pkp)
            ).one()
            add_phase_from_picks(
                session, [session.get_one(AimbatSeismogram, phases.left_out)], "PKP"
            )
            session.commit()
        actions.set_seismogram_parameters(
            phases.pkp, [phases.left_out], {SeismogramParameter.FLIP: True}
        )

        result = actions.rollback_to_snapshot(snapshot_id)

        assert result.added_since == (phases.left_out,)
        with Session(loaded_engine) as session:
            row = session.exec(
                select(AimbatSeismogramParameters)
                .where(AimbatSeismogramParameters.phase_id == phases.pkp)
                .where(AimbatSeismogramParameters.seismogram_id == phases.left_out)
            ).one()
            assert row.flip is True
            # The selected new row changes the stack but took no part in the
            # MCCC run.
            validity = Validity.read(session, phases.pkp)
            assert validity.mccc(phases.pkp)
            assert not validity.iccs_cc(row.id)

    def test_nothing_added(self, loaded_engine: Engine, phases: _Phases) -> None:
        actions.create_snapshot(phases.pkp, "before")
        with Session(loaded_engine) as session:
            snapshot_id = session.exec(
                select(AimbatSnapshot.id).where(AimbatSnapshot.phase_id == phases.pkp)
            ).one()

        assert actions.rollback_to_snapshot(snapshot_id).added_since == ()
