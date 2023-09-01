from click.testing import CliRunner
import pytest


@pytest.mark.depends(depends=["tests/lib/test_project.py::TestProject.test_lib_project"],
                     scope="session")
@pytest.mark.usefixtures("tmp_project")
class TestDefaults:

    def test_lib_defaults(self) -> None:

        from aimbat.lib import defaults

        # test itens also present in aimbat/lib/defaults.yml
        test_items = {"_test_bool": True, "_test_float": 0.1,
                      "_test_int": 1, "_test_str": "test"}

        # an AIMBAT default that doesn't exist
        test_invalid_name = "asdfasdjfasdfasdfasdfjhalksdfhsalhfd"

        # used to test setting to new values
        test_items_set = {"_test_bool": False, "_test_float": 0.2,
                          "_test_int": 2, "_test_str": "TEST"}

        # booleans are a bit more flexible...
        test_bool_true = [True, "yes", 1]
        test_bool_false = [False, "no", 0]

        # used to test setting to new values
        test_items_invalid_type = {"_test_bool": "blah", "_test_float": "blah",
                                   "_test_int": "blah"}

        # get a valid default item
        for key, val in test_items.items():
            assert defaults.defaults_get_value(name=key) == val

        # get one that doesn't exist
        with pytest.raises(defaults.AimbatDefaultNotFound):
            defaults.defaults_get_value(name=test_invalid_name)

        # set to new value
        for key, val in test_items_set.items():
            defaults.defaults_set_value(name=key, value=val)  # type: ignore
            assert defaults.defaults_get_value(name=key) == val

        # try different ways of setting _test_bool to True
        for val in test_bool_true:
            defaults.defaults_set_value(name="_test_bool", value=val)  # type: ignore
            assert defaults.defaults_get_value(name="_test_bool") is True

        # try different ways of setting _test_bool to False
        for val in test_bool_false:
            defaults.defaults_set_value(name="_test_bool", value=val)  # type: ignore
            assert defaults.defaults_get_value(name="_test_bool") is False

        # set to incorrect type
        for key, val in test_items_invalid_type.items():
            with pytest.raises(defaults.AimbatDefaultTypeError):
                defaults.defaults_set_value(name=key, value=val)

        # use invalid name
        with pytest.raises(defaults.AimbatDefaultNotFound):
            defaults.defaults_set_value(name=test_invalid_name, value=False)

        # reset to defaults
        for key, val in test_items.items():
            defaults.defaults_reset_value(name=key)
            assert defaults.defaults_get_value(name=key) == val


@pytest.mark.depends(depends=["TestProject.test_lib_defaults",
                              "test_cli_project"], scope="session")
@pytest.mark.usefixtures("tmp_project")
def test_cli_defaults() -> None:
    """Test AIMBAT cli with defaults subcommand."""

    from aimbat.lib import defaults

    runner = CliRunner()
    result = runner.invoke(defaults.cli)
    assert result.exit_code == 0
    assert 'Usage' in result.output

    result = runner.invoke(defaults.cli, ["list"])
    assert result.exit_code == 0
    for val in ["Name", "Value", "Description"]:
        assert val in result.output

    result = runner.invoke(defaults.cli, ["list", "aimbat"])
    assert result.exit_code == 0
    assert "True" in result.output

    result = runner.invoke(defaults.cli, ["set", "aimbat", "False"])
    assert result.exit_code == 0

    result = runner.invoke(defaults.cli, ["list", "aimbat"])
    assert result.exit_code == 0
    assert "False" in result.output

    result = runner.invoke(defaults.cli, ["reset", "aimbat"])
    assert result.exit_code == 0

    result = runner.invoke(defaults.cli, ["list", "aimbat"])
    assert result.exit_code == 0
    assert "True" in result.output
