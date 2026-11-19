"""Functions in `aimbat.core` that change the project leave committing to the caller."""

from collections.abc import Callable
from pathlib import Path
from uuid import UUID

import pytest
from pandas import Timedelta
from sqlalchemy.orm import Session as SASession
from sqlmodel import Session, select

from aimbat import core
from aimbat.io import DataType
from aimbat.models import AimbatEvent, AimbatSeismogram, AimbatSnapshot, AimbatStation
from aimbat.types import PhaseParameter, SeismogramParameter

type _Case = Callable[[Session], Callable[[], object]]
"""Prepares a call on a session and returns it. Preparation may commit."""


def _event(session: Session) -> AimbatEvent:
    event = session.exec(select(AimbatEvent)).first()
    assert event is not None
    return event


def _seismogram(session: Session) -> AimbatSeismogram:
    seismogram = session.exec(select(AimbatSeismogram)).first()
    assert seismogram is not None
    return seismogram


def _phase_id(session: Session) -> UUID:
    return _seismogram(session).phase_rows[0].phase_id


def _snapshot_id(session: Session) -> UUID:
    core.create_snapshot(session, _phase_id(session))
    session.commit()
    return session.exec(select(AimbatSnapshot.id)).one()


def _rollback(session: Session) -> Callable[[], object]:
    snapshot_id = _snapshot_id(session)
    return lambda: core.rollback_to_snapshot(session, snapshot_id)


def _delete_snapshot(session: Session) -> Callable[[], object]:
    snapshot_id = _snapshot_id(session)
    return lambda: core.delete_snapshot(session, snapshot_id)


def _run_iccs(session: Session) -> Callable[[], object]:
    event = _event(session)
    bound = core.create_iccs_instance(session, event.phases[0].id)
    session.commit()
    return lambda: core.run_iccs(session, event.phases[0].id, bound.iccs, True, True)


def _run_mccc(session: Session) -> Callable[[], object]:
    event = _event(session)
    bound = core.create_iccs_instance(session, event.phases[0].id)
    session.commit()
    return lambda: core.run_mccc(session, event.phases[0].id, bound.iccs, False)


def _prune(session: Session) -> Callable[[], object]:
    Path(_seismogram(session).datasource.sourcename).unlink()
    return lambda: core.prune_project(session, "all")


def _station_id(session: Session) -> UUID:
    station = session.exec(select(AimbatStation)).first()
    assert station is not None
    return station.id


_CASES: dict[str, _Case] = {
    "delete_event": lambda s: lambda: core.delete_event(s, _event(s).id),
    "toggle_phase_completed": lambda s: (
        lambda: core.toggle_phase_completed(s, _phase_id(s))
    ),
    "set_phase_parameters": lambda s: (
        lambda: core.set_phase_parameters(s, _phase_id(s), {PhaseParameter.MIN_CC: 0.3})
    ),
    "save_note": lambda s: lambda: core.save_note(s, "event", _event(s).id, "note"),
    "delete_station": lambda s: lambda: core.delete_station(s, _station_id(s)),
    "delete_seismogram": lambda s: lambda: core.delete_seismogram(s, _seismogram(s).id),
    "set_seismogram_parameters": lambda s: (
        lambda: core.set_seismogram_parameters(
            s, _phase_id(s), [_seismogram(s).id], {SeismogramParameter.FLIP: True}
        )
    ),
    "set_refined_picks": lambda s: (
        lambda: core.set_refined_picks(
            s,
            _phase_id(s),
            {
                _seismogram(s).id: _seismogram(s).phase_rows[0].initial_pick
                + Timedelta(seconds=1)
            },
        )
    ),
    "reset_seismogram_parameters": lambda s: (
        lambda: core.reset_seismogram_parameters(s, _phase_id(s), _seismogram(s).id)
    ),
    "create_snapshot": lambda s: lambda: core.create_snapshot(s, _phase_id(s)),
    "rollback_to_snapshot": _rollback,
    "delete_snapshot": _delete_snapshot,
    "create_iccs_instance": lambda s: (
        lambda: core.create_iccs_instance(s, _phase_id(s))
    ),
    "run_iccs": _run_iccs,
    "run_mccc": _run_mccc,
    "prune_project": _prune,
}


def _forbid_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    def _commit(self: SASession) -> None:
        raise AssertionError("aimbat.core committed")

    monkeypatch.setattr(SASession, "commit", _commit)


@pytest.mark.parametrize("case", _CASES.values(), ids=_CASES.keys())
def test_does_not_commit(
    loaded_session: Session, monkeypatch: pytest.MonkeyPatch, case: _Case
) -> None:
    call = case(loaded_session)
    _forbid_commit(monkeypatch)

    call()


def test_add_data_does_not_commit(
    patched_session: Session,
    multi_event_data: list[Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _forbid_commit(monkeypatch)

    report = core.add_data_to_project(
        patched_session,
        multi_event_data,
        DataType.SAC,
        naming=core.PickNaming(unlabelled_as="P"),
    )
    assert report.promotion.rows
    core.create_snapshots_for_added_data(
        patched_session, {row.phase_id: 1 for row in report.promotion.rows}
    )
