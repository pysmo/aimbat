from aimbat.lib.common import logger
from pysmo import (
    Station,
    Event,
    Seismogram,
)
from pathlib import Path


def checkdata_station(station: Station) -> list[str]:
    """Check if station information is complete.

    Parameters:
        station: station object to test.
    """

    logger.info("Checking station information.")

    issues = list()

    try:
        assert station.name is not None
    except (AssertionError, Exception):
        issue = "No station name found in file."
        issues.append(issue)

    try:
        assert station.latitude is not None
    except (AssertionError, Exception):
        issue = "No station latitude found in file."
        issues.append(issue)

    try:
        assert station.longitude is not None
    except (AssertionError, Exception):
        issue = "No station longitude found in file."
        issues.append(issue)

    return issues


def checkdata_event(event: Event) -> list[str]:
    """Check if event information is complete.

    Parameters:
        event: event object to test.
    """

    logger.info("Checking event information.")

    issues = list()

    try:
        assert event.latitude is not None
    except (AssertionError, Exception):
        issue = "No event latitude found in file."
        issues.append(issue)

    try:
        assert event.longitude is not None
    except (AssertionError, Exception):
        issue = "No event longitude found in file."
        issues.append(issue)

    try:
        assert event.time is not None
    except (AssertionError, Exception):
        issue = "No event time found in file."
        issues.append(issue)

    return issues


def checkdata_seismogram(seismogram: Seismogram) -> list[str]:
    """Check if seismogram information is complete.

    Parameters:
        seismogram: seismogram object to test.
    """

    logger.info("Checking seismogram information.")

    issues = list()
    try:
        assert seismogram.data is not None
        assert len(seismogram.data) > 0
    except (AssertionError, Exception):
        issue = "No seismogram data found in file."
        issues.append(issue)

    return issues


def run_checks(sacfiles: list[Path]) -> None:
    """Run all checks on one or more SAC files.

    Parameters:
        sacfiles: SAC files to test.
    """

    logger.info("Running all checks.")

    from pysmo.classes import SAC

    def checkmark() -> None:
        print("\N{CHECK MARK}", end="")

    def crossmark() -> None:
        print("\N{BALLOT X}", end="")

    all_issues = dict()

    for sacfile in sacfiles:
        issues = list()
        my_sac = SAC.from_file(str(sacfile))
        print(f"\n{sacfile}: ", end="")

        station_issues = checkdata_station(my_sac.station)
        if len(station_issues) == 0:
            checkmark()
        else:
            issues.extend(station_issues)
            crossmark()

        event_issues = checkdata_event(my_sac.event)
        if len(event_issues) == 0:
            checkmark()
        else:
            issues.extend(event_issues)
            crossmark()

        seismogram_issues = checkdata_seismogram(my_sac.seismogram)
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
