"""
Ingest seismograms directly from a PysmoProject, with no SAC/JSON round-trip.

A PysmoProject fetches waveforms on demand and is just one possible producer
of (seismogram, station, event) triples - add_seismograms_to_project accepts
triples built from any pysmo Station/Event/IccsSeismogram-shaped objects,
however the caller likes (a notebook, an ObsPy Stream + inventory, ...).

This reuses the reference station/event pair from pysmo's own PysmoProject
documentation: IU.ANMO recording the 2010-02-27 Maule, Chile M8.8 earthquake.
"""

import pandas as pd
from attrs import define
from sqlmodel import Session

from pysmo import Event, MiniEvent, MiniStation, Seismogram, Station
from pysmo.classes import StationXML
from pysmo.functions import clone_to_mini
from pysmo.tools.iccs import MiniIccsSeismogram
from pysmo.tools.project import FetchContext, ProjectEntry, PysmoProject
from pysmo.tools.signal import remove_response

from aimbat.core import add_seismograms_to_project
from aimbat.db import engine

station_anmo = MiniStation(
    name="ANMO",
    network="IU",
    location="00",
    channel="LHZ",
    latitude=34.945981,
    longitude=-106.457133,
)
event_maule = MiniEvent(
    latitude=-36.122,
    longitude=-72.898,
    depth=22900.0,
    time=pd.Timestamp("2010-02-27T06:34:11.53Z"),
)


@define(kw_only=True)
class ToMiniIccsSeismogramWithResponseRemoved:
    """seismogram_transform: instrument response removed, converted for ICCS."""

    pre_filt: tuple[float, float, float, float]

    def __call__(
        self, seismogram: Seismogram, context: FetchContext[Station, Event]
    ) -> MiniIccsSeismogram:
        response = StationXML.fetch(
            station=context.entry.station, time=context.starttime
        ).response
        corrected = remove_response(
            seismogram, response, pre_filt=self.pre_filt, clone=True
        )
        # t0 is set from the predicted arrival - AimbatSeismogram.t0 needs no
        # further fallback, since IccsSeismogram.t0 is a required field.
        return clone_to_mini(
            MiniIccsSeismogram, corrected, update={"t0": context.predicted}
        )


project = PysmoProject(
    entries=[ProjectEntry(station=station_anmo, event=event_maule)],
    seismogram_transform=ToMiniIccsSeismogramWithResponseRemoved(
        # Teleseismic P on IU.ANMO's LHZ (1 Hz) channel: comfortably above
        # the instrument's own corner and below the 0.5 Hz Nyquist.
        pre_filt=(0.01, 0.02, 0.2, 0.3),
    ),
)

# Build (seismogram, station, event) triples. project.seismogram() fetches
# and applies seismogram_transform; nothing reaches disk until
# add_seismograms_to_project persists it below. PysmoProject's fetch cache
# is in-memory only and the default fetch_seismogram hits a remote FDSN
# service, so this write is the seismogram's first and only copy on disk -
# not a duplicate. That stops being true if fetch_seismogram is swapped for
# one that reads local files (e.g. wrapping SAC.fetch over a local
# archive), which would make data_dir a second, redundant copy.
items = [
    (project.seismogram(station, event), station, event)
    for event in project.events
    for station in project.stations_for(event)
]

with Session(engine) as session:
    add_seismograms_to_project(session, items, data_dir="waveforms")
