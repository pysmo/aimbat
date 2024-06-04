from sqlmodel import Session
from click.testing import CliRunner
from datetime import timedelta
from importlib import reload


class TestLibParameter:
    def test_get_parameter(self, sac_file_good) -> None:  # type: ignore
        from aimbat.lib import db, project, data, parameter

        reload(project)

        project.project_new()

        data.add_files([sac_file_good], filetype="sac")

        with Session(db.engine) as session:
            assert (
                parameter.get_parameter(
                    session=session, seismogram_id=1, parameter_name="select"
                )
                is True
            )
            assert (
                parameter.get_parameter(
                    session=session, seismogram_id=1, parameter_name="t1"
                )
                is None
            )
            assert (
                parameter.get_parameter(
                    session=session, seismogram_id=1, parameter_name="t2"
                )
                is None
            )
            assert parameter.get_parameter(
                session=session, seismogram_id=1, parameter_name="window_pre"
            ) == timedelta(seconds=-7.5)
            assert parameter.get_parameter(
                session=session, seismogram_id=1, parameter_name="window_post"
            ) == timedelta(seconds=7.5)

    def test_set_parameter(self, sac_file_good) -> None:  # type: ignore
        from aimbat.lib import db, project, data, parameter

        reload(project)

        project.project_new()

        data.add_files([sac_file_good], filetype="sac")

        with Session(db.engine) as session:
            parameter.set_parameter(
                session=session,
                seismogram_id=1,
                parameter_name="select",
                parameter_value=False,
            )
            assert (
                parameter.get_parameter(
                    session=session, seismogram_id=1, parameter_name="select"
                )
                is False
            )


class TestCliParamter:
    def test_get_parameter(self, sac_file_good) -> None:  # type: ignore
        """Test AIMBAT cli with parameter subcommand."""

        from aimbat.lib import project, data, parameter

        reload(project)

        runner = CliRunner()

        result = runner.invoke(project.cli, ["new"])
        assert result.exit_code == 0

        result = runner.invoke(parameter.cli)
        assert result.exit_code == 0
        assert "Usage" in result.output

        result = runner.invoke(data.cli, ["add", sac_file_good])
        assert result.exit_code == 0

        result = runner.invoke(parameter.cli, ["get", "1", "select"])
        assert result.exit_code == 0
        assert "True" in result.output

        result = runner.invoke(parameter.cli, ["set", "1", "select", "False"])
        assert result.exit_code == 0

        result = runner.invoke(parameter.cli, ["get", "1", "select"])
        assert result.exit_code == 0
        assert "False" in result.output

        result = runner.invoke(parameter.cli, ["set", "1", "select", "yes"])
        assert result.exit_code == 0

        result = runner.invoke(parameter.cli, ["get", "1", "select"])
        assert result.exit_code == 0
        assert "True" in result.output

        result = runner.invoke(
            parameter.cli, ["set", "1", "t1", "2011-11-04 00:15:23.283"]
        )
        assert result.exit_code == 0

        result = runner.invoke(parameter.cli, ["get", "1", "t1"])
        assert result.exit_code == 0
        assert "2011-11-04 00:15:23.283" in result.output

        result = runner.invoke(
            parameter.cli, ["set", "1", "t2", "2011-11-04 00:15:29.283"]
        )
        assert result.exit_code == 0

        result = runner.invoke(parameter.cli, ["get", "1", "t2"])
        assert result.exit_code == 0
        assert "2011-11-04 00:15:29.283" in result.output

        result = runner.invoke(parameter.cli, ["set", "1", "window_pre", "--", "-2.3"])
        assert result.exit_code == 0

        result = runner.invoke(parameter.cli, ["get", "1", "window_pre"])
        assert result.exit_code == 0
        assert "-1 day, 23:59:57.7" in result.output

        result = runner.invoke(parameter.cli, ["set", "1", "window_post", "--", "5.3"])
        assert result.exit_code == 0

        result = runner.invoke(parameter.cli, ["get", "1", "window_post"])
        assert result.exit_code == 0
        assert "0:00:05.3" in result.output

        result = runner.invoke(
            parameter.cli,
            ["set", "1", "window_pre", "--", "cannot_convert_this_to_float"],
        )
        assert result.exit_code == 1
        assert result.exception
