"""
Ingest seismograms directly from a PysmoProject, with no SAC/JSON round-trip.

A PysmoProject fetches waveforms on demand and is just one possible producer
of (seismogram, station, event) triples. add_seismograms_to_project accepts
triples built from any pysmo Station/Event/IccsSeismogram-shaped objects,
however the caller likes (a notebook, an ObsPy Stream + inventory, ...).

This reuses one event and three stations from AIMBAT's own Alaska teleseismic
sample dataset (../aimbat-sampledata): the 2014-04-12 M7.6 Solomon Islands
earthquake. All three stations (AK/AV network) are in the Aleutians.
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

station_atka = MiniStation(
    name="ATKA",
    network="AK",
    location="--",
    channel="BHZ",
    latitude=52.2016,
    longitude=-174.1975,
)
station_msw = MiniStation(
    name="MSW",
    network="AV",
    location="--",
    channel="BHZ",
    latitude=53.9148,
    longitude=-166.788,
)
station_akrb = MiniStation(
    name="AKRB",
    network="AV",
    location="--",
    channel="BHZ",
    latitude=54.1292,
    longitude=-166.0708,
)
event_solomon = MiniEvent(
    latitude=-11.3487,
    longitude=162.0025,
    depth=22600.0,
    time=pd.Timestamp("2014-04-12T20:14:39.300Z"),
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
    entries=[
        ProjectEntry(station=station_atka, event=event_solomon),
        ProjectEntry(station=station_msw, event=event_solomon),
        ProjectEntry(station=station_akrb, event=event_solomon),
    ],
    seismogram_transform=ToMiniIccsSeismogramWithResponseRemoved(
        # Teleseismic P on a broadband BHZ channel: comfortably within its
        # passband, well clear of microseismic noise below ~0.05 Hz.
        pre_filt=(0.03, 0.05, 0.5, 1.0),
    ),
)

# Build (seismogram, station, event) triples; project.seismogram() fetches
# and applies seismogram_transform. Nothing reaches disk until
# add_seismograms_to_project writes it to data_dir below.
items = [
    (project.seismogram(station, event), station, event)
    for event in project.events
    for station in project.stations_for(event)
]

with Session(engine) as session:
    add_seismograms_to_project(session, items, data_dir="waveforms")
