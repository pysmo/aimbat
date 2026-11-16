"""Digests of the parameters that derived quality values are computed from.

A quality value (`iccs_cc`, the MCCC results) is valid while the parameters
it was computed from are unchanged. Each value is stored with a digest of
those parameters, and is valid while that digest equals the digest of the
current parameters.

Five digests are kept per event:

| Digest | Covers |
|---|---|
| stack | event parameters that are inputs to the stack, and the stack inputs of each selected seismogram |
| seismogram CC | the stack digest, and that seismogram's own stack inputs |
| MCCC | event parameters that are inputs to MCCC, and the MCCC inputs of each seismogram in the run |
| instance | every seismogram CC digest of the event |
| tracked | every parameter of the event and its seismograms that is not bookkeeping |

Which parameter belongs to which digest is read from the parameter specs.

## Encoding

A digest is the SHA-256 of a JSON payload, written without whitespace and
with object keys sorted. The payload is a list of the encoding version, the
digest's name and its content. Parameter values are taken as the database
stores them:

- IDs as 32-character lowercase hex,
- durations as integer nanoseconds,
- timestamps as the stored text, to the microsecond,
- booleans as the integers 0 and 1,
- floats as stored.

Seismograms are listed in ascending order of ID. Any change to what goes into
a payload, or to how a value is written, must bump `ENCODING_VERSION`.
"""

import hashlib
import json
import uuid
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from typing import Any, Self

from sqlalchemy import column, select, table
from sqlmodel import Session

from aimbat.models._parameters import (
    EVENT_PARAMETER_SPECS,
    SEISMOGRAM_PARAMETER_SPECS,
    Reach,
)

__all__ = [
    "ENCODING_VERSION",
    "EventDigests",
    "EventInputs",
    "Validity",
    "compute_digests",
    "encode_members",
    "read_inputs",
]

ENCODING_VERSION = 1
"""Version of the payload encoding. Part of every digest."""

_STACK_EVENT_FIELDS = sorted(
    name for name, spec in EVENT_PARAMETER_SPECS.items() if spec.stack is Reach.EVENT
)
_MCCC_EVENT_FIELDS = sorted(
    name for name, spec in EVENT_PARAMETER_SPECS.items() if spec.mccc is Reach.EVENT
)
_TRACKED_EVENT_FIELDS = sorted(
    name for name, spec in EVENT_PARAMETER_SPECS.items() if not spec.bookkeeping
)
_STACK_SEISMOGRAM_FIELDS = sorted(
    name
    for name, spec in SEISMOGRAM_PARAMETER_SPECS.items()
    if spec.stack is Reach.CONDITIONAL
)
_MCCC_SEISMOGRAM_FIELDS = sorted(
    name
    for name, spec in SEISMOGRAM_PARAMETER_SPECS.items()
    if spec.mccc is Reach.CONDITIONAL
)
_TRACKED_SEISMOGRAM_FIELDS = sorted(
    name for name, spec in SEISMOGRAM_PARAMETER_SPECS.items() if not spec.bookkeeping
)
# A seismogram parameter that is an input to the stack for the whole event
# decides whether the seismogram is part of the stack.
(_STACK_MEMBERSHIP_FIELD,) = (
    name
    for name, spec in SEISMOGRAM_PARAMETER_SPECS.items()
    if spec.stack is Reach.EVENT
)
_EVENT_FIELDS = sorted(EVENT_PARAMETER_SPECS)
_SEISMOGRAM_FIELDS = sorted(SEISMOGRAM_PARAMETER_SPECS)


@dataclass(frozen=True)
class EventInputs:
    """The stored parameters of one event and its seismograms."""

    event_id: str
    """Event ID, as stored."""

    parameters: Mapping[str, Any]
    """Event parameters by field name, as stored."""

    seismograms: Mapping[str, Mapping[str, Any]]
    """Seismogram parameters by field name, keyed by seismogram ID as stored."""


