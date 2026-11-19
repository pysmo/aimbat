"""Properties of the parameter digests and the validity check."""

import uuid
from collections.abc import Mapping
from typing import Any

import pytest

from aimbat.core._validity import (
    PhaseDigests,
    PhaseInputs,
    Validity,
    encode_members,
)

_PHASE = uuid.UUID(int=0xE1)
_A = uuid.UUID(int=0xA)
_B = uuid.UUID(int=0xB)

_PHASE_PARAMETERS = {
    "completed": 0,
    "ramp_width": 0.1,
    "window_pre": -15_000_000_000,
    "window_post": 15_000_000_000,
    "bandpass_apply": 1,
    "bandpass_fmin": 0.05,
    "bandpass_fmax": 2.0,
    "corners": 2,
    "min_cc": 0.5,
    "mccc_damp": 0.1,
    "mccc_min_cc": 0.5,
}


def _inputs(
    rows: Mapping[uuid.UUID, Mapping[str, Any]] | None = None,
    phase_id: uuid.UUID = _PHASE,
) -> PhaseInputs:
    if rows is None:
        rows = {sid: {"flip": 0, "select": 1, "refined_pick": None} for sid in (_A, _B)}
    return PhaseInputs(
        phase_id=phase_id.hex,
        parameters=dict(_PHASE_PARAMETERS),
        rows={sid.hex: dict(p) for sid, p in rows.items()},
    )


class TestDigests:
    """What the digests depend on."""

    def test_row_order_does_not_matter(self) -> None:
        """Rows are sorted before hashing."""
        forward = _inputs()
        backward = PhaseInputs(
            phase_id=forward.phase_id,
            parameters=forward.parameters,
            rows=dict(reversed(list(forward.rows.items()))),
        )
        assert PhaseDigests.of(forward) == PhaseDigests.of(backward)

    def test_phase_is_part_of_every_digest(self) -> None:
        """Identical parameters on two phases give different digests."""
        one = PhaseDigests.of(_inputs())
        other = PhaseDigests.of(_inputs(phase_id=uuid.UUID(int=0xE2)))
        assert one.stack != other.stack
        assert one.instance != other.instance
        assert one.tracked != other.tracked
        assert one.mccc({_A}) != other.mccc({_A})
        assert one.seismogram_cc[_A] != other.seismogram_cc[_A]

    def test_rows_with_equal_parameters_differ(self) -> None:
        """Each row's CC digest names the row."""
        digests = PhaseDigests.of(_inputs())
        assert digests.seismogram_cc[_A] != digests.seismogram_cc[_B]

    def test_mccc_members_are_a_set(self) -> None:
        """Order and repeats of the run's members do not matter."""
        digests = PhaseDigests.of(_inputs())
        assert digests.mccc([_A, _B]) == digests.mccc([_B, _A, _A])

    def test_mccc_depends_on_members(self) -> None:
        """A run over other rows has another digest."""
        digests = PhaseDigests.of(_inputs())
        assert digests.mccc({_A}) != digests.mccc({_A, _B})

    def test_missing_member_changes_mccc(self) -> None:
        """A member that has left the phase no longer matches."""
        before = PhaseDigests.of(_inputs())
        after = PhaseDigests.of(
            _inputs({_B: {"flip": 0, "select": 1, "refined_pick": None}})
        )
        assert before.mccc({_A, _B}) != after.mccc({_A, _B})

    def test_new_row_changes_instance(self) -> None:
        """A deselected row added to the phase shows in the instance."""
        before = PhaseDigests.of(_inputs())
        after = PhaseDigests.of(
            _inputs(
                {
                    _A: {"flip": 0, "select": 1, "refined_pick": None},
                    _B: {"flip": 0, "select": 1, "refined_pick": None},
                    uuid.UUID(int=0xC): {"flip": 0, "select": 0, "refined_pick": None},
                }
            )
        )
        assert after.stack == before.stack
        assert after.instance != before.instance
        assert after.tracked != before.tracked


class TestValidity:
    """Comparing stored fingerprints with the current digests."""

    @pytest.fixture
    def digests(self) -> PhaseDigests:
        return PhaseDigests.of(_inputs())

    def _validity(
        self,
        digests: PhaseDigests,
        iccs: dict[uuid.UUID, str | None] | None = None,
        mccc: tuple[str | None, list[str] | None] | None = None,
    ) -> Validity:
        return Validity({_PHASE: digests}, iccs or {}, {_PHASE: mccc or (None, None)})

    def test_iccs_cc_matching(self, digests: PhaseDigests) -> None:
        validity = self._validity(digests, {_A: digests.seismogram_cc[_A]})
        assert validity.iccs_cc(_A)

    def test_iccs_cc_other_row(self, digests: PhaseDigests) -> None:
        validity = self._validity(digests, {_A: digests.seismogram_cc[_B]})
        assert not validity.iccs_cc(_A)

    @pytest.mark.parametrize(
        "iccs", [{}, {_A: None}], ids=["no-quality-row", "no-fingerprint"]
    )
    def test_iccs_cc_unstamped(
        self, digests: PhaseDigests, iccs: dict[uuid.UUID, str | None]
    ) -> None:
        assert not self._validity(digests, iccs).iccs_cc(_A)

    def test_iccs_cc_not_covered(self, digests: PhaseDigests) -> None:
        """Asking about a row the digests do not cover is an error."""
        with pytest.raises(KeyError):
            self._validity(digests).iccs_cc(uuid.UUID(int=0xF))

    def test_mccc_matching(self, digests: PhaseDigests) -> None:
        validity = self._validity(digests, mccc=(digests.mccc({_A}), [_A.hex]))
        assert validity.mccc(_PHASE)

    def test_mccc_other_members(self, digests: PhaseDigests) -> None:
        stamp = (digests.mccc({_A}), [_A.hex, _B.hex])
        assert not self._validity(digests, mccc=stamp).mccc(_PHASE)

    @pytest.mark.parametrize(
        "stamp",
        [(None, [_A.hex]), ("anything", None), (None, None)],
        ids=["no-fingerprint", "no-members", "neither"],
    )
    def test_mccc_incomplete(
        self, digests: PhaseDigests, stamp: tuple[str | None, list[str] | None]
    ) -> None:
        assert not self._validity(digests, mccc=stamp).mccc(_PHASE)

    def test_mccc_without_quality_row(self, digests: PhaseDigests) -> None:
        assert not Validity({_PHASE: digests}, {}, {}).mccc(_PHASE)

    def test_mccc_not_covered(self, digests: PhaseDigests) -> None:
        """Asking about a phase the digests do not cover is an error."""
        with pytest.raises(KeyError):
            self._validity(digests).mccc(uuid.UUID(int=0xF))


def test_encode_members() -> None:
    """Members are stored as sorted hex without duplicates."""
    assert encode_members([_B, _A, _B]) == [_A.hex, _B.hex]
