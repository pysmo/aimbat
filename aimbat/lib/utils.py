from aimbat.lib.db import engine
from aimbat.lib.models import AimbatSeismogram
from aimbat.lib.common import cli_enable_debug, check_for_notebook
from pysmo import MiniSeismogram, distance, time_array, unix_time_array
from sqlmodel import Session, select
from icecream import ic  # type: ignore
from pyqtgraph.jupyter import PlotWidget  # type: ignore
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pyqtgraph as pg  # type: ignore
import click

ic.disable()


def plotseis(event_id: int, use_qt: bool = False) -> None | PlotWidget:
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

        plot_widget = None
        if use_qt:
            if check_for_notebook():
                plot_widget = PlotWidget(width=200)
            else:
                plot_widget = pg.plot(title=title)
            axis = pg.DateAxisItem()
            plot_widget.setAxisItems({"bottom": axis})
            plot_widget.setLabel("bottom", xlabel)
            plot_widget.setLabel("left", ylabel)

        for seismogram in seismograms:
            miniseis = MiniSeismogram.clone(seismogram)
            miniseis.detrend()
            miniseis.normalize()
            plot_data = miniseis.data * scaling_factor + distance_dict[seismogram.id]
            if use_qt and plot_widget is not None:
                times = unix_time_array(miniseis)
                plot_widget.plot(times, plot_data)
            else:
                times = time_array(miniseis)
                plt.plot(
                    times,
                    plot_data,
                    scalex=True,
                    scaley=True,
                )
        if use_qt and isinstance(plot_widget, PlotWidget):
            return plot_widget
        elif not use_qt:
            plt.xlabel(xlabel=xlabel)
            plt.ylabel(ylabel=ylabel)
            plt.gcf().autofmt_xdate()
            fmt = mdates.DateFormatter("%H:%M:%S")
            plt.gca().xaxis.set_major_formatter(fmt)
            plt.title(title)
            plt.show()
        return None


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

    use_qt: bool = ctx.obj.get("USE_QT", False)

    if use_qt:
        pg.mkQApp()

    plotseis(event_id, use_qt)

    if use_qt:
        pg.exec()


if __name__ == "__main__":
    cli(obj={})
