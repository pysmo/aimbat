"""Which derived values stay valid after a parameter change.

Each case seeds live quality for one phase, changes one parameter, and checks
what is still valid afterwards. The tables below are the rules. Seeding and
observing each go through a single helper (`_seed`, `_observe`), so a change
of mechanism means porting those two functions and leaving the tables alone.

A result stays valid while the inputs it was computed from are unchanged. For
the MCCC results those inputs are the window, taper and bandpass, the MCCC
parameters, and the effective pick and polarity of the rows that took part
in the run. The effective pick is the refined pick if set, else the initial
pick. Selection, `min_cc` and `completed` are not among the inputs.

Every change is made in three situations, which must agree:

- `orm`: the attribute is assigned and the session committed, as the ICCS and
  MCCC write-back and `toggle_phase_completed` do.
- `api`: through `set_phase_parameter` or `set_seismogram_parameter`, with no
  snapshot holding the seeded results.
- `api_with_snapshot`: the same, with a snapshot of the seeded state to
  restore from.

Each rule also says which of the phase's digests change: `tracked` (every
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
    promote_picks,
    set_phase_parameter,
    set_seismogram_parameter,
    store_picks,
)
from aimbat.core._validity import Validity, compute_digests, encode_members
from aimbat.io import DataType, SourcePick
from aimbat.models import (
    AimbatEvent,
    AimbatPhase,
    AimbatPhaseQuality,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    AimbatSeismogramQuality,
    AimbatStation,
)
from aimbat.types import PhaseParameter, SeismogramParameter

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

EVENT_RULES: dict[PhaseParameter, Rule] = {
    PhaseParameter.WINDOW_PRE: _CHANGES_THE_STACK,
    PhaseParameter.WINDOW_POST: _CHANGES_THE_STACK,
    PhaseParameter.RAMP_WIDTH: _CHANGES_THE_STACK,
    PhaseParameter.BANDPASS_APPLY: _CHANGES_THE_STACK,
    PhaseParameter.BANDPASS_FMIN: _CHANGES_THE_STACK,
    PhaseParameter.BANDPASS_FMAX: _CHANGES_THE_STACK,
    PhaseParameter.CORNERS: _CHANGES_THE_STACK,
    PhaseParameter.MCCC_DAMP: _CHANGES_MCCC_ONLY,
    PhaseParameter.MCCC_MIN_CC: _CHANGES_MCCC_ONLY,
    PhaseParameter.MIN_CC: Rule(_EVERYTHING, _TRACKED),
    PhaseParameter.COMPLETED: Rule(_EVERYTHING, _UNCHANGED),
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
        (SeismogramParameter.REFINED_PICK, _PICK_OR_POLARITY),
        (SeismogramParameter.SELECT, _SELECTION),
    )
    for state, rule in rules.items()
}

# Keyed by (target selected, target in the MCCC run, target refined).
#
# Before refinement the initial pick is the effective pick, so an edit acts
# as a pick change. After it, the initial pick is an input to nothing.
INITIAL_PICK_RULES: dict[tuple[bool, bool, bool], Rule] = {
    **{(*state, False): rule for state, rule in _PICK_OR_POLARITY.items()},
    **{(*state, True): Rule(_EVERYTHING, _UNCHANGED) for state in _PICK_OR_POLARITY},
}


@dataclass(frozen=True)
class Seeded:
    """The phase under test, the row whose parameters change, and the
    digests when seeded."""

    phase_id: uuid.UUID
    target_id: uuid.UUID
    """Row ID."""
    tracked: str
    instance: str
    other_phase_id: uuid.UUID | None = None
    """A second phase of the same event, seeded the same way."""


def _seed_quality(
    session: Session, phase: AimbatPhase, excluded: uuid.UUID | None = None
) -> None:
    """Give a phase a full set of valid live quality values.

    The row `excluded` gets `iccs_cc` but takes no part in the MCCC run.
    """
    digests = compute_digests(session, phase.id)[phase.id]
    rows = phase.seismogram_parameters
    members = {row.id for row in rows if row.id != excluded}
    for row in rows:
        quality = AimbatSeismogramQuality(
            seismogram_parameters_id=row.id,
            iccs_cc=0.9,
            iccs_fingerprint=digests.seismogram_cc[row.id],
        )
        if row.id in members:
            quality.mccc_cc_mean = 0.8
            quality.mccc_cc_std = 0.1
            quality.mccc_error = Timedelta(seconds=0.01)
        session.add(quality)
    session.add(
        AimbatPhaseQuality(
            phase_id=phase.id,
            mccc_rmse=Timedelta(seconds=0.02),
            mccc_members=encode_members(members),
            mccc_fingerprint=digests.mccc(members),
        )
    )
    session.commit()

    validity = Validity.read(session, phase.id)
    assert validity.mccc(phase.id)
    assert all(validity.iccs_cc(row.id) for row in rows)


def _add_phase(session: Session, event: AimbatEvent, name: str) -> AimbatPhase:
    """Give every seismogram of an event a pick of a new phase, one second
    after its first initial pick."""
    picks = []
    for seismogram in event.seismograms:
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
    (phase,) = promote_picks(session, picks).phases_created
    session.commit()
    return phase


def _seed(
    engine: Engine,
    situation: Situation,
    *,
    selected: bool = True,
    in_mccc: bool = True,
    refined: bool = False,
    other_phase: bool = False,
) -> Seeded:
    """Give one phase a full set of valid live quality values.

    Args:
        engine: Engine of a project with data loaded.
        situation: Decides whether a snapshot of the seeded state is taken.
        selected: Whether the target row is selected.
        in_mccc: Whether the target row took part in the MCCC run that the
            seeded results stand for.
        refined: Whether the target row has a refined pick.
        other_phase: Whether a second phase of the event is seeded too.
    """
    with Session(engine) as session:
        # Ordered so the same seismogram is the target on every run.
        seismogram = session.exec(
            select(AimbatSeismogram)
            .join(AimbatEvent)
            .join(AimbatStation)
            .order_by(
                col(AimbatEvent.time),
                col(AimbatStation.network),
                col(AimbatStation.name),
            )
        ).first()
        assert seismogram is not None
        event = seismogram.event
        assert len(event.seismograms) >= 3
        (phase,) = event.phases
        (target,) = seismogram.phase_rows
        target.select = selected
        if refined:
            target.refined_pick = target.initial_pick + Timedelta(seconds=0.5)
        session.commit()

        other = _add_phase(session, event, "S") if other_phase else None

        _seed_quality(session, phase, excluded=None if in_mccc else target.id)
        if other is not None:
            _seed_quality(session, other)
        if situation == "api_with_snapshot":
            create_snapshot(session, phase.id)
            session.commit()

        digests = compute_digests(session, phase.id)[phase.id]
        return Seeded(
            phase_id=phase.id,
            target_id=target.id,
            tracked=digests.tracked,
            instance=digests.instance,
            other_phase_id=None if other is None else other.id,
        )


def _observe(engine: Engine, seeded: Seeded) -> tuple[frozenset[str], frozenset[str]]:
    """Report what is still valid, and which digests moved."""
    with Session(engine) as session:
        validity = Validity.read(session, seeded.phase_id)
        digests = validity.digests(seeded.phase_id)
        other_iccs = {
            validity.iccs_cc(row_id)
            for row_id in digests.seismogram_cc
            if row_id != seeded.target_id
        }
        # The rules take for granted that the other rows are alike.
        assert len(other_iccs) == 1, "Only some of the other rows' iccs_cc."

        survives = {
            "target_iccs": validity.iccs_cc(seeded.target_id),
            "other_iccs": other_iccs.pop(),
            "mccc": validity.mccc(seeded.phase_id),
        }
        moved = {
            "tracked": digests.tracked != seeded.tracked,
            "instance": digests.instance != seeded.instance,
        }
        return (
            frozenset(name for name, kept in survives.items() if kept),
            frozenset(name for name, changed in moved.items() if changed),
        )


def _other_phase_valid(engine: Engine, seeded: Seeded) -> bool:
    """Whether every value of the second phase is still valid."""
    assert seeded.other_phase_id is not None
    with Session(engine) as session:
        validity = Validity.read(session, seeded.other_phase_id)
        digests = validity.digests(seeded.other_phase_id)
        return validity.mccc(seeded.other_phase_id) and all(
            validity.iccs_cc(row_id) for row_id in digests.seismogram_cc
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
    engine: Engine, seeded: Seeded, name: PhaseParameter, situation: Situation
) -> None:
    with Session(engine) as session:
        phase = session.get_one(AimbatPhase, seeded.phase_id)
        value = _NEW_VALUE[name](getattr(phase.parameters, name))
        if situation == "orm":
            setattr(phase.parameters, name, value)
        else:
            set_phase_parameter(session, phase.id, name, value)
        session.commit()


def _change_seismogram_parameter(
    engine: Engine, seeded: Seeded, name: SeismogramParameter, situation: Situation
) -> None:
    with Session(engine) as session:
        target = session.get_one(AimbatSeismogramParameters, seeded.target_id)
        if name == SeismogramParameter.REFINED_PICK:
            value = target.initial_pick + Timedelta(seconds=1)
        else:
            value = _NEW_VALUE[name](getattr(target, name))
        if situation == "orm":
            setattr(target, name, value)
        else:
            set_seismogram_parameter(
                session, target.phase_id, target.seismogram_id, name, value
            )
        session.commit()


def _change_initial_pick(engine: Engine, seeded: Seeded) -> None:
    with Session(engine) as session:
        target = session.get_one(AimbatSeismogramParameters, seeded.target_id)
        target.pick.time += Timedelta(seconds=1)
        session.commit()


@pytest.mark.parametrize("situation", _SITUATIONS)
class TestValidityRules:
    """Changing a parameter leaves exactly what its rule says."""

    # Parametrised over the enum, not the table, so a new parameter fails
    # here until it has a rule.
    @pytest.mark.parametrize("name", list(PhaseParameter))
    def test_event_parameter(
        self, loaded_engine: Engine, name: PhaseParameter, situation: Situation
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


# Initial picks have no `set_*` function yet, so only the ORM changes them.
@pytest.mark.parametrize("refined", [False, True], ids=["unrefined", "refined"])
@pytest.mark.parametrize("in_mccc", [True, False], ids=["in-mccc", "not-in-mccc"])
@pytest.mark.parametrize("selected", [True, False], ids=["selected", "deselected"])
def test_initial_pick(
    loaded_engine: Engine, selected: bool, in_mccc: bool, refined: bool
) -> None:
    """An initial pick edit counts only while the refined pick is unset."""
    rule = INITIAL_PICK_RULES[selected, in_mccc, refined]
    seeded = _seed(
        loaded_engine, "orm", selected=selected, in_mccc=in_mccc, refined=refined
    )

    _change_initial_pick(loaded_engine, seeded)

    assert _observe(loaded_engine, seeded) == (rule.survives, rule.digests)


@pytest.mark.parametrize("situation", _SITUATIONS)
class TestPhaseIsolation:
    """A change in one phase leaves another phase of the same event valid."""

    @pytest.mark.parametrize("name", list(PhaseParameter))
    def test_phase_parameter(
        self, loaded_engine: Engine, name: PhaseParameter, situation: Situation
    ) -> None:
        seeded = _seed(loaded_engine, situation, other_phase=True)

        _change_event_parameter(loaded_engine, seeded, name, situation)

        assert _observe(loaded_engine, seeded) == (
            EVENT_RULES[name].survives,
            EVENT_RULES[name].digests,
        )
        assert _other_phase_valid(loaded_engine, seeded)

    @pytest.mark.parametrize("name", list(SeismogramParameter))
    def test_seismogram_parameter(
        self, loaded_engine: Engine, name: SeismogramParameter, situation: Situation
    ) -> None:
        seeded = _seed(loaded_engine, situation, other_phase=True)

        _change_seismogram_parameter(loaded_engine, seeded, name, situation)

        assert _observe(loaded_engine, seeded) == (
            SEISMOGRAM_RULES[name, True, True].survives,
            SEISMOGRAM_RULES[name, True, True].digests,
        )
        assert _other_phase_valid(loaded_engine, seeded)


def test_initial_pick_phase_isolation(loaded_engine: Engine) -> None:
    """An initial pick edit in one phase leaves another phase valid."""
    seeded = _seed(loaded_engine, "orm", other_phase=True)

    _change_initial_pick(loaded_engine, seeded)

    assert _observe(loaded_engine, seeded) == (
        INITIAL_PICK_RULES[True, True, False].survives,
        INITIAL_PICK_RULES[True, True, False].digests,
    )
    assert _other_phase_valid(loaded_engine, seeded)
