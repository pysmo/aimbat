"""Integration tests for actions on one of several phases of an event."""

import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from pandas import Timedelta
from sqlalchemy import Engine
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, col, select

from aimbat import actions
from aimbat.core import promote_picks, store_picks
from aimbat.core._validity import Validity
from aimbat.io import DataType, SourcePick
from aimbat.models import (
    AimbatEvent,
    AimbatPhase,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    AimbatSnapshot,
)
from aimbat.types import PhaseParameter, SeismogramParameter


@dataclass(frozen=True)
class _Phases:
    p: uuid.UUID
    pkp: uuid.UUID
    left_out: uuid.UUID
    """The seismogram with a P row but no PKP row."""


def _add_picks(
    session: Session, seismograms: list[AimbatSeismogram], name: str
) -> None:
    """Store and promote a pick named `name` one second after each seismogram's
    first initial pick."""
    picks = []
    for seismogram in seismograms:
        picks += store_picks(
            session,
            [
                SourcePick(
                    seismogram.phase_rows[0].initial_pick + Timedelta(seconds=1),
                    "t9",
                    label=name,
                )
            ],
            source_name=f"{name}-{seismogram.id}",
            source_type=DataType.SAC,
            source_seismogram=seismogram,
        ).stored
    promote_picks(session, picks)
    session.commit()


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
        _add_picks(session, seismograms[1:], "PKP")
        pkp = session.exec(
            select(AimbatPhase)
            .where(AimbatPhase.event_id == event.id)
            .where(AimbatPhase.name == "PKP")
        ).one()
        return _Phases(p=p.id, pkp=pkp.id, left_out=seismograms[0].id)


def _state(engine: Engine, phase_id: uuid.UUID) -> dict[str, Any]:
    """Everything stored for a phase: parameters, rows, quality and snapshots."""
    with Session(engine) as session:
        phase = session.get_one(AimbatPhase, phase_id)
        rows = sorted(phase.seismogram_parameters, key=lambda r: str(r.id))
        return {
            "parameters": phase.parameters.model_dump(),
            "quality": None if phase.quality is None else phase.quality.model_dump(),
            "rows": [row.model_dump() for row in rows],
            "row_quality": [
                None if row.quality is None else row.quality.model_dump()
                for row in rows
            ],
            "snapshots": sorted(
                str(s)
                for s in session.exec(
                    select(AimbatSnapshot.id).where(AimbatSnapshot.phase_id == phase_id)
                ).all()
            ),
        }


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
        before = _state(loaded_engine, phases.pkp)

        actions.run_iccs(phases.p, autoflip=True, autoselect=True)
        actions.run_mccc(phases.p)
        actions.create_snapshot(phases.p, "P only")

        assert _state(loaded_engine, phases.pkp) == before
        with Session(loaded_engine) as session:
            assert Validity.read(session, phases.p).mccc(phases.p)

    def test_parameter_changes(self, loaded_engine: Engine, phases: _Phases) -> None:
        before = _state(loaded_engine, phases.pkp)
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

        assert _state(loaded_engine, phases.pkp) == before

    def test_seismogram_without_a_row_is_refused(
        self, loaded_engine: Engine, phases: _Phases
    ) -> None:
        before = _state(loaded_engine, phases.pkp)

        with pytest.raises(NoResultFound, match=str(phases.left_out)):
            actions.set_seismogram_parameters(
                phases.pkp, [phases.left_out], {SeismogramParameter.FLIP: True}
            )

        assert _state(loaded_engine, phases.pkp) == before


class TestRollbackKeepsRowsAddedSince:
    """A row created after a snapshot keeps its parameters on rollback."""

    def test_row_added_since(self, loaded_engine: Engine, phases: _Phases) -> None:
        actions.run_mccc(phases.pkp)
        actions.create_snapshot(phases.pkp, "before")
        with Session(loaded_engine) as session:
            snapshot_id = session.exec(
                select(AimbatSnapshot.id).where(AimbatSnapshot.phase_id == phases.pkp)
            ).one()
            _add_picks(
                session, [session.get_one(AimbatSeismogram, phases.left_out)], "PKP"
            )
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
