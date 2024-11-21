from click.testing import CliRunner
from importlib import reload
import uuid


class TestCliSnapshot:
    def test_sac_data(self, sac_file_good) -> None:  # type: ignore
        """Test AIMBAT cli with snapshot subcommand."""

        from aimbat.cli import data, project, snapshot

        runner = CliRunner()

        result = runner.invoke(project.project_cli, ["new"])
        assert result.exit_code == 0

        result = runner.invoke(data.data_cli, ["add", sac_file_good])
        assert result.exit_code == 0

        result = runner.invoke(snapshot.snapshot_cli)
        assert result.exit_code == 0
        assert "Usage" in result.output

        result = runner.invoke(snapshot.snapshot_cli, ["list"])
        assert result.exit_code == 0
        assert "AIMBAT Snapshots" in result.output

        random_comment = str(uuid.uuid4())
        result = runner.invoke(
            snapshot.snapshot_cli, ["create", "1", "-c", random_comment]
        )
        assert result.exit_code == 0

        result = runner.invoke(snapshot.snapshot_cli, ["list"])
        assert result.exit_code == 0

        result = runner.invoke(snapshot.snapshot_cli, ["delete", "1"])
        assert result.exit_code == 0
        assert random_comment not in result.output
