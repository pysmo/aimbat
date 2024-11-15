from aimbat.lib.db import engine
from aimbat.lib.models import AimbatSeismogram
from aimbat.lib.common import cli_enable_debug
from pysmo import MiniSeismogram, distance, time_array, unix_time_array
from sqlmodel import Session, select
from icecream import ic  # type: ignore
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pyqtgraph as pg  # type: ignore
import click
import sys

ic.disable()


def plotseis(event_id: int, use_qt: bool = False) -> None:
    """Plot all seismograms for a particular event ordered by great circle distance.

    Parameters:
        event_id: event id number seismograms are plotted for.
    """

    ic()
    ic(event_id, use_qt)

    with Session(engine) as session:
        select_seismograms = select(AimbatSeismogram).where(
            AimbatSeismogram.event_id == event_id
        )
        seismograms = session.exec(select_seismograms).all()
        ic(seismograms)

        distance_dict = {
            seismogram.id: distance(seismogram.station, seismogram.event) / 1000
            for seismogram in seismograms
        }
        ic(distance_dict)
        distance_min = min(distance_dict.values())
        distance_max = max(distance_dict.values())
        scaling_factor = (distance_max - distance_min) / len(seismograms) * 5
        ic(distance_min, distance_max, scaling_factor)

        title = seismograms[0].event.time.strftime("Event %Y-%m-%d %H:%M:%S")
        xlabel = "Time of day"
        ylabel = "Epicentral distance [km]"

        plotWidget = None
        if use_qt:
            plotWidget = pg.plot(title=title)
            axis = pg.DateAxisItem()
            plotWidget.setAxisItems({"bottom": axis})
            plotWidget.setLabel("bottom", xlabel)
            plotWidget.setLabel("left", ylabel)

        for seismogram in seismograms:
            miniseis = MiniSeismogram.clone(seismogram)
            miniseis.detrend()
            miniseis.normalize()
            plot_data = miniseis.data * scaling_factor + distance_dict[seismogram.id]
            if use_qt and plotWidget is not None:
                times = unix_time_array(miniseis)
                plotWidget.plot(times, plot_data)
            else:
                times = time_array(miniseis)
                plt.plot(
                    times,
                    plot_data,
                    scalex=True,
                    scaley=True,
                )
        if not use_qt:
            plt.xlabel(xlabel=xlabel)
            plt.ylabel(ylabel=ylabel)
            plt.gcf().autofmt_xdate()
            fmt = mdates.DateFormatter("%H:%M:%S")
            plt.gca().xaxis.set_major_formatter(fmt)
            plt.title(title)
            plt.show()
        elif use_qt and sys.flags.interactive != 1:
            pg.exec()


@click.group("utils")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Usefull extra tools to use with AIMBAT projects."""
    cli_enable_debug(ctx)


@cli.command("plotseis")
@click.argument("event_id", nargs=1, type=int, required=True)
@click.pass_context
def cli_plotseis(ctx: click.Context, event_id: int) -> None:
    """Plot seismograms in project."""
    ic()
    use_qt: bool = ctx.obj.get("USE_QT", False)
    plotseis(event_id, use_qt)


if __name__ == "__main__":
    cli(obj={})
