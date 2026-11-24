"""Golden values and the database read for the parameter digests.

Quality values will be stored with these digests and compared against them
later, so the digest of a given parameter set must not change by accident.
If a golden test fails after a deliberate change to a payload, bump
`ENCODING_VERSION` and update the literals. If it fails after anything else
(a dependency bump, a refactor), the stored form of a parameter has changed.
"""

import hashlib
import uuid

from pandas import Timedelta, Timestamp
from sqlalchemy import Engine
from sqlmodel import Session, select

from aimbat.core._validity import (
    PhaseDigests,
    PhaseInputs,
    compute_digests,
    read_inputs,
)
from aimbat.models import (
    AimbatEvent,
    AimbatPhase,
    AimbatPhaseParameters,
    AimbatPick,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    AimbatStation,
    PickOrigin,
)

from testsupport.project import first

_PHASE_ID = uuid.UUID("00000000-0000-4000-8000-0000000000e1")
# Row IDs.
_A1 = uuid.UUID("00000000-0000-4000-8000-0000000000a1")
_B2 = uuid.UUID("00000000-0000-4000-8000-0000000000b2")
_C3 = uuid.UUID("00000000-0000-4000-8000-0000000000c3")

# The golden phase as the database stores it.
GOLDEN_INPUTS = PhaseInputs(
    phase_id="000000000000400080000000000000e1",
    parameters={
        "completed": 0,
        "ramp_width": 0.125,
        "window_pre": -7_500_000_000,
        "window_post": 12_250_000_000,
        "bandpass_apply": 1,
        "bandpass_fmin": 0.05,
        "bandpass_fmax": 2.5,
        "corners": 4,
        "min_cc": 0.6,
        "mccc_damp": 0.1,
        "mccc_min_cc": 0.3,
    },
    rows={
        "000000000000400080000000000000b2": {
            "flip": 0,
            "select": 1,
            "refined_pick": "2011-03-11 05:58:13.123456",
        },
        "000000000000400080000000000000a1": {
            "flip": 1,
            "select": 1,
            "refined_pick": "2011-03-11 05:59:02.000000",
        },
        # No refined pick, so the initial pick is read in its place.
        "000000000000400080000000000000c3": {
            "flip": 0,
            "select": 0,
            "refined_pick": "2011-03-11 05:58:00.000000",
        },
    },
)

GOLDEN_STACK = "3ed0bcaacb7e83c47a398e4fb0bf2d00ab3e9e90988f6d8e105873e648cfd963"
GOLDEN_SEISMOGRAM_CC = {
    _A1: "4f429cb725fb4646f2e445287a09b50b82c302c496550feb13720cc96368931f",
    _B2: "bb94b3ce82d81592744ad4df3093453226a5c33fd2bcc0b4e941df83131e1185",
    _C3: "8aab00ae52895e0204a0a1702bef8c0dfee484a303c6ae90f148c610464dd14e",
}
GOLDEN_INSTANCE = "ca9af594bd534b7791dcff9d7cfad1f73083dc0ca1e1fa4768c1df994b490b20"
GOLDEN_TRACKED = "528d3deeab98f34bb826c17b240ce10ac7b31327b2d5ad0adfd1d92907c48927"
GOLDEN_MCCC_ALL = "0606693c73606967f5fcee8601589751951d744b33b5d70aced874fd620999ba"
"""MCCC digest for a run over all three rows."""
GOLDEN_MCCC_SELECTED = (
    "7ffa116a815a9512e6e3eb5ffc86e8fe5bd496708c65973a454f1eaca38ebfa1"
)
"""MCCC digest for a run over the two selected rows."""

# The text the stack digest is the SHA-256 of, so a failure can be traced to
# the value whose stored form changed. The other digests use the same encoding.
GOLDEN_STACK_PAYLOAD = (
    '[2,"stack",{"parameters":'
    '{"bandpass_apply":1,"bandpass_fmax":2.5,"bandpass_fmin":0.05,"corners":4,'
    '"ramp_width":0.125,"window_post":12250000000,"window_pre":-7500000000},'
    '"phase":"000000000000400080000000000000e1",'
    '"rows":[["000000000000400080000000000000a1",'
    '{"flip":1,"refined_pick":"2011-03-11 05:59:02.000000"}],'
    '["000000000000400080000000000000b2",'
    '{"flip":0,"refined_pick":"2011-03-11 05:58:13.123456"}]]}]'
)


