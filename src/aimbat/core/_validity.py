"""Digests of the parameters that derived quality values are computed from.

A quality value (`iccs_cc`, the MCCC results) is valid while the parameters
it was computed from are unchanged. Each value is stored with a digest of
those parameters, and is valid while that digest equals the digest of the
current parameters.

Five digests are kept per phase. A row is the processing state of one
seismogram in the phase.

| Digest | Covers |
|---|---|
| stack | phase parameters that are inputs to the stack, and the stack inputs of each selected row |
| seismogram CC | the stack digest, and that row's own stack inputs |
| MCCC | phase parameters that are inputs to MCCC, and the MCCC inputs of each row in the run |
| instance | every seismogram CC digest of the phase |
| tracked | every parameter of the phase and its rows that is not bookkeeping |

Which parameter belongs to which digest is read from the parameter specs.
The value given for `refined_pick` is the effective pick: the refined pick
if set, else the initial pick. An edit to the initial pick therefore counts
only while the refined pick is unset.

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

Rows are listed in ascending order of ID. Any change to what goes into a
payload, or to how a value is written, must bump `ENCODING_VERSION`.
"""

import hashlib
import json
import uuid
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from typing import Any, Self

from sqlalchemy import column, func, select, table
from sqlmodel import Session

from aimbat.models._parameters import (
    PHASE_PARAMETER_SPECS,
    SEISMOGRAM_PARAMETER_SPECS,
    Reach,
)

__all__ = ["Validity"]

ENCODING_VERSION = 2
"""Version of the payload encoding. Part of every digest."""

