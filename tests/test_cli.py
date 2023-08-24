from click.testing import CliRunner
from aimbat.lib.defaults import AimbatDefaults
from aimbat import cli
import os

_DEFAULTS = AimbatDefaults()


def test_aimbat_cli() -> None:
    """Test aimbat cli without any subcommands."""
    runner = CliRunner()
    result = runner.invoke(cli.cli)
    assert result.exit_code == 0
    assert 'Usage' in result.output
    result = runner.invoke(cli.cli, '--version')
    assert result.exit_code == 0
    assert 'aimbat, version' in result.output


def test_aimbat_cli_project() -> None:
    """Test aimbat cli without project subcommand."""
    runner = CliRunner()
    result = runner.invoke(cli.cli, 'project')
    assert result.exit_code == 0
    assert 'Usage' in result.output
    for subcommand in ['new', 'del', 'info']:
        result = runner.invoke(cli.cli, ['project', subcommand])
        assert result.exit_code == 1


def test_aimbat_defaults_cli() -> None:
    """
    Test aimbat cli with defaults subcommand.
    """
    runner = CliRunner()
    result = runner.invoke(cli.cli, 'defaults')
    assert result.exit_code == 0
    assert '+-------' in result.output
    result = runner.invoke(cli.cli, ['defaults', '--yaml'])
    assert result.exit_code == 0
    assert '---' in result.output


def test_aimbat_sampledata_cli(sampledata_dir: str = _DEFAULTS.sampledata_dir) -> None:  # type: ignore
    """
    Test aimbat cli with defaults subcommand.
    """
    runner = CliRunner()
    # force download sample data
    result = runner.invoke(cli.cli, ['sampledata', '-f'])
    assert result.exit_code == 0
    assert os.path.isdir(sampledata_dir)
    # try downloading again...
    result = runner.invoke(cli.cli, 'sampledata')
    assert result.exit_code == 1
    # remove directory
    result = runner.invoke(cli.cli, ['sampledata', '-r'])
    assert result.exit_code == 0
    assert os.path.isdir(sampledata_dir) is not True