def _golden_event(*, with_seismograms: bool = True) -> AimbatEvent:
    """Build the ORM objects that store as `GOLDEN_INPUTS`."""
    event = AimbatEvent(
        time=Timestamp("2011-03-11T05:46:24Z"),
        latitude=38.3,
        longitude=142.4,
        depth=29.0,
    )
    phase = AimbatPhase(id=_PHASE_ID, name="P")
    phase.parameters = AimbatPhaseParameters(
        completed=False,
        ramp_width=0.125,
        window_pre=Timedelta(seconds=-7.5),
        window_post=Timedelta(seconds=12.25),
        bandpass_apply=True,
        bandpass_fmin=0.05,
        bandpass_fmax=2.5,
        corners=4,
        min_cc=0.6,
        mccc_damp=0.1,
        mccc_min_cc=0.3,
    )
    event.phases.append(phase)
    if not with_seismograms:
        return event
    for row_id, flip, select_, refined_pick in (
        (_B2, False, True, Timestamp("2011-03-11T05:58:13.123456Z")),
        (_A1, True, True, Timestamp("2011-03-11T05:59:02Z")),
        (_C3, False, False, None),
    ):
        seismogram = AimbatSeismogram(
            begin_time=Timestamp("2011-03-11T05:50:00Z"),
            delta=Timedelta(seconds=0.05),
        )
        seismogram.station = AimbatStation(
            name=f"STA{row_id.hex[-1]}",
            network="NW",
            location="00",
            channel="BHZ",
            latitude=10.0,
            longitude=20.0,
            elevation=30.0,
        )
        pick = AimbatPick(
            time=Timestamp("2011-03-11T05:58:00Z"),
            phase_name="P",
            origin=PickOrigin.MANUAL,
            seismogram=seismogram,
        )
        AimbatSeismogramParameters(
            id=row_id,
            seismogram=seismogram,
            phase=phase,
            pick=pick,
            flip=flip,
            select=select_,
            refined_pick=refined_pick,
        )
        event.seismograms.append(seismogram)
    return event


class TestGoldenDigests:
    """The digests of a fixed parameter set are pinned."""

    def test_stack_digest_matches_documented_payload(self) -> None:
        """The pinned stack digest is the SHA-256 of the payload written above."""
        digest = hashlib.sha256(GOLDEN_STACK_PAYLOAD.encode()).hexdigest()
        assert digest == GOLDEN_STACK

    def test_digests(self) -> None:
        """The digests of the documented inputs."""
        digests = PhaseDigests.of(GOLDEN_INPUTS)
        assert digests.stack == GOLDEN_STACK
        assert digests.seismogram_cc == GOLDEN_SEISMOGRAM_CC
        assert digests.instance == GOLDEN_INSTANCE
        assert digests.tracked == GOLDEN_TRACKED
        assert digests.mccc({_A1, _B2, _C3}) == GOLDEN_MCCC_ALL
        assert digests.mccc({_A1, _B2}) == GOLDEN_MCCC_SELECTED

    def test_read_returns_stored_form(self, engine: Engine) -> None:
        """The golden phase, stored and read back, gives the documented inputs."""
        with Session(engine) as session:
            session.add(_golden_event())
            session.commit()
        with Session(engine) as session:
            assert read_inputs(session) == {_PHASE_ID: GOLDEN_INPUTS}


class TestRead:
    """Reading parameters from the database."""

    def test_pending_change_is_read(self, loaded_engine: Engine) -> None:
        """A change not yet flushed is part of the digests."""
        with Session(loaded_engine) as session:
            phase = first(session, AimbatPhase)
            before = compute_digests(session, phase.id)[phase.id]
            with session.no_autoflush:
                phase.parameters.corners += 1
                after = compute_digests(session, phase.id)[phase.id]
            assert after.stack != before.stack

    def test_one_phase_matches_all_phases(self, loaded_engine: Engine) -> None:
        """Reading one phase gives the same digests as reading every phase."""
        with Session(loaded_engine) as session:
            everything = compute_digests(session)
            assert len(everything) > 1
            for phase_id, digests in everything.items():
                assert compute_digests(session, phase_id) == {phase_id: digests}

    def test_event_reads_its_phases(self, loaded_engine: Engine) -> None:
        """Reading by event gives the digests of that event's phases."""
        with Session(loaded_engine) as session:
            everything = compute_digests(session)
            for event in session.exec(select(AimbatEvent)).all():
                assert compute_digests(session, event_id=event.id) == {
                    phase.id: everything[phase.id] for phase in event.phases
                }

    def test_phase_without_rows(self, engine: Engine) -> None:
        """A phase with no rows has digests too."""
        event = _golden_event(with_seismograms=False)
        with Session(engine) as session:
            session.add(event)
            session.commit()
            (inputs,) = read_inputs(session).values()
        assert inputs.rows == {}

    def test_event_without_phases(self, engine: Engine) -> None:
        """An event without phases has no digests."""
        event = AimbatEvent(
            time=Timestamp("2011-03-11T05:46:24Z"), latitude=0.0, longitude=0.0
        )
        with Session(engine) as session:
            session.add(event)
            session.commit()
            assert compute_digests(session, event_id=event.id) == {}

    def test_rows_belong_to_their_phase(self, loaded_engine: Engine) -> None:
        """Each phase's inputs hold exactly its own rows."""
        with Session(loaded_engine) as session:
            inputs = read_inputs(session)
            for phase in session.exec(select(AimbatPhase)).all():
                assert set(inputs[phase.id].rows) == {
                    row.id.hex for row in phase.seismogram_parameters
                }
