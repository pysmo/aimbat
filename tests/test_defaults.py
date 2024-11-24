import pytest
from typer.testing import CliRunner


class TestLibDefaults:
    def test_defaults(self, db_session) -> None:  # type: ignore
        from aimbat.lib import defaults

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

        # project.create_project()

        # get a valid default item
        for key, val in test_items.items():
            assert defaults.get_default(db_session, name=key) == val

        # get one that doesn't exist
        with pytest.raises(RuntimeError):
            _ = defaults.get_default(db_session, name=test_invalid_name)

        # set to new value
        for key, val in test_items_set.items():
            defaults.set_default(db_session, name=key, value=val)  # type: ignore
            assert defaults.get_default(db_session, name=key) == val

        # set to incorrect type
        for key, val in test_items_invalid_type.items():
            with pytest.raises(ValueError):
                defaults.set_default(db_session, name=key, value=val)

        # use invalid name
        with pytest.raises(RuntimeError):
            defaults.set_default(db_session, name=test_invalid_name, value=False)

        # reset to defaults
        for key, val in test_items.items():
            defaults.reset_default(db_session, name=key)
            assert defaults.get_default(db_session, name=key) == val


class TestCliDefaults:
    def test_defaults(self, db_url) -> None:  # type: ignore
        """Test AIMBAT cli with defaults subcommand."""

        from aimbat.app import app

        runner = CliRunner()
        result = runner.invoke(app, ["--db-url", db_url, "defaults"])
        assert result.exit_code == 0
        assert "Usage" in result.output

        result = runner.invoke(app, ["--db-url", db_url, "project", "create"])
        assert result.exit_code == 0

        result = runner.invoke(app, ["--db-url", db_url, "defaults", "list"])
        assert result.exit_code == 0
        for val in ["Name", "Value", "Description"]:
            assert val in result.output

        result = runner.invoke(app, ["--db-url", db_url, "defaults", "list", "aimbat"])
        assert result.exit_code == 0
        assert "True" in result.output

        # booleans are a bit more flexible...
        test_bool_true = ["True", "yes", "1"]
        test_bool_false = ["False", "no", "0"]
        for i in test_bool_true:
            result = runner.invoke(
                app, ["--db-url", db_url, "defaults", "set", "aimbat", i]
            )
            assert result.exit_code == 0
            result = runner.invoke(
                app, ["--db-url", db_url, "defaults", "list", "aimbat"]
            )
            assert result.exit_code == 0
            assert "True" in result.output
        for i in test_bool_false:
            result = runner.invoke(
                app, ["--db-url", db_url, "defaults", "set", "aimbat", i]
            )
            assert result.exit_code == 0
            result = runner.invoke(
                app, ["--db-url", db_url, "defaults", "list", "aimbat"]
            )
            assert result.exit_code == 0
            assert "False" in result.output

        result = runner.invoke(app, ["--db-url", db_url, "defaults", "reset", "aimbat"])
        assert result.exit_code == 0

        result = runner.invoke(app, ["--db-url", db_url, "defaults", "list", "aimbat"])
        assert result.exit_code == 0
        assert "True" in result.output
