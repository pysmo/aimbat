import pytest
from importlib import reload


class TestLibDefaults:
    def test_defaults(self) -> None:
        from aimbat.lib import project, defaults

        _ = reload(project)

        # test itens also present in aimbat/lib/defaults.yml
        test_items = {
            "_test_bool": True,
            "_test_float": 0.1,
            "_test_int": 1,
            "_test_str": "test",
        }

        # an AIMBAT default that doesn't exist
        test_invalid_name = "asdfasdjfasdfasdfasdfjhalksdfhsalhfd"

        # used to test setting to new values
        test_items_set = {
            "_test_bool": False,
            "_test_float": 0.2,
            "_test_int": 2,
            "_test_str": "TEST",
        }

        # used to test setting to new values
        test_items_invalid_type = {
            "_test_bool": "blah",
            "_test_float": "blah",
            "_test_int": "blah",
        }

        project.project_new()

        # get a valid default item
        for key, val in test_items.items():
            assert defaults.defaults_get_value(name=key) == val

        # get one that doesn't exist
        with pytest.raises(RuntimeError):
            _ = defaults.defaults_get_value(name=test_invalid_name)

        # set to new value
        for key, val in test_items_set.items():
            defaults.defaults_set_value(name=key, value=val)  # type: ignore
            assert defaults.defaults_get_value(name=key) == val

        # set to incorrect type
        for key, val in test_items_invalid_type.items():
            with pytest.raises(ValueError):
                defaults.defaults_set_value(name=key, value=val)

        # use invalid name
        with pytest.raises(RuntimeError):
            defaults.defaults_set_value(name=test_invalid_name, value=False)

        # reset to defaults
        for key, val in test_items.items():
            defaults.defaults_reset_value(name=key)
            assert defaults.defaults_get_value(name=key) == val
