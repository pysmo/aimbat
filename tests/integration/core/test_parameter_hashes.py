"""Golden-value tests for the ICCS and MCCC parameter hashes.

Snapshots store these digests and later runs compare against them, so the
digest of a given parameter set must not change by accident: a different
digest silently stops existing snapshots from matching. The relative
properties (which parameter affects which hash) are covered in
`test_snapshots.py::TestComputeHashes`.

If a test here fails after a deliberate change to what is hashed, update the
literals. If it fails after anything else (a dependency bump, a refactor), the
serialised form of a parameter has changed and stored hashes no longer match.
"""

import hashlib
import uuid

import pytest
from pandas import Timedelta, Timestamp
from sqlalchemy import Engine
from sqlmodel import Session

from aimbat.core._snapshot import compute_iccs_hash, compute_mccc_hash
from aimbat.models import (
    AimbatEvent,
    AimbatEventParameters,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    AimbatStation,
)

GOLDEN_ICCS_HASH = "0b76a434d0ec9565c88cf8dc44a2d12a7a9266efa0d76274f4826d08dcac2f77"
GOLDEN_MCCC_HASH = "2d53ee51b1ff20c5bc8fe76a2f3460104097dea5d8eb94b724dea861cd156b06"

# The text each digest is the SHA-256 of. Kept here so a failure can be traced
# to the field whose serialised form changed.
GOLDEN_ICCS_PAYLOAD = (
    '{"event": {"bandpass_apply": true, "bandpass_fmax": 2.5, '
    '"bandpass_fmin": 0.05, "corners": 4, '
    '"event_id": "00000000-0000-4000-8000-0000000000e1", "ramp_width": 0.125, '
    '"window_post": 12.25, "window_pre": -7.5}, "seismograms": ['
    '{"flip": true, "seismogram_id": "00000000-0000-4000-8000-0000000000a1", '
    '"select": true, "t1": "2011-03-11T05:59:02Z"}, '
    '{"flip": false, "seismogram_id": "00000000-0000-4000-8000-0000000000b2", '
    '"select": true, "t1": "2011-03-11T05:58:13.123456Z"}, '
    '{"flip": false, "seismogram_id": "00000000-0000-4000-8000-0000000000c3", '
    '"select": false, "t1": null}]}'
)
GOLDEN_MCCC_PAYLOAD = (
    '{"event": {"bandpass_apply": true, "bandpass_fmax": 2.5, '
    '"bandpass_fmin": 0.05, "corners": 4, '
    '"event_id": "00000000-0000-4000-8000-0000000000e1", "mccc_damp": 0.1, '
    '"mccc_min_cc": 0.3, "ramp_width": 0.125, "window_post": 12.25, '
    '"window_pre": -7.5}, "seismograms": ['
    '{"flip": true, "seismogram_id": "00000000-0000-4000-8000-0000000000a1", '
    '"t1": "2011-03-11T05:59:02Z"}, '
    '{"flip": false, "seismogram_id": "00000000-0000-4000-8000-0000000000b2", '
    '"t1": "2011-03-11T05:58:13.123456Z"}, '
    '{"flip": false, "seismogram_id": "00000000-0000-4000-8000-0000000000c3", '
    '"t1": null}]}'
)

_EVENT_ID = uuid.UUID("00000000-0000-4000-8000-0000000000e1")
# Listed out of ID order: the hash must sort them.
_SEISMOGRAM_IDS = (
    uuid.UUID("00000000-0000-4000-8000-0000000000b2"),
    uuid.UUID("00000000-0000-4000-8000-0000000000a1"),
    uuid.UUID("00000000-0000-4000-8000-0000000000c3"),
)
_SEISMOGRAM_PARAMETERS: tuple[tuple[bool, bool, Timestamp | None], ...] = (
    (False, True, Timestamp("2011-03-11T05:58:13.123456Z")),
    (True, True, Timestamp("2011-03-11T05:59:02Z")),
    (False, False, None),
)


def _golden_event() -> AimbatEvent:
    """Build the fixed event the golden digests were computed from.

    Every hashed field is set explicitly so the digests do not depend on the
    default settings.
    """
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
    for seismogram_id, (flip, select, t1) in zip(
        _SEISMOGRAM_IDS, _SEISMOGRAM_PARAMETERS, strict=True
    ):
        seismogram = AimbatSeismogram(
            id=seismogram_id,
            begin_time=Timestamp("2011-03-11T05:50:00Z"),
            delta=Timedelta(seconds=0.05),
            t0=Timestamp("2011-03-11T05:58:00Z"),
        )
        seismogram.station = station
        seismogram.parameters = AimbatSeismogramParameters(
            flip=flip, select=select, t1=t1
        )
        event.seismograms.append(seismogram)
    return event


def _reloaded(engine: Engine, event: AimbatEvent) -> tuple[str, str]:
    """Store `event`, then hash it as read back by a new session."""
    event_id = event.id
    with Session(engine) as session:
        session.add(event)
        session.commit()
    with Session(engine) as session:
        stored = session.get_one(AimbatEvent, event_id)
        return compute_iccs_hash(stored), compute_mccc_hash(stored)


class TestGoldenHashes:
    """The digests of a fixed parameter set are pinned."""

    def test_digests_match_documented_payloads(self) -> None:
        """The pinned digests are the SHA-256 of the payloads written above."""
        assert hashlib.sha256(GOLDEN_ICCS_PAYLOAD.encode()).hexdigest() == (
            GOLDEN_ICCS_HASH
        )
        assert hashlib.sha256(GOLDEN_MCCC_PAYLOAD.encode()).hexdigest() == (
            GOLDEN_MCCC_HASH
        )

    def test_in_memory(self) -> None:
        """Parameters that have not been through the database."""
        event = _golden_event()
        assert compute_iccs_hash(event) == GOLDEN_ICCS_HASH
        assert compute_mccc_hash(event) == GOLDEN_MCCC_HASH

    def test_after_round_trip(self, engine: Engine) -> None:
        """The same parameters, stored and read back."""
        assert _reloaded(engine, _golden_event()) == (
            GOLDEN_ICCS_HASH,
            GOLDEN_MCCC_HASH,
        )

    def test_excluded_fields_do_not_reach_the_digest(self) -> None:
        """Fields outside both hashes can change without moving the digests."""
        event = _golden_event()
        event.parameters.completed = True
        event.parameters.min_cc = 0.9
        assert compute_iccs_hash(event) == GOLDEN_ICCS_HASH
        assert compute_mccc_hash(event) == GOLDEN_MCCC_HASH


class TestSubMicrosecondPick:
    """A pick finer than the database stores, hashed before and after storing."""

    @pytest.mark.parametrize(
        "nanoseconds",
        [
            pytest.param(400, id="rounds-down"),
            pytest.param(500, id="tie"),
            pytest.param(600, id="rounds-up"),
        ],
    )
    def test_hash_survives_storing(self, engine: Engine, nanoseconds: int) -> None:
        """Storing a pick must not change the digests it produces."""
        event = _golden_event()
        pick = event.seismograms[0].parameters.t1
        assert pick is not None
        event.seismograms[0].parameters.t1 = pick + Timedelta(nanoseconds=nanoseconds)
        before = compute_iccs_hash(event), compute_mccc_hash(event)
        assert _reloaded(engine, event) == before
