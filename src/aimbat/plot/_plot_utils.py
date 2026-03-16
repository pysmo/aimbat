"""Prepare seismogram data for plotting."""

import uuid

import pandas as pd

from pysmo import MiniSeismogram
from pysmo.functions import clone_to_mini, detrend, normalize, resample
from pysmo.tools.azdist import distance
from pysmo.tools.signal import bandpass

from aimbat.logger import logger
from aimbat.models import AimbatEvent, AimbatSeismogram, AimbatStation

__all__ = ["clean_timedelta", "event_seismograms", "station_seismograms"]

_RESAMPLE_DELTA = pd.Timedelta(0.1, unit="s")


def clean_timedelta(x: float, _: int | None) -> str:
    total_seconds = x / 1e9
    sign = "-" if total_seconds < 0 else ""
    total_seconds = abs(int(total_seconds))
    minutes, seconds = divmod(total_seconds, 60)
    return f"{sign}{minutes:02d}:{seconds:02d}"


def _prepare_seismogram_for_plotting(seismogram: AimbatSeismogram) -> MiniSeismogram:
    logger.debug(f"Preparing seismogram {seismogram.id} for plotting.")
    preped_seis = clone_to_mini(MiniSeismogram, seismogram)
    detrend(preped_seis)
    if seismogram.event.parameters.bandpass_apply is True:
        fmin = seismogram.event.parameters.bandpass_fmin
        fmax = seismogram.event.parameters.bandpass_fmax
        logger.debug(f"Applying bandpass filter: {fmin}-{fmax} Hz.")
        bandpass(preped_seis, fmin, fmax)
    resample(preped_seis, _RESAMPLE_DELTA)
    normalize(preped_seis)
    return preped_seis


def event_seismograms(
    event: AimbatEvent,
) -> list[tuple[MiniSeismogram, AimbatStation, float, uuid.UUID]]:
    """Get all seismograms for a particular event ordered by descending great circle distance.

    Args:
        event: AimbatEvent.

    Returns:
        List of tuples containing the seismogram, station, distance from the
            event, and seismogram ID for each seismogram.
    """

    data = [
        (
            _prepare_seismogram_for_plotting(s),
            s.station,
            distance(s.station, s.event) / 1000,
            s.id,
        )
        for s in event.seismograms
    ]
    data.sort(key=lambda x: x[2], reverse=True)
    return data


def station_seismograms(
    station: AimbatStation,
) -> list[tuple[MiniSeismogram, AimbatEvent, pd.Timestamp, uuid.UUID]]:
    """Get all seismograms for a particular station ordered by event time.

    Args:
        station: AimbatStation.

    Returns:
        List of tuples containing the seismogram, event, pick time, and
            seismogram ID for each seismogram.
    """
    data = [
        (_prepare_seismogram_for_plotting(s), s.event, s.t1 or s.t0, s.id)
        for s in station.seismograms
    ]
    data.sort(key=lambda x: x[2])
    return data
