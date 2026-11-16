"""Which derived values stay valid after a parameter change.

Each case seeds live quality for one event, changes one parameter, and checks
what is still valid afterwards. The tables below are the rules. Seeding and
observing each go through a single helper (`_seed`, `_observe`), so a change
of mechanism means porting those two functions and leaving the tables alone.

A result stays valid while the inputs it was computed from are unchanged. For
the MCCC results those inputs are the window, taper and bandpass, the MCCC
parameters, and the pick and polarity of the seismograms that took part in
the run. Selection, `min_cc` and `completed` are not among them.

Every change is made in three situations, which must agree:

- `orm`: the attribute is assigned and the session committed, as the ICCS and
  MCCC write-back and `toggle_event_completed` do.
- `api`: through `set_event_parameter` or `set_seismogram_parameter`, with no
  snapshot holding the seeded results.
- `api_with_snapshot`: the same, with a snapshot of the seeded state to
  restore from.

Each rule also says which of the event's digests change: `tracked` (every
parameter that is not bookkeeping) and `instance` (what a built ICCS
instance reflects).
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
from aimbat.core._validity import Validity, compute_digests, encode_members
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

# What can stay valid after a change.
_NOTHING: frozenset[str] = frozenset()
_OTHER_ICCS = frozenset({"other_iccs"})
_ICCS = frozenset({"target_iccs", "other_iccs"})
_MCCC = frozenset({"mccc"})
_EVERYTHING = _ICCS | _MCCC

# Which digests a change moves.
_UNCHANGED: frozenset[str] = frozenset()
_TRACKED = frozenset({"tracked"})
_INSTANCE = frozenset({"tracked", "instance"})


@dataclass(frozen=True)
class Rule:
    """What stays valid after a change, and which digests it moves."""

    survives: frozenset[str]
    digests: frozenset[str]


_CHANGES_THE_STACK = Rule(_NOTHING, _INSTANCE)
_CHANGES_MCCC_ONLY = Rule(_ICCS, _TRACKED)

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
    EventParameter.MIN_CC: Rule(_EVERYTHING, _TRACKED),
    EventParameter.COMPLETED: Rule(_EVERYTHING, _UNCHANGED),
}

# Keyed by (parameter, target selected, target in the MCCC run).
#
# A pick or polarity change on a seismogram outside the stack leaves the other
# seismograms' `iccs_cc` alone, and one outside the MCCC run leaves the MCCC
# results alone.
_PICK_OR_POLARITY: dict[tuple[bool, bool], Rule] = {
    (True, True): Rule(_NOTHING, _INSTANCE),
    (True, False): Rule(_MCCC, _INSTANCE),
    (False, True): Rule(_OTHER_ICCS, _INSTANCE),
    (False, False): Rule(_OTHER_ICCS | _MCCC, _INSTANCE),
}
# Selection changes the stack, so no `iccs_cc` survives, but it is not an
# input to MCCC, so the MCCC results always stay.
_SELECTION: dict[tuple[bool, bool], Rule] = {
    (selected, in_mccc): Rule(_MCCC, _INSTANCE)
    for selected in (True, False)
    for in_mccc in (True, False)
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
    """The event under test, the seismogram whose parameters change, and the
    digests when seeded."""

    event_id: uuid.UUID
    target_id: uuid.UUID
    tracked: str
    instance: str


def _seed(
    engine: Engine,
    situation: Situation,
    *,
    selected: bool = True,
    in_mccc: bool = True,
) -> Seeded:
    """Give one event a full set of valid live quality values.

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

        digests = compute_digests(session, event.id)[event.id]
        members = {
            seismogram.id
            for seismogram in event.seismograms
            if in_mccc or seismogram.id != target.id
        }
        for seismogram in event.seismograms:
            quality = AimbatSeismogramQuality(
                seismogram_id=seismogram.id,
                iccs_cc=0.9,
                iccs_fingerprint=digests.seismogram_cc[seismogram.id],
            )
            if seismogram.id in members:
                quality.mccc_cc_mean = 0.8
                quality.mccc_cc_std = 0.1
                quality.mccc_error = Timedelta(seconds=0.01)
            session.add(quality)
        session.add(
            AimbatEventQuality(
                event_id=event.id,
                mccc_rmse=Timedelta(seconds=0.02),
                mccc_members=encode_members(members),
                mccc_fingerprint=digests.mccc(members),
            )
        )
        session.commit()
        if situation == "api_with_snapshot":
            create_snapshot(session, event)

        validity = Validity.read(session, event.id)
        assert validity.mccc(event.id)
        assert all(validity.iccs_cc(s.id) for s in event.seismograms)
        return Seeded(
            event_id=event.id,
            target_id=target.id,
            tracked=digests.tracked,
            instance=digests.instance,
        )


def _observe(engine: Engine, seeded: Seeded) -> tuple[frozenset[str], frozenset[str]]:
    """Report what is still valid, and which digests moved."""
    with Session(engine) as session:
        validity = Validity.read(session, seeded.event_id)
        digests = validity.digests(seeded.event_id)
        other_iccs = {
            validity.iccs_cc(seismogram_id)
            for seismogram_id in digests.seismogram_cc
            if seismogram_id != seeded.target_id
        }
        # The rules take for granted that the other seismograms are alike.
        assert len(other_iccs) == 1, "Only some of the other seismograms' iccs_cc."

        survives = {
            "target_iccs": validity.iccs_cc(seeded.target_id),
            "other_iccs": other_iccs.pop(),
            "mccc": validity.mccc(seeded.event_id),
        }
        moved = {
            "tracked": digests.tracked != seeded.tracked,
            "instance": digests.instance != seeded.instance,
        }
        return (
            frozenset(name for name, kept in survives.items() if kept),
            frozenset(name for name, changed in moved.items() if changed),
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

        assert _observe(loaded_engine, seeded) == (rule.survives, rule.digests)

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

        assert _observe(loaded_engine, seeded) == (rule.survives, rule.digests)
