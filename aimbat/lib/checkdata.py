"""
Module to check seismogram files for errors before importing them into AIMBAT.
"""

from aimbat.lib.common import ic
from aimbat.lib.common import AimbatDataError
from pysmo import Station, Event, Seismogram


def checkdata_station(station: Station, called_from_cli: bool = False) -> list[str]:
    """Check if station information is complete.

    Parameters:
        station: station object to test.
        called_from_cli:
            set to true to return a list of issues instead of
            raising errors.
    """
    ic()

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

    ic(issues)
    return issues


def checkdata_event(event: Event, called_from_cli: bool = False) -> list[str]:
    """Check if event information is complete.

    Parameters:
        event: event object to test.
        called_from_cli:
            set to true to return a list of issues instead of
            raising errors.
    """

    ic()

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

    ic(issues)
    return issues


def checkdata_seismogram(
    seismogram: Seismogram, called_from_cli: bool = False
) -> list[str]:
    """Check if seismogram information is complete.

    Parameters:
        seismogram: seismogram object to test.
        called_from_cli:
            set to true to return a list of issues instead of
            raising errors.
    """

    ic()

    issues = list()
    try:
        assert seismogram.data is not None
        assert len(seismogram.data) > 0
    except (AssertionError, Exception):
        issue = "No seismogram data found in file."
        if not called_from_cli:
            raise AimbatDataError(issue)
        issues.append(issue)

    ic(issues)
    return issues
