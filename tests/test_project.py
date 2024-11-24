from typer.testing import CliRunner
import platform
import pytest


class TestLibProject:
    def test_project(self, db_engine) -> None:  # type: ignore
        from aimbat.lib import project

        project.create_project(db_engine)

        with pytest.raises(RuntimeError):
            project.create_project(db_engine)

        project.print_project_info(db_engine)

        # HACK - this does run on windows, but not on
        # github actions for some reason.
        if platform.system() != "Windows":
            project.delete_project(db_engine)

            with pytest.raises(RuntimeError):
                project.delete_project(db_engine)


class TestCliProject:
    def test_project(self, db_url: str) -> None:
        """Test AIMBAT cli with project subcommand."""

        from aimbat.app import app

        runner = CliRunner()
        result = runner.invoke(app)
        assert result.exit_code == 0
        assert "Usage" in result.output

        result = runner.invoke(app, ["--db-url", db_url, "project", "create"])
        print(result.output)
        assert result.exit_code == 0

        result = runner.invoke(app, ["--db-url", db_url, "project", "create"])
        assert result.exit_code == 1

        result = runner.invoke(app, ["--db-url", db_url, "project", "info"])
        assert result.exit_code == 0
        assert "AIMBAT Project File:" in result.stdout

        # HACK - this does run on windows, but not on
        # github actions for some reason.
        if platform.system() != "Windows":
            result = runner.invoke(app, ["--db-url", db_url, "project", "delete"])
            assert result.exit_code == 0

            result = runner.invoke(app, ["--db-url", db_url, "project", "delete"])
            assert result.exit_code == 1

            result = runner.invoke(app, ["--db-url", db_url, "project", "info"])
            assert result.exit_code == 1
