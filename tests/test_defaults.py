import pytest
import dataclasses
from pysmo.aimbat.lib.defaults import AimbatDefaults, AimbatDefaultItem, AimbatConfigError


@pytest.fixture()
def defaults():
    """
    Create an instance of the AimbatDefaults object
    """
    return AimbatDefaults()


@pytest.fixture()
def default_item():
    """
    Create an instance of the AimbatDefaultItem object
    """
    return AimbatDefaultItem('abc', 123, [str, int], 'description')


def test_AimbatDefaults(defaults):
    """
    Test AimbatDefaults class
    """
    assert isinstance(defaults, AimbatDefaults)
    assert isinstance(defaults.simple_dict, dict)
    assert isinstance(defaults.items, list)
    assert isinstance(defaults.global_only, bool)
    assert isinstance(defaults.global_defaults_file, str)
    assert isinstance(defaults.local_defaults_file, str)

    for item in defaults.items:
        assert isinstance(getattr(defaults, item), AimbatDefaultItem)


def test_AimbatDefaultItemImmutable(default_item):
    """
    Test AimbatDefaultItem class immutability.
    """
    assert isinstance(default_item, AimbatDefaultItem)
    assert default_item.value == default_item.local_value
    with pytest.raises(dataclasses.FrozenInstanceError):
        default_item.global_value = 456


def test_AimbatConfigError(defaults):
    with pytest.raises(AimbatConfigError):
        raise AimbatConfigError(name='name', value='some value', local_defaults_file=defaults.local_defaults_file,
                                message="test message")
