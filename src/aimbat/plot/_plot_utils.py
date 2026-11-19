"""Prepare seismogram data for plotting."""

import uuid

import pandas as pd

from pysmo import MiniSeismogram
from pysmo.functions import clone_to_mini, detrend, normalize, resample
from pysmo.tools.azdist import distance
from pysmo.tools.signal import bandpass

from aimbat.logger import logger
from aimbat.models import (
    AimbatEvent,
    AimbatPhase,
    AimbatSeismogramParameters,
    AimbatStation,
)

__all__ = ["clean_timedelta", "event_seismograms", "station_seismograms"]

_RESAMPLE_DELTA = pd.Timedelta(0.1, unit="s")


def clean_timedelta(x: float, _: int | None) -> str:
    """Format elapsed seconds as `[-]MM:SS` for a matplotlib tick formatter."""
    sign = "-" if x < 0 else ""
    total_seconds = abs(int(x))
    minutes, seconds = divmod(total_seconds, 60)
    return f"{sign}{minutes:02d}:{seconds:02d}"


def _prepare_seismogram_for_plotting(row: AimbatSeismogramParameters) -> MiniSeismogram:
    """Prepare a copy of a seismogram for plotting.

    Removes any linear trend, applies the phase's bandpass filter if enabled,
    resamples to a fixed sample interval, and normalises the amplitude by its
    absolute maximum.

    Args:
        row: Row of the seismogram to prepare, for the phase whose parameters
            apply.

    Returns:
        A new, independent seismogram ready for plotting.
    """
    logger.debug(f"Preparing seismogram {row.seismogram_id} for plotting.")
    preped_seis = clone_to_mini(MiniSeismogram, row.seismogram)
    detrend(preped_seis)
    parameters = row.phase.parameters
    if parameters.bandpass_apply is True:
        fmin = parameters.bandpass_fmin
        fmax = parameters.bandpass_fmax
        logger.debug(f"Applying bandpass filter: {fmin}-{fmax} Hz.")
        bandpass(preped_seis, fmin, fmax)
    resample(preped_seis, _RESAMPLE_DELTA)
    normalize(preped_seis)
    return preped_seis


def event_seismograms(
    event: AimbatEvent | AimbatPhase,
) -> list[
    tuple[
        MiniSeismogram,
        AimbatStation,
        float,
        pd.Timestamp,
        pd.Timestamp | None,
        uuid.UUID,
    ]
]:
    """Get the seismograms of an event or one of its phases, by descending great circle distance.

    A seismogram appears once for each phase covered that it is in.

    Note:
        Each seismogram is detrended/filtered/resampled/normalised
        synchronously in `_prepare_seismogram_for_plotting`, with no
        batching or progress feedback - for an event with a large number of
        seismograms, the plot window can take a noticeable moment to appear
        with no indication that anything is happening.

    Args:
        event: The event, for every phase, or one phase.

    Returns:
        List of tuples containing the seismogram, station, distance from the
            event, initial pick, refined pick (or `None` if not set), and
            seismogram ID for each seismogram.
    """
    phases = [event] if isinstance(event, AimbatPhase) else event.phases
    if isinstance(event, AimbatPhase):
        event = event.event

    data = [
        (
            _prepare_seismogram_for_plotting(row),
            row.seismogram.station,
            distance(row.seismogram.station, event) / 1000,
            row.initial_pick,
            row.refined_pick,
            row.seismogram_id,
        )
        for phase in phases
        for row in phase.seismogram_parameters
    ]
    data.sort(key=lambda x: x[2], reverse=True)
    return data


def station_seismograms(
    station: AimbatStation,
) -> list[
    tuple[MiniSeismogram, AimbatEvent, pd.Timestamp, pd.Timestamp | None, uuid.UUID]
]:
    """Get all seismograms for a particular station ordered by pick time.

    Note:
        See `event_seismograms` - the same synchronous, unbatched
        preparation cost applies here.

    Args:
        station: AimbatStation.

    Returns:
        List of tuples containing the seismogram, event, initial pick,
            refined pick (or `None` if not set), and seismogram ID for each
            seismogram.
    """
    data = [
        (
            _prepare_seismogram_for_plotting(row),
            s.event,
            row.initial_pick,
            row.refined_pick,
            s.id,
        )
        for s in station.seismograms
        for row in s.phase_rows
    ]
    data.sort(key=lambda x: x[3] or x[2])
    return data
