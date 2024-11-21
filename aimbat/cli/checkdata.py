"""
Module to check seismogram files for errors before importing them into AIMBAT.
"""

from aimbat.lib.common import cli_enable_debug
from pathlib import Path
import click


def checkdata_run_checks_cli(sacfiles: list[Path]) -> None:
    """Run all checks on one or more SAC files.

    Parameters:
        sacfiles: SAC files to test.
    """

    from aimbat.lib.checkdata import (
        checkdata_event,
        checkdata_station,
        checkdata_seismogram,
    )
    from pysmo import SAC

    def checkmark() -> None:
        print("\N{CHECK MARK}", end="")

    def crossmark() -> None:
        print("\N{BALLOT X}", end="")

    all_issues = dict()

    for sacfile in sacfiles:
        issues = list()
        my_sac = SAC.from_file(str(sacfile))
        print(f"\n{sacfile}: ", end="")

        station_issues = checkdata_station(my_sac.station, called_from_cli=True)
        if len(station_issues) == 0:
            checkmark()
        else:
            issues.extend(station_issues)
            crossmark()

        event_issues = checkdata_event(my_sac.event, called_from_cli=True)
        if len(event_issues) == 0:
            checkmark()
        else:
            issues.extend(event_issues)
            crossmark()

        seismogram_issues = checkdata_seismogram(
            my_sac.seismogram, called_from_cli=True
        )
        if len(seismogram_issues) == 0:
            checkmark()
        else:
            issues.extend(seismogram_issues)
            crossmark()

        if len(issues) > 0:
            all_issues[sacfile] = issues

    if len(all_issues) == 0:
        print("\n\nNo issues found!")
        return

    print("\n\nPlease fix the following issues before proceeding:")
    for sacfile, issues in all_issues.items():
        print(f"\n file: {sacfile}:")
        for issue in issues:
            print(f"  - {issue}")


@click.command("checkdata")
@click.argument("sacfiles", nargs=-1, type=click.Path(exists=True), required=True)
@click.pass_context
def checkdata_cli(ctx: click.Context, sacfiles: list[Path]) -> None:
    """Check if there are any problems with the input SAC files."""
    cli_enable_debug(ctx)
    checkdata_run_checks_cli(sacfiles)


if __name__ == "__main__":
    checkdata_cli(obj={})
