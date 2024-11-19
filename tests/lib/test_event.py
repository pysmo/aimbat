from click.testing import CliRunner
from importlib import reload
from sqlmodel import Session
from datetime import timedelta
from random import randrange


class TestLibEvent:
    def test_get_parameter(self, sac_file_good) -> None:  # type: ignore
        from aimbat.lib import db, project, data, event

        reload(project)

        project.project_new()

        data.data_add_files([sac_file_good], filetype="sac")

        with Session(db.engine) as session:
            assert event.get_parameter(
                session=session, event_id=1, parameter_name="window_pre"
            ) == timedelta(seconds=-7.5)
            assert event.get_parameter(
                session=session, event_id=1, parameter_name="window_post"
            ) == timedelta(seconds=7.5)

    def test_set_parameter(self, sac_file_good) -> None:  # type: ignore
        from aimbat.lib import db, project, data, event

        reload(project)

        project.project_new()

        data.data_add_files([sac_file_good], filetype="sac")

        with Session(db.engine) as session:
            window_post_new = timedelta(seconds=randrange(10))
            event.set_parameter(
                session=session,
                event_id=1,
                parameter_name="window_post",
                parameter_value=window_post_new,
            )
            assert (
                event.get_parameter(
                    session=session, event_id=1, parameter_name="window_post"
                )
                == window_post_new
            )


class TestCliEvent:
    def test_sac_data(self, sac_file_good) -> None:  # type: ignore
        """Test AIMBAT cli with event subcommand."""

        from aimbat.lib import project, data, event

        reload(project)

        runner = CliRunner()

        result = runner.invoke(project.cli, ["new"])
        assert result.exit_code == 0

        result = runner.invoke(data.cli_data, ["add"])
        assert result.exit_code == 2

        result = runner.invoke(data.cli_data, ["add", sac_file_good])
        assert result.exit_code == 0

        result = runner.invoke(event.cli)
        assert result.exit_code == 0
        assert "Usage" in result.output

        result = runner.invoke(event.cli, ["list"])
        assert result.exit_code == 0
        assert "2011-09-15 19:31:04.080000" in result.output

        result = runner.invoke(
            event.cli, ["parameter", "set", "1", "window_pre", "--", "-2.3"]
        )
        assert result.exit_code == 0

        result = runner.invoke(event.cli, ["parameter", "get", "1", "window_pre"])
        assert result.exit_code == 0
        assert "-1 day, 23:59:57.7" in result.output

        result = runner.invoke(
            event.cli, ["parameter", "set", "1", "window_post", "--", "5.3"]
        )
        assert result.exit_code == 0

        result = runner.invoke(event.cli, ["parameter", "get", "1", "window_post"])
        assert result.exit_code == 0
        assert "0:00:05.3" in result.output

        result = runner.invoke(
            event.cli,
            [
                "parameter",
                "set",
                "1",
                "window_pre",
                "--",
                "cannot_convert_this_to_float",
            ],
        )
        assert result.exit_code == 1
        assert result.exception
