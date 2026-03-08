from functools import singledispatch
from typing import Literal, overload

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import mplcursors  # type: ignore[import-untyped]
import pandas as pd
from matplotlib import ticker
from sqlmodel import Session

from pysmo.tools.plotutils import time_array

from aimbat.models import AimbatEvent, AimbatStation

from ._plot_utils import clean_timedelta, event_seismograms, station_seismograms

__all__ = ["plot_seismograms"]


@singledispatch
def _plot_seis(
    arg: AimbatEvent | AimbatStation, session: Session
) -> tuple[plt.Figure, plt.Axes]:
    raise NotImplementedError(f"Cannot plot type: {type(arg)}")


@_plot_seis.register
def _(event: AimbatEvent, session: Session) -> tuple[plt.Figure, plt.Axes]:
    """Plot all seismograms for a particular event ordered by great circle distance."""

    if len(seismograms := event_seismograms(event)) == 0:
        raise RuntimeError(f"No seismograms found in event {event.id}.")

    fig, ax = plt.subplots(figsize=(10, 6))

    distance_min = min(d[2] for d in seismograms)
    distance_max = max(d[2] for d in seismograms)
    scaling_factor = (distance_max - distance_min) / len(seismograms) * 5

    for seismogram, station, distance_km, id in seismograms:
        data = seismogram.data * scaling_factor + distance_km
        times = time_array(seismogram)
        pd.Series(data, index=times).plot(
            ax=ax, scalex=True, scaley=True, label=f"Seismogram: {id}"
        )

    cursor = mplcursors.cursor(ax.lines, hover=True)

    @cursor.connect("add")
    def on_add(sel: mplcursors.Selection) -> None:
        sel.annotation.set_text(sel.artist.get_label())

    plt.xlabel(xlabel="Time of day")
    plt.ylabel(ylabel="Epicentral distance [km]")
    plt.gcf().autofmt_xdate()
    fmt = mdates.DateFormatter("%H:%M:%S")
    plt.gca().xaxis.set_major_formatter(fmt)
    plt.title(event.time.strftime("Event %Y-%m-%d %H:%M:%S"))
    return fig, ax


@_plot_seis.register
def _(station: AimbatStation, session: Session) -> tuple[plt.Figure, plt.Axes]:
    """Plot all seismograms for a particular station ordered by event time."""
    if len(seismograms := station_seismograms(station)) == 0:
        raise RuntimeError(f"No seismograms found for station {station.id}.")

    fig, ax = plt.subplots(figsize=(10, 6))

    for i, (seismogram, event, pick, id) in enumerate(seismograms):
        data = seismogram.data + i
        start = seismogram.begin_time - pick
        end = seismogram.end_time - pick
        td_index = pd.timedelta_range(start=start, end=end, periods=len(data))
        pd.Series(data, index=td_index).plot(
            ax=ax, scalex=True, scaley=True, label=f"Seismogram: {id}"
        )

    cursor = mplcursors.cursor(ax.lines, hover=True)

    @cursor.connect("add")
    def on_add(sel: mplcursors.Selection) -> None:
        sel.annotation.set_text(sel.artist.get_label())

    ax.xaxis.set_major_formatter(ticker.FuncFormatter(clean_timedelta))
    ax.yaxis.set_visible(False)
    plt.xlabel(xlabel="Time relative to pick")
    plt.title(f"Station {station.network} -- {station.name}")
    return fig, ax


@overload
def plot_seismograms(
    session: Session, plot_for: AimbatEvent | AimbatStation, return_fig: Literal[True]
) -> tuple[plt.Figure, plt.Axes]: ...


@overload
def plot_seismograms(
    session: Session, plot_for: AimbatEvent | AimbatStation, return_fig: Literal[False]
) -> None: ...


def plot_seismograms(
    session: Session, plot_for: AimbatEvent | AimbatStation, return_fig: bool
) -> tuple[plt.Figure, plt.Axes] | None:
    """Plot all seismograms for a particular event or station.

    Args:
        session: Database session.
        plot_for: What to plot the seismograms for (Event or Station).
        return_fig: Whether to return the figure and axes objects instead of showing the plot.

    Returns:
        figure and axes objects if return_fig is True, otherwise None.

    Raises:
        RuntimeError: If no seismograms are found for the event or station.

    Note:
        The seismograms use the filter settings specified in the event parameters.
    """
    fig, ax = _plot_seis(plot_for, session)

    if return_fig:
        return fig, ax
    plt.show()
    return None
