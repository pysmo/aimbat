"""Properties of the parameter digests and the validity check."""

import uuid
from collections.abc import Mapping
from typing import Any

import pytest

from aimbat.core._validity import (
    EventDigests,
    EventInputs,
    Validity,
    encode_members,
)

_EVENT = uuid.UUID(int=0xE1)
_A = uuid.UUID(int=0xA)
_B = uuid.UUID(int=0xB)

_EVENT_PARAMETERS = {
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
    seismograms: Mapping[uuid.UUID, Mapping[str, Any]] | None = None,
    event_id: uuid.UUID = _EVENT,
) -> EventInputs:
    if seismograms is None:
        seismograms = {sid: {"flip": 0, "select": 1, "t1": None} for sid in (_A, _B)}
    return EventInputs(
        event_id=event_id.hex,
        parameters=dict(_EVENT_PARAMETERS),
        seismograms={sid.hex: dict(p) for sid, p in seismograms.items()},
    )


class TestDigests:
    """What the digests depend on."""

    def test_seismogram_order_does_not_matter(self) -> None:
        """Seismograms are sorted before hashing."""
        forward = _inputs()
        backward = EventInputs(
            event_id=forward.event_id,
            parameters=forward.parameters,
            seismograms=dict(reversed(list(forward.seismograms.items()))),
        )
        assert EventDigests.of(forward) == EventDigests.of(backward)

    def test_event_is_part_of_every_digest(self) -> None:
        """Identical parameters on two events give different digests."""
        one = EventDigests.of(_inputs())
        other = EventDigests.of(_inputs(event_id=uuid.UUID(int=0xE2)))
        assert one.stack != other.stack
        assert one.instance != other.instance
        assert one.tracked != other.tracked
        assert one.mccc({_A}) != other.mccc({_A})
        assert one.seismogram_cc[_A] != other.seismogram_cc[_A]

    def test_seismograms_with_equal_parameters_differ(self) -> None:
        """Each seismogram's CC digest names the seismogram."""
        digests = EventDigests.of(_inputs())
        assert digests.seismogram_cc[_A] != digests.seismogram_cc[_B]

    def test_mccc_members_are_a_set(self) -> None:
        """Order and repeats of the run's members do not matter."""
        digests = EventDigests.of(_inputs())
        assert digests.mccc([_A, _B]) == digests.mccc([_B, _A, _A])

    def test_mccc_depends_on_members(self) -> None:
        """A run over other seismograms has another digest."""
        digests = EventDigests.of(_inputs())
        assert digests.mccc({_A}) != digests.mccc({_A, _B})

    def test_missing_member_changes_mccc(self) -> None:
        """A member that has left the event no longer matches."""
        before = EventDigests.of(_inputs())
        after = EventDigests.of(_inputs({_B: {"flip": 0, "select": 1, "t1": None}}))
        assert before.mccc({_A, _B}) != after.mccc({_A, _B})

    def test_new_seismogram_changes_instance(self) -> None:
        """A deselected seismogram added to the event shows in the instance."""
        before = EventDigests.of(_inputs())
        after = EventDigests.of(
            _inputs(
                {
                    _A: {"flip": 0, "select": 1, "t1": None},
                    _B: {"flip": 0, "select": 1, "t1": None},
                    uuid.UUID(int=0xC): {"flip": 0, "select": 0, "t1": None},
                }
            )
        )
        assert after.stack == before.stack
        assert after.instance != before.instance
        assert after.tracked != before.tracked


class TestValidity:
    """Comparing stored fingerprints with the current digests."""

    @pytest.fixture
    def digests(self) -> EventDigests:
        return EventDigests.of(_inputs())

    def _validity(
        self,
        digests: EventDigests,
        iccs: dict[uuid.UUID, str | None] | None = None,
        mccc: tuple[str | None, list[str] | None] | None = None,
    ) -> Validity:
        return Validity({_EVENT: digests}, iccs or {}, {_EVENT: mccc or (None, None)})

    def test_iccs_cc_matching(self, digests: EventDigests) -> None:
        validity = self._validity(digests, {_A: digests.seismogram_cc[_A]})
        assert validity.iccs_cc(_A)

    def test_iccs_cc_other_seismogram(self, digests: EventDigests) -> None:
        validity = self._validity(digests, {_A: digests.seismogram_cc[_B]})
        assert not validity.iccs_cc(_A)

    @pytest.mark.parametrize(
        "iccs", [{}, {_A: None}], ids=["no-quality-row", "no-fingerprint"]
    )
    def test_iccs_cc_unstamped(
        self, digests: EventDigests, iccs: dict[uuid.UUID, str | None]
    ) -> None:
        assert not self._validity(digests, iccs).iccs_cc(_A)

    def test_iccs_cc_not_covered(self, digests: EventDigests) -> None:
        """Asking about a seismogram the digests do not cover is an error."""
        with pytest.raises(KeyError):
            self._validity(digests).iccs_cc(uuid.UUID(int=0xF))

    def test_mccc_matching(self, digests: EventDigests) -> None:
        validity = self._validity(digests, mccc=(digests.mccc({_A}), [_A.hex]))
        assert validity.mccc(_EVENT)

    def test_mccc_other_members(self, digests: EventDigests) -> None:
        stamp = (digests.mccc({_A}), [_A.hex, _B.hex])
        assert not self._validity(digests, mccc=stamp).mccc(_EVENT)

    @pytest.mark.parametrize(
        "stamp",
        [(None, [_A.hex]), ("anything", None), (None, None)],
        ids=["no-fingerprint", "no-members", "neither"],
    )
    def test_mccc_incomplete(
        self, digests: EventDigests, stamp: tuple[str | None, list[str] | None]
    ) -> None:
        assert not self._validity(digests, mccc=stamp).mccc(_EVENT)

    def test_mccc_without_quality_row(self, digests: EventDigests) -> None:
        assert not Validity({_EVENT: digests}, {}, {}).mccc(_EVENT)

    def test_mccc_not_covered(self, digests: EventDigests) -> None:
        """Asking about an event the digests do not cover is an error."""
        with pytest.raises(KeyError):
            self._validity(digests).mccc(uuid.UUID(int=0xF))


def test_encode_members() -> None:
    """Members are stored as sorted hex without duplicates."""
    assert encode_members([_B, _A, _B]) == [_A.hex, _B.hex]
