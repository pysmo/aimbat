from click.testing import CliRunner
from importlib import reload
from sqlmodel import Session


class TestLibSeismogram:
    def test_get_parameter(self, sac_file_good) -> None:  # type: ignore
        from aimbat.lib import db, project, data, seismogram

        reload(project)

        project.project_new()

        data.add_files([sac_file_good], filetype="sac")

        with Session(db.engine) as session:
            assert (
                seismogram.get_parameter(
                    session=session, seismogram_id=1, parameter_name="select"
                )
                is True
            )
            assert (
                seismogram.get_parameter(
                    session=session, seismogram_id=1, parameter_name="t1"
                )
                is None
            )
            assert (
                seismogram.get_parameter(
                    session=session, seismogram_id=1, parameter_name="t2"
                )
                is None
            )

    def test_set_parameter(self, sac_file_good) -> None:  # type: ignore
        from aimbat.lib import db, project, data, seismogram

        reload(project)

        project.project_new()

        data.add_files([sac_file_good], filetype="sac")

        with Session(db.engine) as session:
            seismogram.set_parameter(
                session=session,
                seismogram_id=1,
                parameter_name="select",
                parameter_value=False,
            )
            assert (
                seismogram.get_parameter(
                    session=session, seismogram_id=1, parameter_name="select"
                )
                is False
            )


class TestCliSeismogram:
    def test_sac_data(self, sac_file_good) -> None:  # type: ignore
        """Test AIMBAT cli with seismogram subcommand."""

        from aimbat.lib import project, data, seismogram

        reload(project)

        runner = CliRunner()

        result = runner.invoke(project.cli, ["new"])
        assert result.exit_code == 0

        result = runner.invoke(data.cli, ["add"])
        assert result.exit_code == 2

        result = runner.invoke(data.cli, ["add", sac_file_good])
        assert result.exit_code == 0

        result = runner.invoke(seismogram.cli)
        assert result.exit_code == 0
        assert "Usage" in result.output

        result = runner.invoke(seismogram.cli, ["list"])
        assert result.exit_code == 0
        assert "pytest-of" in result.output

        result = runner.invoke(seismogram.cli, ["parameter", "get", "1", "select"])
        assert result.exit_code == 0
        assert "True" in result.output

        result = runner.invoke(
            seismogram.cli, ["parameter", "set", "1", "select", "False"]
        )
        assert result.exit_code == 0

        result = runner.invoke(seismogram.cli, ["parameter", "get", "1", "select"])
        assert result.exit_code == 0
        assert "False" in result.output

        result = runner.invoke(
            seismogram.cli, ["parameter", "set", "1", "select", "yes"]
        )
        assert result.exit_code == 0

        result = runner.invoke(seismogram.cli, ["parameter", "get", "1", "select"])
        assert result.exit_code == 0
        assert "True" in result.output

        result = runner.invoke(
            seismogram.cli, ["parameter", "set", "1", "t1", "2011-11-04 00:15:23.283"]
        )
        assert result.exit_code == 0

        result = runner.invoke(seismogram.cli, ["parameter", "get", "1", "t1"])
        assert result.exit_code == 0
        assert "2011-11-04 00:15:23.283" in result.output

        result = runner.invoke(
            seismogram.cli, ["parameter", "set", "1", "t2", "2011-11-04 00:15:29.283"]
        )
        assert result.exit_code == 0

        result = runner.invoke(seismogram.cli, ["parameter", "get", "1", "t2"])
        assert result.exit_code == 0
        assert "2011-11-04 00:15:29.283" in result.output
