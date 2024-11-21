from sqlmodel import Session, select
from click.testing import CliRunner
from importlib import reload
from aimbat.lib.models import AimbatFile


class TestCliData:
    def test_sac_data(self, sac_file_good) -> None:  # type: ignore
        """Test AIMBAT cli with data subcommand."""

        from aimbat.lib import db
        from aimbat.cli import data, project

        reload(project)

        runner = CliRunner()

        result = runner.invoke(project.project_cli, ["new"])
        assert result.exit_code == 0

        result = runner.invoke(data.data_cli)
        assert result.exit_code == 0
        assert "Usage" in result.output

        result = runner.invoke(data.data_cli, ["add"])
        assert result.exit_code == 2

        result = runner.invoke(data.data_cli, ["add", sac_file_good])
        assert result.exit_code == 0
        with Session(db.engine) as session:
            test_file = session.exec(select(AimbatFile)).one()
            assert test_file.filename == sac_file_good

        result = runner.invoke(data.data_cli, ["list"])
        assert result.exit_code == 0
