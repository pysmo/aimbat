"""View and manage stations."""

from typing import Annotated, Literal
from uuid import UUID

from cyclopts import App

from aimbat.models import AimbatStation

from .common import (
    DebugParameter,
    JsonDumpParameters,
    TableParameters,
    event_parameter_is_all,
    event_parameter_with_all,
    id_parameter,
    open_in_editor,
    simple_exception,
    station_parameter_is_all,
    station_parameter_with_all,
)

app = App(name="station", help=__doc__, help_format="markdown")
_note = App(name="note", help="Read and edit station notes.", help_format="markdown")
_quality = App(
    name="quality", help="View station quality metrics.", help_format="markdown"
)
app.command(_note)
app.command(_quality)


@_note.command(name="read")
@simple_exception
def cli_station_note_read(
    station_id: Annotated[
        UUID,
        id_parameter(AimbatStation, help="UUID (or unique prefix) of station."),
    ],
    *,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Display the note attached to a station, rendered as Markdown."""
    from rich.console import Console
    from rich.markdown import Markdown
    from sqlmodel import Session

    from aimbat.core import get_note_content
    from aimbat.db import engine

    with Session(engine) as session:
        content = get_note_content(session, "station", station_id)

    Console().print(Markdown(content) if content else "(no note)")


@_note.command(name="edit")
@simple_exception
def cli_station_note_edit(
    station_id: Annotated[
        UUID,
        id_parameter(AimbatStation, help="UUID (or unique prefix) of station."),
    ],
    *,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Open the station note in `$EDITOR` and save changes on exit."""
    from sqlmodel import Session

    from aimbat.core import get_note_content, save_note
    from aimbat.db import engine

    with Session(engine) as session:
        original = get_note_content(session, "station", station_id)

    updated = open_in_editor(original)

    if updated != original:
        with Session(engine) as session:
            save_note(session, "station", station_id, updated)


@app.command(name="delete")
@simple_exception
def cli_station_delete(
    station_id: Annotated[
        UUID,
        id_parameter(
            AimbatStation,
            help="UUID (or unique prefix) of station to delete.",
        ),
    ],
    *,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Delete existing station (for all events)."""
    from sqlmodel import Session

    from aimbat.core import delete_station
    from aimbat.db import engine

    with Session(engine) as session:
        delete_station(session, station_id)


@app.command(name="plotseis")
@simple_exception
def cli_station_seismograms_plot(
    station_id: Annotated[
        UUID,
        id_parameter(
            AimbatStation,
            help="UUID (or unique prefix) of station to plot seismograms for.",
        ),
    ],
    *,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Plot input seismograms for events recorded at this station."""
    from sqlmodel import Session

    from aimbat.db import engine
    from aimbat.models import AimbatStation
    from aimbat.plot import plot_seismograms

    with Session(engine) as session:
        station = session.get(AimbatStation, station_id)
        if station is None:
            raise ValueError(f"Station with ID {station_id} not found.")
        plot_seismograms(session, station, return_fig=False)


@app.command(name="dump")
@simple_exception
def cli_station_dump(
    *, dump_parameters: JsonDumpParameters = JsonDumpParameters()
) -> None:
    """Dump the contents of the AIMBAT station table to JSON.

    Output can be piped or redirected for use in external tools or scripts.
    """

    from rich import print_json
    from sqlmodel import Session

    from aimbat.core import dump_station_table
    from aimbat.db import engine

    with Session(engine) as session:
        print_json(data=dump_station_table(session, by_alias=dump_parameters.by_alias))


@app.command(name="list")
@simple_exception
def cli_station_list(
    event_id: Annotated[UUID | Literal["all"], event_parameter_with_all()],
    table_parameters: TableParameters = TableParameters(),
) -> None:
    """Print information on the stations used in an event."""
    from sqlmodel import Session

    from aimbat.core import dump_station_table, resolve_event
    from aimbat.db import engine
    from aimbat.logger import logger
    from aimbat.models import AimbatStationRead
    from aimbat.utils import uuid_shortener

    from .common import json_to_table

    if raw := table_parameters.raw:
        exclude = {"short_id"}
    else:
        exclude = {"id"}

    with Session(engine) as session:
        if event_parameter_is_all(event_id):
            logger.debug("Selecting all AIMBAT stations.")
            data = dump_station_table(session, from_read_model=True, exclude=exclude)
            title = "AIMBAT stations for all events"
        else:
            logger.debug("Selecting AIMBAT stations used by event.")
            event = resolve_event(session, event_id)
            data = dump_station_table(
                session,
                event_id=event.id,
                from_read_model=True,
                exclude={"seismogram_count", "event_count"} | exclude,
            )
            if raw:
                title = f"AIMBAT stations for event {event.time} (ID={event.id})"
            else:
                title = f"AIMBAT stations for event {event.time.strftime('%Y-%m-%d %H:%M:%S')} (ID={uuid_shortener(session, event)})"

        json_to_table(data, model=AimbatStationRead, title=title, raw=raw)


@_quality.command(name="dump")
@simple_exception
def cli_station_quality_dump(
    *, dump_parameters: JsonDumpParameters = JsonDumpParameters()
) -> None:
    """Dump station quality statistics to JSON.

    Output can be piped or redirected for use in external tools or scripts.
    """
    from rich import print_json
    from sqlmodel import Session

    from aimbat.core import dump_station_quality_table
    from aimbat.db import engine

    with Session(engine) as session:
        data = dump_station_quality_table(session, by_alias=dump_parameters.by_alias)

    print_json(data=data)


@_quality.command(name="list")
@simple_exception
def cli_station_quality_list(
    station_id: Annotated[UUID | Literal["all"], station_parameter_with_all()],
    *,
    table_parameters: TableParameters = TableParameters(),
) -> None:
    """Show aggregated quality statistics for a station or all stations.

    Displays ICCS and MCCC quality metrics (means, SEMs) aggregated across
    all seismograms of each station.
    """
    from sqlmodel import Session

    from aimbat.core import dump_station_quality_table
    from aimbat.db import engine
    from aimbat.models import RichColSpec, SeismogramQualityStats
    from aimbat.utils import uuid_shortener

    from .common import json_to_table

    raw = table_parameters.raw
    is_all = station_parameter_is_all(station_id)

    with Session(engine) as session:
        if is_all:
            title = "Quality statistics for all stations"
            exclude = None
        else:
            label = (
                str(station_id)
                if raw
                else uuid_shortener(session, AimbatStation, str_uuid=str(station_id))
            )
            title = f"Quality statistics for station: {label}"
            exclude = {"station_id"}

        col_specs = {
            "station_id": RichColSpec(
                formatter=lambda x: uuid_shortener(session, AimbatStation, str_uuid=x),
            ),
        }

        data = dump_station_quality_table(
            session,
            station_id=None if station_parameter_is_all(station_id) else station_id,
            exclude=exclude,
        )

    json_to_table(
        data=data,
        model=SeismogramQualityStats,
        title=title,
        raw=raw,
        col_specs=col_specs,
    )


if __name__ == "__main__":
    app()
