from click.testing import CliRunner
from pysmo.aimbat import cli


def test_aimbat_cli():
    """
    Test aimbat cli without any subcommands.
    """
    runner = CliRunner()
    result = runner.invoke(cli.cli)
    assert result.exit_code == 0
    assert 'Usage' in result.output
    result = runner.invoke(cli.cli, '--version')
    assert result.exit_code == 0
    assert 'aimbat, version' in result.output


def test_aimbat_defaults_cli():
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
