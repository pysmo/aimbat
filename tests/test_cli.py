from click.testing import CliRunner
from importlib import metadata, reload


def test_cli(monkeypatch):  # type: ignore
    """Test aimbat cli without any subcommands."""
    from aimbat import app

    runner = CliRunner()

    result = runner.invoke(app.cli)
    assert result.exit_code == 0
    assert "Usage" in result.output

    result = runner.invoke(app.cli, "--version")
    assert result.exit_code == 0
    assert "aimbat, version" in result.output

    def mock_raise(*args, **kwargs):  # type: ignore
        raise Exception

    monkeypatch.setattr(metadata, "version", mock_raise)
    _ = reload(app)

    result = runner.invoke(app.cli, "--version")
    assert result.exit_code == 0
    assert "unknown" in result.output
