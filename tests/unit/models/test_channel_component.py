import pytest

from aimbat.models import AimbatStation, channel_component, phase_component


@pytest.mark.parametrize(
    ("channel", "component"),
    [("BHZ", "Z"), ("BH1", "1"), ("bhn", "N"), ("HHT", "T"), ("LHE", "E")],
)
def test_component_of_seed_codes(channel: str, component: str) -> None:
    assert channel_component(channel) == component


@pytest.mark.parametrize("channel", ["", "Z", "BHZ1", "BH-", "BHÉ"])
def test_no_component_for_other_codes(channel: str) -> None:
    assert channel_component(channel) is None


@pytest.mark.parametrize(("channel", "component"), [("BHQ", "Q"), ("BH-", "")])
def test_phase_component(channel: str, component: str) -> None:
    station = AimbatStation(
        network="XX",
        name="ABC",
        location="00",
        channel=channel,
        latitude=0,
        longitude=0,
    )
    assert phase_component(station) == component
