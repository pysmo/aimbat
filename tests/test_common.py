import pytest


def test_convert_to_type() -> None:
    from aimbat.cli.common import convert_to_type
    from aimbat.lib.typing import ProjectDefault, EventParameter, SeismogramParameter
    from datetime import datetime, timedelta

    assert convert_to_type(ProjectDefault.AIMBAT, "Yes") is True
    assert convert_to_type(ProjectDefault.AIMBAT, "no") is False
    with pytest.raises(ValueError):
        convert_to_type(ProjectDefault.AIMBAT, "foo")
    assert convert_to_type(ProjectDefault.DELTA_TOLERANCE, 10) == 10
    with pytest.raises(ValueError):
        convert_to_type(ProjectDefault.DELTA_TOLERANCE, 10.0)

    assert convert_to_type(EventParameter.COMPLETED, True) is True
    assert convert_to_type(EventParameter.WINDOW_PRE, -10) == timedelta(seconds=-10.0)
    assert convert_to_type(SeismogramParameter.SELECT, False) is False
    now = datetime.now()
    assert convert_to_type(SeismogramParameter.T1, now.isoformat()) == now
    with pytest.raises(ValueError):
        assert convert_to_type(SeismogramParameter.T1, "2025")
    with pytest.raises(ValueError):
        convert_to_type("foo", "foo")  # type: ignore