def _digest(name: str, content: Any) -> str:
    payload = json.dumps(
        [ENCODING_VERSION, name, content], separators=(",", ":"), sort_keys=True
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _pick(values: Mapping[str, Any], names: list[str]) -> dict[str, Any]:
    return {name: values[name] for name in names}


@dataclass(frozen=True)
class EventDigests:
    """The digests of one event's parameters.

    The MCCC digest depends on which seismograms took part in the run, so it
    is computed on request with `mccc`.
    """

    inputs: EventInputs = field(repr=False)
    stack: str
    seismogram_cc: Mapping[uuid.UUID, str]
    instance: str
    tracked: str

    @classmethod
    def of(cls, inputs: EventInputs) -> Self:
        """Compute the digests of an event's parameters."""
        seismograms = sorted(inputs.seismograms.items())
        stack = _digest(
            "stack",
            {
                "event": inputs.event_id,
                "parameters": _pick(inputs.parameters, _STACK_EVENT_FIELDS),
                "seismograms": [
                    [seismogram_id, _pick(parameters, _STACK_SEISMOGRAM_FIELDS)]
                    for seismogram_id, parameters in seismograms
                    if parameters[_STACK_MEMBERSHIP_FIELD]
                ],
            },
        )
        seismogram_cc = {
            seismogram_id: _digest(
                "seismogram_cc",
                [stack, seismogram_id, _pick(parameters, _STACK_SEISMOGRAM_FIELDS)],
            )
            for seismogram_id, parameters in seismograms
        }
        instance = _digest("instance", [inputs.event_id, list(seismogram_cc.values())])
        tracked = _digest(
            "tracked",
            {
                "event": inputs.event_id,
                "parameters": _pick(inputs.parameters, _TRACKED_EVENT_FIELDS),
                "seismograms": [
                    [seismogram_id, _pick(parameters, _TRACKED_SEISMOGRAM_FIELDS)]
                    for seismogram_id, parameters in seismograms
                ],
            },
        )
        return cls(
            inputs=inputs,
            stack=stack,
            seismogram_cc={
                uuid.UUID(hex=seismogram_id): digest
                for seismogram_id, digest in seismogram_cc.items()
            },
            instance=instance,
            tracked=tracked,
        )

    def mccc(self, members: Collection[uuid.UUID]) -> str:
        """The MCCC digest for a run over the given seismograms.

        A member that is no longer part of the event counts as changed.
        """
        seismograms = self.inputs.seismograms
        return _digest(
            "mccc",
            {
                "event": self.inputs.event_id,
                "parameters": _pick(self.inputs.parameters, _MCCC_EVENT_FIELDS),
                "seismograms": [
                    [
                        member,
                        _pick(seismograms[member], _MCCC_SEISMOGRAM_FIELDS)
                        if member in seismograms
                        else None,
                    ]
                    for member in sorted({m.hex for m in members})
                ],
            },
        )


def read_inputs(
    session: Session, event_id: uuid.UUID | None = None
) -> dict[uuid.UUID, EventInputs]:
    """Read the stored parameters of one event, or of every event.

    Pending changes in the session are flushed first, so they are included.

    Args:
        session: Database session.
        event_id: Event to read. All events if `None`.

    Returns:
        The parameters of each event, keyed by event ID.
    """
    session.flush()

    # Untyped columns, so the values come back as stored.
    event_parameters = table(
        "aimbateventparameters",
        column("event_id"),
        *(column(name) for name in _EVENT_FIELDS),
    )
    seismogram = table("aimbatseismogram", column("id"), column("event_id"))
    seismogram_parameters = table(
        "aimbatseismogramparameters",
        column("seismogram_id"),
        *(column(name) for name in _SEISMOGRAM_FIELDS),
    )

    event_query = select(event_parameters)
    seismogram_query = select(
        seismogram.c.event_id,
        seismogram.c.id,
        *(seismogram_parameters.c[name] for name in _SEISMOGRAM_FIELDS),
    ).join(
        seismogram_parameters,
        seismogram_parameters.c.seismogram_id == seismogram.c.id,
    )
    if event_id is not None:
        event_query = event_query.where(event_parameters.c.event_id == event_id.hex)
        seismogram_query = seismogram_query.where(seismogram.c.event_id == event_id.hex)

    seismograms: dict[str, dict[str, Mapping[str, Any]]] = {}
    for row in session.execute(seismogram_query).mappings():
        seismograms.setdefault(row["event_id"], {})[row["id"]] = {
            name: row[name] for name in _SEISMOGRAM_FIELDS
        }

    inputs: dict[uuid.UUID, EventInputs] = {}
    for row in session.execute(event_query).mappings():
        stored_id = row["event_id"]
        inputs[uuid.UUID(hex=stored_id)] = EventInputs(
            event_id=stored_id,
            parameters={name: row[name] for name in _EVENT_FIELDS},
            seismograms=seismograms.get(stored_id, {}),
        )
    return inputs


def compute_digests(
    session: Session, event_id: uuid.UUID | None = None
) -> dict[uuid.UUID, EventDigests]:
    """Compute the digests of one event, or of every event, in one pass.

    Args:
        session: Database session.
        event_id: Event to compute. All events if `None`.

    Returns:
        The digests of each event, keyed by event ID.
    """
    return {
        key: EventDigests.of(inputs)
        for key, inputs in read_inputs(session, event_id).items()
    }


def encode_members(members: Collection[uuid.UUID]) -> list[str]:
    """The stored form of an MCCC run's members: hex IDs, sorted, no duplicates."""
    return sorted({member.hex for member in members})


def _read_fingerprints(
    session: Session, event_id: uuid.UUID | None
) -> tuple[dict[uuid.UUID, str | None], dict[uuid.UUID, tuple[str | None, Any]]]:
    """Read the stored fingerprints of one event, or of every event.

    Returns:
        The `iccs_fingerprint` of each seismogram quality row, and the
        `mccc_fingerprint` and `mccc_members` of each event quality row.
    """
    seismogram = table("aimbatseismogram", column("id"), column("event_id"))
    seismogram_quality = table(
        "aimbatseismogramquality", column("seismogram_id"), column("iccs_fingerprint")
    )
    event_quality = table(
        "aimbateventquality",
        column("event_id"),
        column("mccc_fingerprint"),
        column("mccc_members"),
    )
    iccs_query = select(
        seismogram_quality.c.seismogram_id, seismogram_quality.c.iccs_fingerprint
    ).join(seismogram, seismogram.c.id == seismogram_quality.c.seismogram_id)
    mccc_query = select(event_quality)
    if event_id is not None:
        iccs_query = iccs_query.where(seismogram.c.event_id == event_id.hex)
        mccc_query = mccc_query.where(event_quality.c.event_id == event_id.hex)
    iccs = {
        uuid.UUID(hex=seismogram_id): fingerprint
        for seismogram_id, fingerprint in session.execute(iccs_query)
    }
    mccc = {
        uuid.UUID(hex=stored_id): (
            fingerprint,
            None if members is None else json.loads(members),
        )
        for stored_id, fingerprint, members in session.execute(mccc_query)
    }
    return iccs, mccc


class Validity:
    """Whether stored quality values match the current parameters.

    Built once per command, then passed to every reader of quality values. A
    stored value counts only if this says it is valid.
    """

    def __init__(
        self,
        digests: Mapping[uuid.UUID, EventDigests],
        iccs_fingerprints: Mapping[uuid.UUID, str | None],
        mccc_stamps: Mapping[uuid.UUID, tuple[str | None, Collection[str] | None]],
    ) -> None:
        """Initialise from current digests and stored fingerprints.

        Args:
            digests: Digests of every event that will be asked about.
            iccs_fingerprints: Stored `iccs_fingerprint` by seismogram ID.
            mccc_stamps: Stored `mccc_fingerprint` and `mccc_members` by event ID.
        """
        self._digests = dict(digests)
        self._iccs: dict[uuid.UUID, bool] = {}
        self._mccc: dict[uuid.UUID, bool] = {}
        for event_id, event in digests.items():
            for seismogram_id, digest in event.seismogram_cc.items():
                stored = iccs_fingerprints.get(seismogram_id)
                self._iccs[seismogram_id] = stored is not None and stored == digest
            fingerprint, members = mccc_stamps.get(event_id, (None, None))
            self._mccc[event_id] = (
                fingerprint is not None
                and members is not None
                and fingerprint
                == event.mccc([uuid.UUID(hex=member) for member in members])
            )

    @classmethod
    def read(cls, session: Session, event_id: uuid.UUID | None = None) -> Self:
        """Compare the stored fingerprints of one event, or of every event.

        Pending changes in the session are flushed first.

        Args:
            session: Database session.
            event_id: Event to cover. All events if `None`.
        """
        digests = compute_digests(session, event_id)
        return cls(digests, *_read_fingerprints(session, event_id))

    def digests(self, event_id: uuid.UUID) -> EventDigests:
        """The current digests of an event.

        Raises:
            KeyError: If the event is not covered.
        """
        return self._digests[event_id]

    def iccs_cc(self, seismogram_id: uuid.UUID) -> bool:
        """Whether a seismogram's stored `iccs_cc` is valid.

        Raises:
            KeyError: If the seismogram is not covered.
        """
        return self._iccs[seismogram_id]

    def mccc(self, event_id: uuid.UUID) -> bool:
        """Whether an event's stored MCCC results are valid.

        Raises:
            KeyError: If the event is not covered.
        """
        return self._mccc[event_id]
