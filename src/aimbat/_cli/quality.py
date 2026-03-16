"""View alignment quality metrics."""

import json
import uuid
from enum import StrEnum
from typing import Annotated, Any

from cyclopts import App

from aimbat.models import AimbatSeismogram, AimbatStation
from aimbat.models._quality import AimbatSeismogramQualityBase

from .common import (
    DebugParameter,
    GlobalParameters,
    id_parameter,
    simple_exception,
)


class SeismogramQualityField(StrEnum):
    """Available seismogram-level quality metric field names."""

    mccc_cc_mean = "mccc_cc_mean"
    mccc_cc_std = "mccc_cc_std"
    mccc_error = "mccc_error"


class EventQualityField(StrEnum):
    """Available event-level quality metric field names."""

    mccc_rmse = "mccc_rmse"


app = App(name="quality", help=__doc__, help_format="markdown")
_seismogram = App(
    name="seismogram", help="Seismogram alignment quality.", help_format="markdown"
)
_event = App(name="event", help="Event alignment quality.", help_format="markdown")
_station = App(
    name="station", help="Station alignment quality.", help_format="markdown"
)
app.command(_seismogram)
app.command(_event)
app.command(_station)


def _fmt(v: Any) -> str:
    """Format a quality metric value for display."""
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "✓" if v else "✗"
    if isinstance(v, float):
        return f"{v:.5f}"
    return str(v)


# ---------------------------------------------------------------------------
# Seismogram
# ---------------------------------------------------------------------------


@_seismogram.command(name="list")
@simple_exception
def cli_quality_seismogram_list(
    seismogram_id: Annotated[uuid.UUID, id_parameter(AimbatSeismogram)],
    *,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Show quality metrics for a seismogram as a table."""
    from sqlmodel import Session

    from aimbat.core import get_quality_seismogram
    from aimbat.db import engine
    from aimbat.utils import json_to_table

    with Session(engine) as session:
        quality = get_quality_seismogram(session, seismogram_id)

    data: dict[str, Any]
    _skip = {"id", "seismogram_id", "snapshot_id"}
    if quality is None:
        data = {
            k: None for k in AimbatSeismogramQualityBase.model_fields if k not in _skip
        }
    else:
        data = quality.model_dump(mode="json")

    json_to_table(
        data,
        title=f"Quality — Seismogram {str(seismogram_id)[:8]}",
        skip_keys=list(_skip),
        formatters={k: _fmt for k in data},
    )


@_seismogram.command(name="dump")
@simple_exception
def cli_quality_seismogram_dump(
    seismogram_id: Annotated[uuid.UUID, id_parameter(AimbatSeismogram)],
    *,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Dump seismogram quality metrics as JSON."""
    from rich import print_json
    from sqlmodel import Session

    from aimbat.core import get_quality_seismogram
    from aimbat.db import engine

    with Session(engine) as session:
        quality = get_quality_seismogram(session, seismogram_id)

    if quality is None:
        data: dict[str, Any] = {
            "seismogram_id": str(seismogram_id),
            **{
                k: None
                for k in AimbatSeismogramQualityBase.model_fields
                if k not in ("id", "seismogram_id", "snapshot_id")
            },
        }
    else:
        data = quality.model_dump(mode="json")

    print_json(json.dumps(data))


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------


@_event.command(name="list")
@simple_exception
def cli_quality_event_list(
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Show quality metrics for an event as a table."""
    from sqlmodel import Session

    from aimbat.core import dump_quality_event, resolve_event
    from aimbat.db import engine
    from aimbat.utils import json_to_table

    with Session(engine) as session:
        event = resolve_event(session, global_parameters.event_id)
        data = dump_quality_event(session, event.id)
        title = f"Quality — Event {str(event.id)[:8]}"

    json_to_table(
        data,
        title=title,
        skip_keys=["id", "event_id"],
        formatters={k: _fmt for k in data},
    )


@_event.command(name="dump")
@simple_exception
def cli_quality_event_dump(
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Dump event quality metrics as JSON."""
    from rich import print_json
    from sqlmodel import Session

    from aimbat.core import dump_quality_event, resolve_event
    from aimbat.db import engine

    with Session(engine) as session:
        event = resolve_event(session, global_parameters.event_id)
        data = dump_quality_event(session, event.id)

    print_json(json.dumps(data))


# ---------------------------------------------------------------------------
# Station
# ---------------------------------------------------------------------------


@_station.command(name="list")
@simple_exception
def cli_quality_station_list(
    station_id: Annotated[uuid.UUID, id_parameter(AimbatStation)],
    *,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Show quality metrics for a station as a table."""
    from sqlmodel import Session

    from aimbat.core import dump_quality_station
    from aimbat.db import engine
    from aimbat.utils import json_to_table

    with Session(engine) as session:
        data = dump_quality_station(session, station_id)

    json_to_table(
        data,
        title=f"Quality — Station {str(station_id)[:8]}",
        skip_keys=["station_id"],
        formatters={k: _fmt for k in data},
    )


@_station.command(name="dump")
@simple_exception
def cli_quality_station_dump(
    station_id: Annotated[uuid.UUID, id_parameter(AimbatStation)],
    *,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Dump station quality metrics as JSON."""
    from rich import print_json
    from sqlmodel import Session

    from aimbat.core import dump_quality_station
    from aimbat.db import engine

    with Session(engine) as session:
        data = dump_quality_station(session, station_id)

    print_json(json.dumps(data))


if __name__ == "__main__":
    app()
