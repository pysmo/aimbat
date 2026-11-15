"""Which derived values survive a parameter change.

Each case seeds live quality for one event, changes one parameter, and checks
what is still there afterwards. The tables below are the rules. Seeding and
observing each go through a single helper (`_seed`, `_observe`), so a change
of mechanism means porting those two functions and leaving the tables alone.

The intended rule is that a result stays valid while the inputs it was
computed from are unchanged. For the MCCC results those inputs are the window,
taper and bandpass, the MCCC parameters, and the pick and polarity of the
seismograms that took part in the run. Selection, `min_cc` and `completed` are
not among them.

Every change is made in the three situations that exist today, because they
do not always follow that rule. Each cell that departs from it is marked
"Deviates" and pins what happens today, not what should. All of them err
towards discarding a result that is still valid, never towards keeping a stale
one.

- `orm`: the attribute is assigned and the session committed, as the ICCS and
  MCCC write-back and `toggle_event_completed` do.
- `api`: through `set_event_parameter` or `set_seismogram_parameter`, with no
  snapshot holding the seeded results.
- `api_with_snapshot`: the same, with a snapshot of the seeded state to
  restore from.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, get_args

import pytest
from pandas import Timedelta
from sqlalchemy import Engine
from sqlmodel import Session, col, select

from aimbat.core import (
    create_snapshot,
    set_event_parameter,
    set_seismogram_parameter,
)
from aimbat.models import (
    AimbatEvent,
    AimbatEventQuality,
    AimbatSeismogram,
    AimbatSeismogramQuality,
    AimbatStation,
)
from aimbat.types import EventParameter, SeismogramParameter

type Situation = Literal["orm", "api", "api_with_snapshot"]
_SITUATIONS: tuple[Situation, ...] = get_args(Situation.__value__)

# What can survive a change.
_NOTHING: frozenset[str] = frozenset()
_OTHER_ICCS = frozenset({"other_iccs"})
_ICCS = frozenset({"target_iccs", "other_iccs"})
_MCCC = frozenset({"mccc"})
_EVERYTHING = _ICCS | _MCCC

# How the event can be marked by a change.
_UNMARKED: frozenset[str] = frozenset()
_MODIFIED = frozenset({"modified"})
_STACK_MODIFIED = frozenset({"modified", "stack_modified"})


@dataclass(frozen=True)
class Rule:
    """What survives a change in each situation, and how the event is marked."""

    orm: frozenset[str]
    api: frozenset[str]
    api_with_snapshot: frozenset[str]
    marks: frozenset[str]


def _same(survives: frozenset[str], marks: frozenset[str]) -> Rule:
    """A rule on which all three situations agree."""
    return Rule(survives, survives, survives, marks)


_CHANGES_THE_STACK = _same(_NOTHING, _STACK_MODIFIED)
_CHANGES_MCCC_ONLY = _same(_ICCS, _MODIFIED)

EVENT_RULES: dict[EventParameter, Rule] = {
    EventParameter.WINDOW_PRE: _CHANGES_THE_STACK,
    EventParameter.WINDOW_POST: _CHANGES_THE_STACK,
    EventParameter.RAMP_WIDTH: _CHANGES_THE_STACK,
    EventParameter.BANDPASS_APPLY: _CHANGES_THE_STACK,
    EventParameter.BANDPASS_FMIN: _CHANGES_THE_STACK,
    EventParameter.BANDPASS_FMAX: _CHANGES_THE_STACK,
    EventParameter.CORNERS: _CHANGES_THE_STACK,
    EventParameter.MCCC_DAMP: _CHANGES_MCCC_ONLY,
    EventParameter.MCCC_MIN_CC: _CHANGES_MCCC_ONLY,
    # Deviates (`api`): neither parameter affects a result, but the set
    # functions drop every MCCC result that no snapshot holds.
    EventParameter.MIN_CC: Rule(
        orm=_EVERYTHING, api=_ICCS, api_with_snapshot=_EVERYTHING, marks=_MODIFIED
    ),
    EventParameter.COMPLETED: Rule(
        orm=_EVERYTHING, api=_ICCS, api_with_snapshot=_EVERYTHING, marks=_UNMARKED
    ),
}

# Keyed by (parameter, target selected, target in the MCCC run).
#
# A pick or polarity change on a seismogram outside the stack leaves the other
# seismograms' `iccs_cc` alone.
_PICK_OR_POLARITY: dict[tuple[bool, bool], Rule] = {
    (True, True): _same(_NOTHING, _STACK_MODIFIED),
    # Deviates (`api`, `api_with_snapshot`): the seismogram was not in the
    # MCCC run, so the MCCC results should stay. The MCCC hash covers every
    # seismogram's pick and polarity, in the run or not.
    (True, False): Rule(
        orm=_MCCC, api=_NOTHING, api_with_snapshot=_NOTHING, marks=_STACK_MODIFIED
    ),
    (False, True): _same(_OTHER_ICCS, _STACK_MODIFIED),
    # Deviates (`api`, `api_with_snapshot`): as above.
    (False, False): Rule(
        orm=_OTHER_ICCS | _MCCC,
        api=_OTHER_ICCS,
        api_with_snapshot=_OTHER_ICCS,
        marks=_STACK_MODIFIED,
    ),
}
# Selection changes the stack, so no `iccs_cc` survives, but it is not an
# input to MCCC, so the MCCC results should always stay.
_SELECTION: dict[tuple[bool, bool], Rule] = {
    # Deviates (`orm`, `api`): the triggers drop the MCCC results when the
    # seismogram was in the run, and the set functions drop them unless a
    # snapshot holds them.
    (selected, True): Rule(
        orm=_NOTHING, api=_NOTHING, api_with_snapshot=_MCCC, marks=_STACK_MODIFIED
    )
    for selected in (True, False)
} | {
    # Deviates (`api`): dropped because no snapshot holds them.
    (selected, False): Rule(
        orm=_MCCC, api=_NOTHING, api_with_snapshot=_MCCC, marks=_STACK_MODIFIED
    )
    for selected in (True, False)
}

SEISMOGRAM_RULES: dict[tuple[SeismogramParameter, bool, bool], Rule] = {
    (name, *state): rule
    for name, rules in (
        (SeismogramParameter.FLIP, _PICK_OR_POLARITY),
        (SeismogramParameter.T1, _PICK_OR_POLARITY),
        (SeismogramParameter.SELECT, _SELECTION),
    )
    for state, rule in rules.items()
}


@dataclass(frozen=True)
class Seeded:
    """The event under test and the seismogram whose parameters change."""

    event_id: uuid.UUID
    target_id: uuid.UUID
    in_mccc: bool


def _seed(
    engine: Engine,
    situation: Situation,
    *,
    selected: bool = True,
    in_mccc: bool = True,
) -> Seeded:
    """Give one event a full set of live quality values.

    Args:
        engine: Engine of a project with data loaded.
        situation: Decides whether a snapshot of the seeded state is taken.
        selected: Whether the target seismogram is selected.
        in_mccc: Whether the target seismogram took part in the MCCC run that
            the seeded results stand for.
    """
    with Session(engine) as session:
        # Ordered so the same seismogram is the target on every run.
        target = session.exec(
            select(AimbatSeismogram)
            .join(AimbatEvent)
            .join(AimbatStation)
            .order_by(
                col(AimbatEvent.time),
                col(AimbatStation.network),
                col(AimbatStation.name),
            )
        ).first()
        assert target is not None
        event = target.event
        assert len(event.seismograms) >= 3
        target.parameters.select = selected
        session.commit()

        for seismogram in event.seismograms:
            quality = AimbatSeismogramQuality(seismogram_id=seismogram.id, iccs_cc=0.9)
            if in_mccc or seismogram.id != target.id:
                quality.mccc_cc_mean = 0.8
                quality.mccc_cc_std = 0.1
                quality.mccc_error = Timedelta(seconds=0.01)
            session.add(quality)
        session.add(
            AimbatEventQuality(event_id=event.id, mccc_rmse=Timedelta(seconds=0.02))
        )
        session.commit()
        if situation == "api_with_snapshot":
            create_snapshot(session, event)

        event.last_modified = None
        event.stack_modified = None
        session.commit()
        return Seeded(event_id=event.id, target_id=target.id, in_mccc=in_mccc)


def _observe(engine: Engine, seeded: Seeded) -> tuple[frozenset[str], frozenset[str]]:
    """Report what survived of the seeded state, and how the event is marked."""
    with Session(engine) as session:
        event = session.get_one(AimbatEvent, seeded.event_id)
        qualities = session.exec(
            select(AimbatSeismogramQuality).where(
                col(AimbatSeismogramQuality.seismogram_id).in_(
                    [seismogram.id for seismogram in event.seismograms]
                )
            )
        ).all()
        target = next(q for q in qualities if q.seismogram_id == seeded.target_id)
        others = [q for q in qualities if q.seismogram_id != seeded.target_id]

        # Guards on what the rules take for granted: the other seismograms
        # are treated alike, and the MCCC results stand or fall together.
        other_iccs = {q.iccs_cc is not None for q in others}
        assert len(other_iccs) == 1, (
            "Some of the other seismograms kept `iccs_cc` and some did not: "
            f"{[q.iccs_cc for q in others]}"
        )
        rmse = event.quality.mccc_rmse if event.quality is not None else None
        target_stats = (target.mccc_cc_mean, target.mccc_cc_std, target.mccc_error)
        stats = [(q.mccc_cc_mean, q.mccc_cc_std, q.mccc_error) for q in others]
        if seeded.in_mccc:
            stats.append(target_stats)
        else:
            assert target_stats == (None, None, None), (
                f"A seismogram outside the MCCC run gained MCCC results: {target_stats}"
            )
        mccc = {value is not None for row in stats for value in row}
        mccc.add(rmse is not None)
        assert len(mccc) == 1, (
            "Only part of the MCCC results survived: "
            f"event RMSE {rmse}, per-seismogram stats {stats}"
        )

        survives = {
            "target_iccs": target.iccs_cc is not None,
            "other_iccs": other_iccs.pop(),
            "mccc": mccc.pop(),
        }
        marks = {
            "modified": event.last_modified is not None,
            "stack_modified": event.stack_modified is not None,
        }
        return (
            frozenset(name for name, kept in survives.items() if kept),
            frozenset(name for name, marked in marks.items() if marked),
        )


_NEW_VALUE: dict[str, Callable[[Any], Any]] = {
    "completed": lambda value: not value,
    "ramp_width": lambda value: value + 0.05,
    "window_pre": lambda value: value - Timedelta(seconds=1),
    "window_post": lambda value: value + Timedelta(seconds=1),
    "bandpass_apply": lambda value: not value,
    "bandpass_fmin": lambda value: value + 0.01,
    "bandpass_fmax": lambda value: value + 0.5,
    "corners": lambda value: value + 1,
    "min_cc": lambda value: value / 2 + 0.1,
    "mccc_damp": lambda value: value + 0.5,
    "mccc_min_cc": lambda value: value / 2 + 0.1,
    "flip": lambda value: not value,
    "select": lambda value: not value,
}
"""A valid value for each parameter that differs from the current one."""


def _change_event_parameter(
    engine: Engine, seeded: Seeded, name: EventParameter, situation: Situation
) -> None:
    with Session(engine) as session:
        event = session.get_one(AimbatEvent, seeded.event_id)
        value = _NEW_VALUE[name](getattr(event.parameters, name))
        if situation == "orm":
            setattr(event.parameters, name, value)
            session.commit()
        else:
            set_event_parameter(session, event.id, name, value)


def _change_seismogram_parameter(
    engine: Engine, seeded: Seeded, name: SeismogramParameter, situation: Situation
) -> None:
    with Session(engine) as session:
        target = session.get_one(AimbatSeismogram, seeded.target_id)
        if name == SeismogramParameter.T1:
            value = target.t0 + Timedelta(seconds=1)
        else:
            value = _NEW_VALUE[name](getattr(target.parameters, name))
        if situation == "orm":
            setattr(target.parameters, name, value)
            session.commit()
        else:
            set_seismogram_parameter(session, target.id, name, value)


@pytest.mark.parametrize("situation", _SITUATIONS)
class TestValidityRules:
    """Changing a parameter leaves exactly what its rule says."""

    # Parametrised over the enum, not the table, so a new parameter fails
    # here until it has a rule.
    @pytest.mark.parametrize("name", list(EventParameter))
    def test_event_parameter(
        self, loaded_engine: Engine, name: EventParameter, situation: Situation
    ) -> None:
        """An event parameter change."""
        rule = EVENT_RULES[name]
        seeded = _seed(loaded_engine, situation)

        _change_event_parameter(loaded_engine, seeded, name, situation)

        assert _observe(loaded_engine, seeded) == (
            getattr(rule, situation),
            rule.marks,
        )

    @pytest.mark.parametrize("in_mccc", [True, False], ids=["in-mccc", "not-in-mccc"])
    @pytest.mark.parametrize("selected", [True, False], ids=["selected", "deselected"])
    @pytest.mark.parametrize("name", list(SeismogramParameter))
    def test_seismogram_parameter(
        self,
        loaded_engine: Engine,
        name: SeismogramParameter,
        selected: bool,
        in_mccc: bool,
        situation: Situation,
    ) -> None:
        """A seismogram parameter change, by the state the seismogram was in."""
        rule = SEISMOGRAM_RULES[name, selected, in_mccc]
        seeded = _seed(loaded_engine, situation, selected=selected, in_mccc=in_mccc)

        _change_seismogram_parameter(loaded_engine, seeded, name, situation)

        assert _observe(loaded_engine, seeded) == (
            getattr(rule, situation),
            rule.marks,
        )
