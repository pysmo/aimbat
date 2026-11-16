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
    EventDigests,
    EventInputs,
    compute_digests,
    read_inputs,
)
from aimbat.models import (
    AimbatEvent,
    AimbatEventParameters,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    AimbatStation,
)

_EVENT_ID = uuid.UUID("00000000-0000-4000-8000-0000000000e1")
_A1 = uuid.UUID("00000000-0000-4000-8000-0000000000a1")
_B2 = uuid.UUID("00000000-0000-4000-8000-0000000000b2")
_C3 = uuid.UUID("00000000-0000-4000-8000-0000000000c3")

# The golden event as the database stores it.
GOLDEN_INPUTS = EventInputs(
    event_id="000000000000400080000000000000e1",
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
    seismograms={
        "000000000000400080000000000000b2": {
            "flip": 0,
            "select": 1,
            "t1": "2011-03-11 05:58:13.123456",
        },
        "000000000000400080000000000000a1": {
            "flip": 1,
            "select": 1,
            "t1": "2011-03-11 05:59:02.000000",
        },
        "000000000000400080000000000000c3": {"flip": 0, "select": 0, "t1": None},
    },
)

GOLDEN_STACK = "65b7f14cc0b342b7c64f04a21674f44185a60ddd37d14cf79966fdc7734bc1a1"
GOLDEN_SEISMOGRAM_CC = {
    _A1: "6ed8615c7f4f121a77d94fc147f0bf2eeae629f885f8fc4c1aa6a928f1b0ea09",
    _B2: "269b7c12ef2c240bdb77da3f67398aef1527aa50ad05119c048290c09c526d73",
    _C3: "9a3533d6076ff148d4eb189c63e48b10b20ec6d567932cd4a37ca35b3b501830",
}
GOLDEN_INSTANCE = "2767334a9bbaf5ae6464d3c1473f46aafcbc79d37a7cca9bedd6c033d6d4c47c"
GOLDEN_TRACKED = "5216433d4860fb2c7041d74041fbe499b8b2d0a4c6f0b4061ecaa2afef80dc66"
GOLDEN_MCCC_ALL = "320ed36b082fa950d421142c53693a3e87abe36cc90d3e7325fc983b62e7a21c"
"""MCCC digest for a run over all three seismograms."""
GOLDEN_MCCC_SELECTED = (
    "90511af6b009be45dc61593d0118672aac899d853bb1d495d66ca80987b20a70"
)
"""MCCC digest for a run over the two selected seismograms."""

# The text the stack digest is the SHA-256 of, so a failure can be traced to
# the value whose stored form changed. The other digests use the same encoding.
GOLDEN_STACK_PAYLOAD = (
    '[1,"stack",{"event":"000000000000400080000000000000e1","parameters":'
    '{"bandpass_apply":1,"bandpass_fmax":2.5,"bandpass_fmin":0.05,"corners":4,'
    '"ramp_width":0.125,"window_post":12250000000,"window_pre":-7500000000},'
    '"seismograms":[["000000000000400080000000000000a1",'
    '{"flip":1,"t1":"2011-03-11 05:59:02.000000"}],'
    '["000000000000400080000000000000b2",'
    '{"flip":0,"t1":"2011-03-11 05:58:13.123456"}]]}]'
)


def _golden_event() -> AimbatEvent:
    """Build the ORM objects that store as `GOLDEN_INPUTS`."""
    station = AimbatStation(
        name="STA",
        network="NW",
        location="00",
        channel="BHZ",
        latitude=10.0,
        longitude=20.0,
        elevation=30.0,
    )
    event = AimbatEvent(
        id=_EVENT_ID,
        time=Timestamp("2011-03-11T05:46:24Z"),
        latitude=38.3,
        longitude=142.4,
        depth=29.0,
    )
    event.parameters = AimbatEventParameters(
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
    for seismogram_id, flip, select_, t1 in (
        (_B2, False, True, Timestamp("2011-03-11T05:58:13.123456Z")),
        (_A1, True, True, Timestamp("2011-03-11T05:59:02Z")),
        (_C3, False, False, None),
    ):
        seismogram = AimbatSeismogram(
            id=seismogram_id,
            begin_time=Timestamp("2011-03-11T05:50:00Z"),
            delta=Timedelta(seconds=0.05),
            t0=Timestamp("2011-03-11T05:58:00Z"),
        )
        seismogram.station = station
        seismogram.parameters = AimbatSeismogramParameters(
            flip=flip, select=select_, t1=t1
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
        digests = EventDigests.of(GOLDEN_INPUTS)
        assert digests.stack == GOLDEN_STACK
        assert digests.seismogram_cc == GOLDEN_SEISMOGRAM_CC
        assert digests.instance == GOLDEN_INSTANCE
        assert digests.tracked == GOLDEN_TRACKED
        assert digests.mccc({_A1, _B2, _C3}) == GOLDEN_MCCC_ALL
        assert digests.mccc({_A1, _B2}) == GOLDEN_MCCC_SELECTED

    def test_read_returns_stored_form(self, engine: Engine) -> None:
        """The golden event, stored and read back, gives the documented inputs."""
        with Session(engine) as session:
            session.add(_golden_event())
            session.commit()
        with Session(engine) as session:
            assert read_inputs(session) == {_EVENT_ID: GOLDEN_INPUTS}


class TestRead:
    """Reading parameters from the database."""

    def test_pending_change_is_read(self, loaded_engine: Engine) -> None:
        """A change not yet flushed is part of the digests."""
        with Session(loaded_engine) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            before = compute_digests(session, event.id)[event.id]
            with session.no_autoflush:
                event.parameters.corners += 1
                after = compute_digests(session, event.id)[event.id]
            assert after.stack != before.stack

    def test_one_event_matches_all_events(self, loaded_engine: Engine) -> None:
        """Reading one event gives the same digests as reading every event."""
        with Session(loaded_engine) as session:
            everything = compute_digests(session)
            assert len(everything) > 1
            for event_id, digests in everything.items():
                assert compute_digests(session, event_id) == {event_id: digests}

    def test_event_without_seismograms(self, engine: Engine) -> None:
        """An event with no seismograms has digests too."""
        event = _golden_event()
        event.seismograms.clear()
        with Session(engine) as session:
            session.add(event)
            session.commit()
            (inputs,) = read_inputs(session).values()
        assert inputs.seismograms == {}

    def test_seismograms_belong_to_their_event(self, loaded_engine: Engine) -> None:
        """Each event's inputs hold exactly its own seismograms."""
        with Session(loaded_engine) as session:
            inputs = read_inputs(session)
            for event in session.exec(select(AimbatEvent)).all():
                assert set(inputs[event.id].seismograms) == {
                    seismogram.id.hex for seismogram in event.seismograms
                }
