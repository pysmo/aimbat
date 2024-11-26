from typer.testing import CliRunner
from aimbat.lib import data, seismogram
from aimbat.app import app


class TestLibSeismogram:
    def test_get_parameter(self, db_session, test_data) -> None:  # type: ignore
        data.add_files_to_project(db_session, test_data, filetype="sac")

        assert (
            seismogram.get_seismogram_parameter(
                session=db_session, seismogram_id=1, parameter_name="select"
            )
            is True
        )
        assert (
            seismogram.get_seismogram_parameter(
                session=db_session, seismogram_id=1, parameter_name="t1"
            )
            is None
        )
        assert (
            seismogram.get_seismogram_parameter(
                session=db_session, seismogram_id=1, parameter_name="t2"
            )
            is None
        )

    def test_set_parameter(self, db_session, test_data) -> None:  # type: ignore
        data.add_files_to_project(db_session, test_data, filetype="sac")

        seismogram.set_seismogram_parameter(
            session=db_session,
            seismogram_id=1,
            parameter_name="select",
            parameter_value=False,
        )
        assert (
            seismogram.get_seismogram_parameter(
                session=db_session, seismogram_id=1, parameter_name="select"
            )
            is False
        )


class TestCliSeismogram:
    def test_sac_data(self, db_url, test_data_string, monkeypatch) -> None:  # type: ignore
        """Test AIMBAT cli with seismogram subcommand."""

        monkeypatch.setenv("COLUMNS", "1000")

        runner = CliRunner()

        result = runner.invoke(app, "seismogram")
        assert result.exit_code == 0
        assert "Usage" in result.output

        result = runner.invoke(app, ["--db-url", db_url, "project", "create"])
        assert result.exit_code == 0

        args = ["--db-url", db_url, "data", "add"]
        args.extend(test_data_string)
        result = runner.invoke(app, args)
        assert result.exit_code == 0

        result = runner.invoke(
            app, ["--db-url", db_url, "seismogram", "get", "1", "select"]
        )
        assert result.exit_code == 0
        assert "True" in result.output

        result = runner.invoke(
            app, ["--db-url", db_url, "seismogram", "set", "1", "select", "False"]
        )
        assert result.exit_code == 0

        result = runner.invoke(
            app, ["--db-url", db_url, "seismogram", "get", "1", "select"]
        )
        assert result.exit_code == 0
        assert "False" in result.output

        result = runner.invoke(
            app, ["--db-url", db_url, "seismogram", "set", "1", "select", "yes"]
        )
        assert result.exit_code == 0

        result = runner.invoke(
            app,
            ["--db-url", db_url, "seismogram", "set", "1", "select", "noooooooooooooo"],
        )
        assert result.exit_code == 1

        result = runner.invoke(
            app, ["--db-url", db_url, "seismogram", "get", "1", "select"]
        )
        assert result.exit_code == 0
        assert "True" in result.output

        result = runner.invoke(
            app,
            [
                "--db-url",
                db_url,
                "seismogram",
                "set",
                "1",
                "t1",
                "2011-11-04 00:15:23.283",
            ],
        )
        assert result.exit_code == 0

        result = runner.invoke(
            app, ["--db-url", db_url, "seismogram", "get", "1", "t1"]
        )
        assert result.exit_code == 0
        assert "2011-11-04 00:15:23.283" in result.output

        result = runner.invoke(
            app,
            [
                "--db-url",
                db_url,
                "seismogram",
                "set",
                "1",
                "t2",
                "2011-11-04 00:15:29.283",
            ],
        )
        assert result.exit_code == 0

        result = runner.invoke(
            app, ["--db-url", db_url, "seismogram", "get", "1", "t2"]
        )
        assert result.exit_code == 0
        assert "2011-11-04 00:15:29.283" in result.output

        result = runner.invoke(app, ["--db-url", db_url, "seismogram", "list"])
        assert result.exit_code == 1

        result = runner.invoke(app, ["--db-url", db_url, "seismogram", "list", "--all"])
        assert result.exit_code == 0
        assert test_data_string[0] in result.output

        result = runner.invoke(app, ["--db-url", db_url, "event", "activate", "1"])
        assert result.exit_code == 0

        result = runner.invoke(app, ["--db-url", db_url, "seismogram", "list"])
        assert result.exit_code == 0
