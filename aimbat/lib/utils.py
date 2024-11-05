from aimbat.lib.db import engine
from aimbat.lib.models import AimbatSeismogram
from pysmo import MiniSeismogram, distance, time_array
from sqlmodel import Session, select
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import click


def plotseis(event_id: int) -> None:
    """Plot all seismograms for a particular event ordered by great circle distance.

    Parameters:
        event_id: event id number seismograms are plotted for.
    """
    with Session(engine) as session:
        select_seismograms = select(AimbatSeismogram).where(
            AimbatSeismogram.event_id == event_id
        )
        seismograms = session.exec(select_seismograms).all()
        distance_dict = {
            seismogram.id: distance(seismogram.station, seismogram.event) / 1000
            for seismogram in seismograms
        }
        distance_min = min(distance_dict.values())
        distance_max = max(distance_dict.values())
        scaling_factor = (distance_max - distance_min) / len(seismograms) * 5

        for seismogram in seismograms:
            miniseis = MiniSeismogram.clone(seismogram)
            miniseis.detrend()
            miniseis.normalize()
            times = time_array(miniseis)
            plt.plot(
                times,
                miniseis.data * scaling_factor + distance_dict[seismogram.id],
                scalex=True,
                scaley=True,
            )
        plt.xlabel("Time")
        plt.gcf().autofmt_xdate()
        fmt = mdates.DateFormatter("%H:%M:%S")
        plt.gca().xaxis.set_major_formatter(fmt)
        title = seismograms[0].event.time.strftime("%Y-%m-%d %H:%M:%S")
        plt.title(title)
    plt.show()


@click.group("utils")
def cli() -> None:
    """Usefull extra tools to use with AIMBAT projects."""
    pass


@cli.command("plotseis")
@click.argument("event_id", nargs=1, type=int, required=True)
def cli_plotseis(event_id: int) -> None:
    """Plot seismograms in project."""

    plotseis(event_id=event_id)


if __name__ == "__main__":
    cli()
