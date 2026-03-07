"""
Load a project from SAC files that carry no event/station headers.

Layout:
  - 3 events
  - 10 broadband stations
  - 20 seismograms: events 1 and 2 recorded at 7 stations each,
    event 3 recorded at 6 stations
"""

import json
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from aimbat.db import engine
from aimbat.core import (
    add_data_to_project,
    create_project,
    create_snapshot,
)
from aimbat.io import DataType
from aimbat.models import AimbatEvent, AimbatStation

# ------------------------------------------------------------------ #
# Metadata                                                            #
# ------------------------------------------------------------------ #

EVENTS: list[dict[str, Any]] = [
    {
        "time": "2024-01-12T08:14:33Z",
        "latitude": 37.52,
        "longitude": 143.04,
        "depth": 35.0,
    },
    {
        "time": "2024-02-28T21:07:55Z",
        "latitude": -23.11,
        "longitude": -67.89,
        "depth": 120.0,
    },
    {
        "time": "2024-03-09T03:51:20Z",
        "latitude": 51.72,
        "longitude": 178.35,
        "depth": 55.0,
    },
]

STATIONS: list[dict[str, Any]] = [
    {
        "name": "ANMO",
        "network": "IU",
        "location": "00",
        "channel": "BHZ",
        "latitude": 34.946,
        "longitude": -106.457,
        "elevation": 1820.0,
    },
    {
        "name": "COLA",
        "network": "IU",
        "location": "00",
        "channel": "BHZ",
        "latitude": 64.874,
        "longitude": -147.861,
        "elevation": 84.0,
    },
    {
        "name": "GUMO",
        "network": "IU",
        "location": "00",
        "channel": "BHZ",
        "latitude": 13.589,
        "longitude": 144.868,
        "elevation": 74.0,
    },
    {
        "name": "HRV",
        "network": "IU",
        "location": "00",
        "channel": "BHZ",
        "latitude": 42.506,
        "longitude": -71.558,
        "elevation": 200.0,
    },
    {
        "name": "MAJO",
        "network": "IU",
        "location": "00",
        "channel": "BHZ",
        "latitude": 36.536,
        "longitude": 138.204,
        "elevation": 399.0,
    },
    {
        "name": "MIDW",
        "network": "IU",
        "location": "00",
        "channel": "BHZ",
        "latitude": 28.216,
        "longitude": -177.370,
        "elevation": 150.0,
    },
    {
        "name": "POHA",
        "network": "IU",
        "location": "00",
        "channel": "BHZ",
        "latitude": 19.757,
        "longitude": -155.531,
        "elevation": 1936.0,
    },
    {
        "name": "SSPA",
        "network": "IU",
        "location": "00",
        "channel": "BHZ",
        "latitude": 40.636,
        "longitude": -77.888,
        "elevation": 270.0,
    },
    {
        "name": "TATO",
        "network": "IU",
        "location": "00",
        "channel": "BHZ",
        "latitude": 24.975,
        "longitude": 121.498,
        "elevation": 75.0,
    },
    {
        "name": "YSS",
        "network": "IU",
        "location": "00",
        "channel": "BHZ",
        "latitude": 46.958,
        "longitude": 142.760,
        "elevation": 89.0,
    },
]

# Which stations recorded each event (indices into STATIONS list).
# 7 + 7 + 6 = 20 seismograms total.
EVENT_STATION_MAP = {
    0: [0, 1, 2, 3, 4, 5, 6],  # event 1 — 7 seismograms
    1: [0, 1, 2, 3, 4, 5, 6],  # event 2 — 7 seismograms
    2: [0, 1, 2, 3, 4, 5],  # event 3 — 6 seismograms
}

# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #


def write_json(data: dict, path: Path) -> Path:
    path.write_text(json.dumps(data))
    return path


def sac_path(event_idx: int, station_idx: int) -> Path:
    """Return the path to the SAC file for a given event/station pair."""
    return Path(f"data/ev{event_idx + 1:02d}_st{station_idx + 1:02d}.sac")


# ------------------------------------------------------------------ #
# Main                                                                #
# ------------------------------------------------------------------ #

workdir = Path("json_metadata")
workdir.mkdir(exist_ok=True)

# 1. Initialise project
create_project(engine)

with Session(engine) as session:

    # 2. Register events from JSON
    event_files = [
        write_json(ev, workdir / f"event_{i:02d}.json") for i, ev in enumerate(EVENTS)
    ]
    add_data_to_project(session, event_files, DataType.JSON_EVENT)

    # 3. Register stations from JSON
    station_files = [
        write_json(st, workdir / f"station_{i:02d}.json")
        for i, st in enumerate(STATIONS)
    ]
    add_data_to_project(session, station_files, DataType.JSON_STATION)

    # 4. Retrieve the newly created records
    events = session.exec(select(AimbatEvent)).all()
    stations = session.exec(select(AimbatStation)).all()

    # Build lookup maps by (time, network+name) so insertion order doesn't matter
    event_by_time = {str(e.time)[:19]: e for e in events}
    station_by_key = {(s.network, s.name): s for s in stations}

    # 5. Add SAC files, linking each to its pre-registered event and station
    for ev_idx, st_indices in EVENT_STATION_MAP.items():
        ev_time = EVENTS[ev_idx]["time"][:19]
        db_event = event_by_time[ev_time]

        for st_idx in st_indices:
            st_meta = STATIONS[st_idx]
            db_station = station_by_key[(st_meta["network"], st_meta["name"])]

            add_data_to_project(
                session,
                [sac_path(ev_idx, st_idx)],
                DataType.SAC,
                event_id=db_event.id,
                station_id=db_station.id,
            )

    # 6. Snapshot the initial state before any processing
    events = session.exec(select(AimbatEvent)).all()
    for event in events:
        create_snapshot(session, event, comment="initial import")

print("Project ready.")
print(f"  Events:   {len(events)}")
print(f"  Stations: {len(stations)}")
