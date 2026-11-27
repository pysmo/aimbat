"""Unit tests for carrying the TUI's phase selection between events."""

import pytest

from aimbat._tui._iccs_lifecycle import PhaseKey, carry_key


@pytest.mark.parametrize(
    ("carried", "keys", "expected"),
    [
        (("SKS", "Q"), [("SKS", "Q"), ("SKS", "T")], ("SKS", "Q")),
        (("SKS", "Q"), [("P", "Z"), ("SKS", "T")], ("SKS", "T")),
        (("SKS", "Q"), [("SKS", "L"), ("SKS", "T")], None),
        (("SKS", "Q"), [("P", "Z")], None),
        (None, [("P", "Z")], None),
    ],
)
def test_carry_key(
    carried: PhaseKey | None, keys: list[PhaseKey], expected: PhaseKey | None
) -> None:
    assert carry_key(carried, keys) == expected
