"""Integration tests for actions on real data with two labelled phases.

testkit's multi-phase data are one deep event recorded with labelled P (`t0`)
and pP (`t5`) picks. One station, AV.AKRB, has no pP pick.
"""

import uuid
from pathlib import Path
from typing import Any

import pytest
from pandas import Timedelta, Timestamp
from sqlalchemy import Engine
from sqlmodel import Session, col, select

from pysmo.classes import SAC

from aimbat import actions
from aimbat.core._validity import Validity
from aimbat.io import DataType
from aimbat.models import AimbatPhase, AimbatSnapshot

from testsupport.project import phase_state, station_key

_PHASES = ("P", "pP")
_P_ONLY = "AV.AKRB"


def _phase_id(engine: Engine, name: str) -> uuid.UUID:
    with Session(engine) as session:
        return session.exec(
            select(AimbatPhase.id).where(col(AimbatPhase.name) == name)
        ).one()


def _members(engine: Engine, name: str) -> set[str]:
    """`NETWORK.STATION` of each seismogram the phase has a row for."""
    with Session(engine) as session:
        phase = session.get_one(AimbatPhase, _phase_id(engine, name))
        return {
            station_key(row.seismogram.station) for row in phase.seismogram_parameters
        }


def _state(engine: Engine, name: str) -> dict[str, Any]:
    return phase_state(engine, _phase_id(engine, name))


def _process(phase_id: uuid.UUID) -> None:
    actions.run_iccs(phase_id, autoflip=True, autoselect=True)
    actions.run_mccc(phase_id)


class TestImport:
    """Ingesting the files names each phase from the pick labels."""

    @pytest.fixture
    def imported(self, patched_engine: Engine, multi_phase_data: list[Path]) -> Engine:
        actions.add_data(multi_phase_data, DataType.SAC, engine=patched_engine)
        return patched_engine

    def test_phases_and_members(
        self, imported: Engine, multi_phase_data: list[Path]
    ) -> None:
        with Session(imported) as session:
            names = sorted(session.exec(select(AimbatPhase.name)).all())
        assert names == sorted(_PHASES)

        stations = {path.name.rsplit(".", 2)[0] for path in multi_phase_data}
        assert _members(imported, "P") == stations
        assert _members(imported, "pP") == stations - {_P_ONLY}

    def test_initial_picks_are_the_labelled_headers(
        self, imported: Engine, multi_phase_data: list[Path]
    ) -> None:
        expected: dict[tuple[str, str], Timestamp] = {}
        for path in multi_phase_data:
            sac = SAC.from_file(path)
            for name, time in (("P", sac.timestamps.t0), ("pP", sac.timestamps.t5)):
                if time is not None:
                    expected[(station_key(sac.station), name)] = time

        found: dict[tuple[str, str], Timestamp] = {}
        with Session(imported) as session:
            for phase in session.exec(select(AimbatPhase)).all():
                for row in phase.seismogram_parameters:
                    key = (station_key(row.seismogram.station), phase.name)
                    found[key] = row.initial_pick
        assert found.keys() == expected.keys()
        for key, pick in found.items():
            assert abs(pick - expected[key]) < Timedelta(milliseconds=1), key

    def test_each_phase_gets_a_baseline_snapshot(self, imported: Engine) -> None:
        for name in _PHASES:
            assert len(_state(imported, name)["snapshots"]) == 1


class TestProcessing:
    """ICCS and MCCC on one phase, with the other phase left alone."""

    @pytest.mark.parametrize(("name", "other"), [("P", "pP"), ("pP", "P")])
    def test_alignment_leaves_the_other_phase(
        self, multi_phase_engine: Engine, name: str, other: str
    ) -> None:
        before = _state(multi_phase_engine, other)
        phase_id = _phase_id(multi_phase_engine, name)

        _process(phase_id)
        actions.create_snapshot(phase_id, f"{name} aligned")

        assert _state(multi_phase_engine, other) == before
        with Session(multi_phase_engine) as session:
            assert Validity.read(session, phase_id).mccc(phase_id)

    def test_residuals_agree_between_phases(self, multi_phase_engine: Engine) -> None:
        """P and pP share the receiver side, so each station's residuals agree."""
        residuals: dict[str, dict[str, Timedelta]] = {}
        for name in _PHASES:
            phase_id = _phase_id(multi_phase_engine, name)
            _process(phase_id)
            with Session(multi_phase_engine) as session:
                phase = session.get_one(AimbatPhase, phase_id)
                for row in phase.seismogram_parameters:
                    assert row.select and not row.flip
                    assert row.refined_pick is not None
                    residuals.setdefault(name, {})[
                        station_key(row.seismogram.station)
                    ] = row.refined_pick - row.initial_pick

        assert residuals["pP"].keys() == residuals["P"].keys() - {_P_ONLY}
        for key, pp in residuals["pP"].items():
            assert abs(pp) < Timedelta(seconds=2), key
            assert abs(pp - residuals["P"][key]) < Timedelta(seconds=0.5), key

    def test_rollback_restores_one_phase_only(self, multi_phase_engine: Engine) -> None:
        p, pp = (_phase_id(multi_phase_engine, name) for name in _PHASES)
        actions.create_snapshot(p, "baseline")
        with Session(multi_phase_engine) as session:
            (baseline,) = session.exec(
                select(AimbatSnapshot.id).where(AimbatSnapshot.phase_id == p)
            ).all()
        baseline_rows = _state(multi_phase_engine, "P")["rows"]

        _process(p)
        _process(pp)
        aligned_pp = _state(multi_phase_engine, "pP")
        assert _state(multi_phase_engine, "P")["rows"] != baseline_rows

        actions.rollback_to_snapshot(baseline)

        assert _state(multi_phase_engine, "P")["rows"] == baseline_rows
        assert _state(multi_phase_engine, "pP") == aligned_pp
