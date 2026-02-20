"""Add a random delay to a random choice of seismograms to create random events."""

from pysmo.classes import SAC
from pathlib import Path
from random import choices, randint
from pandas import Timedelta


def mk_data(orgfile: Path, newfile: Path, td: Timedelta) -> None:
    my_sac = SAC.from_file(str(orgfile))
    my_sac.event.time += td
    my_sac.write(str(newfile))


def make_data(orgfiles: list[Path], new_event_dir: Path, k: int) -> None:
    td = Timedelta(hours=randint(1000, 10000))
    for orgfile in choices(orgfiles, k=k):
        newfile = new_event_dir / orgfile.name
        mk_data(orgfile, newfile, td)


my_dir = Path(__file__).parent.resolve()

event_1 = my_dir / "event_1"
event_2 = my_dir / "event_2"
event_3 = my_dir / "event_3"

event_2.mkdir()
event_3.mkdir()

orgfiles = sorted(event_1.glob("*.bhz"))

make_data(orgfiles, event_2, 6)
make_data(orgfiles, event_3, 1)
