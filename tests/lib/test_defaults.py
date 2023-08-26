from aimbat.lib import defaults as lib
import pytest


@pytest.mark.depends(depends=["tests/lib/test_project.py::TestProject.test_lib_project"],
                     scope="session")
class TestDefaults:

    @pytest.mark.usefixtures("tmp_project_engine")
    def test_lib_defaults(self, tmp_project_engine):  # type: ignore

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
            assert lib.defaults_get_value(engine=tmp_project_engine, name=key) == val

        # get one that doesn't exist
        with pytest.raises(lib.AimbatDefaultNotFound):
            lib.defaults_get_value(engine=tmp_project_engine, name=test_invalid_name)

        # set to new value
        for key, val in test_items_set.items():
            lib.defaults_set_value(engine=tmp_project_engine, name=key, value=val)
            assert lib.defaults_get_value(engine=tmp_project_engine, name=key) == val

        # try different ways of setting _test_bool to True
        for val in test_bool_true:
            lib.defaults_set_value(engine=tmp_project_engine, name="_test_bool", value=val)
            assert lib.defaults_get_value(engine=tmp_project_engine, name="_test_bool") is True

        # try different ways of setting _test_bool to False
        for val in test_bool_false:
            lib.defaults_set_value(engine=tmp_project_engine, name="_test_bool", value=val)
            assert lib.defaults_get_value(engine=tmp_project_engine, name="_test_bool") is False

        # set to incorrect type
        for key, val in test_items_invalid_type.items():
            with pytest.raises(lib.AimbatDefaultTypeError):
                lib.defaults_set_value(engine=tmp_project_engine, name=key, value=val)

        # use invalid name
        with pytest.raises(lib.AimbatDefaultNotFound):
            lib.defaults_set_value(engine=tmp_project_engine, name=test_invalid_name, value=False)

        # reset to defaults
        for key, val in test_items.items():
            lib.defaults_reset_value(engine=tmp_project_engine, name=key)
            assert lib.defaults_get_value(engine=tmp_project_engine, name=key) == val
