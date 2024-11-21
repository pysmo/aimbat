from pathlib import Path
from click.testing import CliRunner
import platform


class TestCliProject:
    def test_project(self) -> None:
        """Test AIMBAT cli with project subcommand."""

        from aimbat.lib.project import AIMBAT_PROJECT
        from aimbat.cli.project import project_cli

        assert not Path.exists(Path(AIMBAT_PROJECT))

        runner = CliRunner()
        result = runner.invoke(project_cli)
        assert result.exit_code == 0
        assert "Usage" in result.output

        result = runner.invoke(project_cli, ["new"])
        assert result.exit_code == 0
        assert "Created new AIMBAT project" in result.output
        assert Path.exists(Path(AIMBAT_PROJECT))

        result = runner.invoke(project_cli, ["new"])
        assert result.exit_code == 0
        assert (
            "Unable to create a new project: found existing AIMBAT_PROJECT"
            in result.output
        )

        result = runner.invoke(project_cli, ["info"])
        assert result.exit_code == 0
        assert "AIMBAT Project File:" in result.output

        # HACK - this does run on windows, but not on
        # github actions for some reason.
        if platform.system() != "Windows":
            result = runner.invoke(project_cli, ["del", "--yes"])
            assert result.exit_code == 0
            assert not Path.exists(Path(AIMBAT_PROJECT))

            result = runner.invoke(project_cli, ["del", "--yes"])
            assert result.exit_code == 0
            assert "Unable to delete project: AIMBAT_PROJECT=" in result.output

            result = runner.invoke(project_cli, ["info"])
            assert result.exit_code == 0
            assert "Unable to show info: AIMBAT_PROJECT=" in result.output
