from aimbat.lib.common import AimbatDataError
from pathlib import Path
from pysmo import SAC, Station, Event, Seismogram
import click


def check_station(station: Station, called_from_cli: bool = False) -> list[str]:
    """Check if station information is complete.

    Parameters:
        station: station object to test.
        called_from_cli:
            set to true to return a list of issues instead of
            raising errors.
    """
    issues = list()
    try:
        assert station.name is not None
    except (AssertionError, Exception):
        issue = "No station name found in file."
        if not called_from_cli:
            raise AimbatDataError(issue)
        issues.append(issue)

    try:
        assert station.latitude is not None
    except (AssertionError, Exception):
        issue = "No station latitude found in file."
        if not called_from_cli:
            raise AimbatDataError(issue)
        issues.append(issue)

    try:
        assert station.longitude is not None
    except (AssertionError, Exception):
        issue = "No station longitude found in file."
        if not called_from_cli:
            raise AimbatDataError(issue)
        issues.append(issue)

    return issues


def check_event(event: Event, called_from_cli: bool = False) -> list[str]:
    """Check if event information is complete.

    Parameters:
        event: event object to test.
        called_from_cli:
            set to true to return a list of issues instead of
            raising errors.
    """
    issues = list()
    try:
        assert event.latitude is not None
    except (AssertionError, Exception):
        issue = "No event latitude found in file."
        if not called_from_cli:
            raise AimbatDataError(issue)
        issues.append(issue)

    try:
        assert event.longitude is not None
    except (AssertionError, Exception):
        issue = "No event longitude found in file."
        if not called_from_cli:
            raise AimbatDataError(issue)
        issues.append(issue)

    try:
        assert event.time is not None
    except (AssertionError, Exception):
        issue = "No event time found in file."
        if not called_from_cli:
            raise AimbatDataError(issue)
        issues.append(issue)

    return issues


def check_seismogram(
    seismogram: Seismogram, called_from_cli: bool = False
) -> list[str]:
    """Check if seismogram information is complete.

    Parameters:
        seismogram: seismogram object to test.
        called_from_cli:
            set to true to return a list of issues instead of
            raising errors.
    """
    issues = list()
    try:
        assert seismogram.data is not None
        assert len(seismogram.data) > 0
    except (AssertionError, Exception):
        issue = "No seismogram data found in file."
        if not called_from_cli:
            raise AimbatDataError(issue)
        issues.append(issue)

    return issues


def run_checks_cli(sacfiles: list[Path]) -> None:
    """Run all checks on one or more SAC files.

    Parameters:
        sacfiles: SAC files to test.
    """

    def checkmark() -> None:
        print("\N{check mark}", end="")

    def crossmark() -> None:
        print("\N{ballot x}", end="")

    all_issues = dict()

    for sacfile in sacfiles:
        issues = list()
        my_sac = SAC.from_file(str(sacfile))
        print(f"\n{sacfile}: ", end="")

        station_issues = check_station(my_sac.station, called_from_cli=True)
        if len(station_issues) == 0:
            checkmark()
        else:
            issues.extend(station_issues)
            crossmark()

        event_issues = check_event(my_sac.event, called_from_cli=True)
        if len(event_issues) == 0:
            checkmark()
        else:
            issues.extend(event_issues)
            crossmark()

        seismogram_issues = check_seismogram(my_sac.seismogram, called_from_cli=True)
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
def cli(sacfiles: list[Path]) -> None:
    """Check if there are any problems with the input SAC files."""

    run_checks_cli(sacfiles)


if __name__ == "__main__":
    cli()
