import pytest
import yaml
from aimbat.lib.defaults import AimbatDefaults


@pytest.fixture()
def local_key_dict():  # type: ignore
    """
    A small dictionary to create a local yaml file for testing
    """
    return {'delta_tolerance': 4, 'sampledata_dir': 'test_dir'}


@pytest.fixture()
def aimbat_yml_file(tmpdir_factory, local_key_dict):  # type: ignore
    filename = tmpdir_factory.mktemp("data").join("aimbat.yml")
    with open(filename, 'w+') as fh:
        yaml.dump(local_key_dict, fh)
    return str(filename)


@pytest.fixture()
def defaults(aimbat_yml_file):  # type: ignore
    """
    Create an instance of the AimbatDefaults object
    """
    global_only_defaults = AimbatDefaults(global_only=True)
    defaults_without_locals = AimbatDefaults(local_defaults_file="")
    defaults_with_locals = AimbatDefaults(local_defaults_file=aimbat_yml_file)
    return global_only_defaults, defaults_without_locals, defaults_with_locals


def test_AimbatDefaults_isinstance(defaults) -> None:  # type: ignore
    """
    Test AimbatDefaults class
    """
    global_only, without_locals, with_locals = defaults
    for d in defaults:
        assert isinstance(d, AimbatDefaults)
        assert isinstance(d.simple_dict, dict)
        assert isinstance(d.global_only, bool)
        assert isinstance(d.local_defaults_file, str)


def test_global_is_readonly(defaults) -> None:  # type: ignore
    global_defaults, *_ = defaults
    with pytest.raises(RuntimeError):
        global_defaults.delta_tolerance = 3


def test_change_data(defaults) -> None:  # type: ignore
    _, defaults, *_ = defaults
    org = defaults.delta_tolerance
    defaults.delta_tolerance = org+1
    assert defaults.delta_tolerance == org+1


@pytest.mark.depends(on=['test_change_data'])
def test_bad_type(defaults) -> None:  # type: ignore
    _, defaults, *_ = defaults
    with pytest.raises(ValueError):
        defaults.delta_tolerance = "invalid"


def test_local_changes(defaults) -> None:  # type: ignore
    *_, with_local_defaults = defaults
    assert with_local_defaults.delta_tolerance == 4
    assert with_local_defaults.sampledata_dir == "test_dir"