_STACK_EVENT_FIELDS = sorted(
    name for name, spec in PHASE_PARAMETER_SPECS.items() if spec.stack is Reach.EVENT
)
_MCCC_EVENT_FIELDS = sorted(
    name for name, spec in PHASE_PARAMETER_SPECS.items() if spec.mccc is Reach.EVENT
)
_TRACKED_EVENT_FIELDS = sorted(
    name for name, spec in PHASE_PARAMETER_SPECS.items() if not spec.bookkeeping
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
# A seismogram parameter that is an input to the stack for the whole phase
# decides whether the row is part of the stack.
(_STACK_MEMBERSHIP_FIELD,) = (
    name
    for name, spec in SEISMOGRAM_PARAMETER_SPECS.items()
    if spec.stack is Reach.EVENT
)
_EVENT_FIELDS = sorted(PHASE_PARAMETER_SPECS)
_SEISMOGRAM_FIELDS = sorted(SEISMOGRAM_PARAMETER_SPECS)
_PICK_FIELD = "refined_pick"
"""The row parameter whose value is replaced by the effective pick."""


@dataclass(frozen=True)
class PhaseInputs:
    """The stored parameters of one phase and its rows."""

    phase_id: str
    """Phase ID, as stored."""

    parameters: Mapping[str, Any]
    """Phase parameters by field name, as stored."""

    rows: Mapping[str, Mapping[str, Any]]
    """Row parameters by field name, keyed by row ID as stored. The value of
    `refined_pick` is the effective pick."""


def _digest(name: str, content: Any) -> str:
    payload = json.dumps(
        [ENCODING_VERSION, name, content], separators=(",", ":"), sort_keys=True
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _pick(values: Mapping[str, Any], names: list[str]) -> dict[str, Any]:
    return {name: values[name] for name in names}


@dataclass(frozen=True)
class PhaseDigests:
    """The digests of one phase's parameters.

    The MCCC digest depends on which rows took part in the run, so it is
    computed on request with `mccc`.
    """

    inputs: PhaseInputs = field(repr=False)
    stack: str
    seismogram_cc: Mapping[uuid.UUID, str]
    """Seismogram CC digest by row ID."""
    instance: str
    tracked: str

    @classmethod
    def of(cls, inputs: PhaseInputs) -> Self:
        """Compute the digests of a phase's parameters."""
        rows = sorted(inputs.rows.items())
        stack = _digest(
            "stack",
            {
                "phase": inputs.phase_id,
                "parameters": _pick(inputs.parameters, _STACK_EVENT_FIELDS),
                "rows": [
                    [row_id, _pick(parameters, _STACK_SEISMOGRAM_FIELDS)]
                    for row_id, parameters in rows
                    if parameters[_STACK_MEMBERSHIP_FIELD]
                ],
            },
        )
        seismogram_cc = {
            row_id: _digest(
                "seismogram_cc",
                [stack, row_id, _pick(parameters, _STACK_SEISMOGRAM_FIELDS)],
            )
            for row_id, parameters in rows
        }
        instance = _digest("instance", [inputs.phase_id, list(seismogram_cc.values())])
        tracked = _digest(
            "tracked",
            {
                "phase": inputs.phase_id,
                "parameters": _pick(inputs.parameters, _TRACKED_EVENT_FIELDS),
                "rows": [
                    [row_id, _pick(parameters, _TRACKED_SEISMOGRAM_FIELDS)]
                    for row_id, parameters in rows
                ],
            },
        )
        return cls(
            inputs=inputs,
            stack=stack,
            seismogram_cc={
                uuid.UUID(hex=row_id): digest
                for row_id, digest in seismogram_cc.items()
            },
            instance=instance,
            tracked=tracked,
        )

    def mccc(self, members: Collection[uuid.UUID]) -> str:
        """The MCCC digest for a run over the given rows.

        A member that is no longer a row of the phase counts as changed.
        """
        rows = self.inputs.rows
        return _digest(
            "mccc",
            {
                "phase": self.inputs.phase_id,
                "parameters": _pick(self.inputs.parameters, _MCCC_EVENT_FIELDS),
                "rows": [
                    [
                        member,
                        _pick(rows[member], _MCCC_SEISMOGRAM_FIELDS)
                        if member in rows
                        else None,
                    ]
                    for member in sorted({m.hex for m in members})
                ],
            },
        )


def read_inputs(
    session: Session,
    phase_id: uuid.UUID | None = None,
    *,
    event_id: uuid.UUID | None = None,
) -> dict[uuid.UUID, PhaseInputs]:
    """Read the stored parameters of one phase, the phases of one event, or every phase.

    Pending changes in the session are flushed first, so they are included.

    Args:
        session: Database session.
        phase_id: Phase to read.
        event_id: Event whose phases are read. Every phase if neither is given.

    Returns:
        The parameters of each phase, keyed by phase ID.
    """
    session.flush()

    # Untyped columns, so the values come back as stored.
    phase = table("aimbatphase", column("id"), column("event_id"))
    phase_parameters = table(
        "aimbatphaseparameters",
        column("phase_id"),
        *(column(name) for name in _EVENT_FIELDS),
    )
    rows = table(
        "aimbatseismogramparameters",
        column("id"),
        column("phase_id"),
        column("pick_id"),
        *(column(name) for name in _SEISMOGRAM_FIELDS),
    )
    pick = table("aimbatpick", column("id"), column("time"))

    phase_query = select(
        phase.c.id, *(phase_parameters.c[name] for name in _EVENT_FIELDS)
    ).join(phase, phase.c.id == phase_parameters.c.phase_id)
    row_query = (
        select(
            rows.c.phase_id,
            rows.c.id,
            *(rows.c[name] for name in _SEISMOGRAM_FIELDS if name != _PICK_FIELD),
            func.coalesce(rows.c[_PICK_FIELD], pick.c.time).label(_PICK_FIELD),
        )
        .join(pick, pick.c.id == rows.c.pick_id)
        .join(phase, phase.c.id == rows.c.phase_id)
    )
    if phase_id is not None:
        phase_query = phase_query.where(phase.c.id == phase_id.hex)
        row_query = row_query.where(phase.c.id == phase_id.hex)
    if event_id is not None:
        phase_query = phase_query.where(phase.c.event_id == event_id.hex)
        row_query = row_query.where(phase.c.event_id == event_id.hex)

    phase_rows: dict[str, dict[str, Mapping[str, Any]]] = {}
    for row in session.execute(row_query).mappings():
        phase_rows.setdefault(row["phase_id"], {})[row["id"]] = {
            name: row[name] for name in _SEISMOGRAM_FIELDS
        }

    inputs: dict[uuid.UUID, PhaseInputs] = {}
    for row in session.execute(phase_query).mappings():
        stored_id = row["id"]
        inputs[uuid.UUID(hex=stored_id)] = PhaseInputs(
            phase_id=stored_id,
            parameters={name: row[name] for name in _EVENT_FIELDS},
            rows=phase_rows.get(stored_id, {}),
        )
    return inputs


def compute_digests(
    session: Session,
    phase_id: uuid.UUID | None = None,
    *,
    event_id: uuid.UUID | None = None,
) -> dict[uuid.UUID, PhaseDigests]:
    """Compute the digests of one phase, the phases of one event, or every phase.

    Args:
        session: Database session.
        phase_id: Phase to compute.
        event_id: Event whose phases are computed. Every phase if neither is
            given.

    Returns:
        The digests of each phase, keyed by phase ID.
    """
    return {
        key: PhaseDigests.of(inputs)
        for key, inputs in read_inputs(session, phase_id, event_id=event_id).items()
    }


def encode_members(members: Collection[uuid.UUID]) -> list[str]:
    """The stored form of an MCCC run's members: hex IDs, sorted, no duplicates."""
    return sorted({member.hex for member in members})


def _read_fingerprints(
    session: Session, phase_id: uuid.UUID | None, event_id: uuid.UUID | None
) -> tuple[dict[uuid.UUID, str | None], dict[uuid.UUID, tuple[str | None, Any]]]:
    """Read the stored fingerprints of one phase, the phases of one event, or every phase.

    Returns:
        The `iccs_fingerprint` of each row, and the `mccc_fingerprint` and
        `mccc_members` of each phase.
    """
    rows = table("aimbatseismogramparameters", column("id"), column("phase_id"))
    seismogram_quality = table(
        "aimbatseismogramquality",
        column("seismogram_parameters_id"),
        column("iccs_fingerprint"),
    )
    phase = table("aimbatphase", column("id"), column("event_id"))
    phase_quality = table(
        "aimbatphasequality",
        column("phase_id"),
        column("mccc_fingerprint"),
        column("mccc_members"),
    )
    iccs_query = (
        select(rows.c.id, seismogram_quality.c.iccs_fingerprint)
        .join(rows, rows.c.id == seismogram_quality.c.seismogram_parameters_id)
        .join(phase, phase.c.id == rows.c.phase_id)
    )
    mccc_query = select(
        phase.c.id,
        phase_quality.c.mccc_fingerprint,
        phase_quality.c.mccc_members,
    ).join(phase, phase.c.id == phase_quality.c.phase_id)
    if phase_id is not None:
        iccs_query = iccs_query.where(phase.c.id == phase_id.hex)
        mccc_query = mccc_query.where(phase.c.id == phase_id.hex)
    if event_id is not None:
        iccs_query = iccs_query.where(phase.c.event_id == event_id.hex)
        mccc_query = mccc_query.where(phase.c.event_id == event_id.hex)
    iccs = {
        uuid.UUID(hex=row_id): fingerprint
        for row_id, fingerprint in session.execute(iccs_query)
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
        digests: Mapping[uuid.UUID, PhaseDigests],
        iccs_fingerprints: Mapping[uuid.UUID, str | None],
        mccc_stamps: Mapping[uuid.UUID, tuple[str | None, Collection[str] | None]],
    ) -> None:
        """Initialise from current digests and stored fingerprints.

        Args:
            digests: Digests of every phase that will be asked about.
            iccs_fingerprints: Stored `iccs_fingerprint` by row ID.
            mccc_stamps: Stored `mccc_fingerprint` and `mccc_members` by phase ID.
        """
        self._digests = dict(digests)
        self._iccs: dict[uuid.UUID, bool] = {}
        self._mccc: dict[uuid.UUID, bool] = {}
        for phase_id, phase in digests.items():
            for row_id, digest in phase.seismogram_cc.items():
                stored = iccs_fingerprints.get(row_id)
                self._iccs[row_id] = stored is not None and stored == digest
            fingerprint, members = mccc_stamps.get(phase_id, (None, None))
            self._mccc[phase_id] = (
                fingerprint is not None
                and members is not None
                and fingerprint
                == phase.mccc([uuid.UUID(hex=member) for member in members])
            )

    @classmethod
    def read(
        cls,
        session: Session,
        phase_id: uuid.UUID | None = None,
        *,
        event_id: uuid.UUID | None = None,
    ) -> Self:
        """Compare the stored fingerprints of one phase, the phases of one event, or every phase.

        Pending changes in the session are flushed first.

        Args:
            session: Database session.
            phase_id: Phase to cover.
            event_id: Event whose phases are covered. Every phase if neither
                is given.
        """
        digests = compute_digests(session, phase_id, event_id=event_id)
        return cls(digests, *_read_fingerprints(session, phase_id, event_id))

    def digests(self, phase_id: uuid.UUID) -> PhaseDigests:
        """The current digests of a phase.

        Raises:
            KeyError: If the phase is not covered.
        """
        return self._digests[phase_id]

    def iccs_cc(self, row_id: uuid.UUID) -> bool:
        """Whether the stored `iccs_cc` of a row is valid.

        Args:
            row_id: ID of the row (`AimbatSeismogramParameters`).

        Raises:
            KeyError: If the row is not covered.
        """
        return self._iccs[row_id]

    def mccc(self, phase_id: uuid.UUID) -> bool:
        """Whether a phase's stored MCCC results are valid.

        Raises:
            KeyError: If the phase is not covered.
        """
        return self._mccc[phase_id]
