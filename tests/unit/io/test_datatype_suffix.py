from pathlib import PurePath

import pytest

from aimbat.io import DataType, has_datatype_suffix


@pytest.mark.parametrize(
    "name",
    [
        "a.sac",
        "AK.BAL.--.BHZ",
        "AK.BAL.--.BHT",
        "x.bhq",
        "IU.COLA.00.BH1",
        "AK.PAX.--.LHZ",
        "XX.ABC.00.HNE",
    ],
)
def test_sac_names(name: str) -> None:
    assert has_datatype_suffix(PurePath(name), DataType.SAC)


@pytest.mark.parametrize(
    "name",
    ["a.mseed", "a.json", "a.sa", "a.BHZ1", "noext", "a.txt", "a.csv", "a.png"]
    + ["a.log", "a.xml", "a.BDF"],
)
def test_not_sac_names(name: str) -> None:
    assert not has_datatype_suffix(PurePath(name), DataType.SAC)


def test_channel_codes_only_for_sac() -> None:
    assert not has_datatype_suffix(PurePath("a.BHZ"), DataType.MSEED)
    assert has_datatype_suffix(PurePath("a.ms"), DataType.MSEED)
