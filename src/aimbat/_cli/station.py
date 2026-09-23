"""View and manage stations."""

from typing import Annotated, Literal
from uuid import UUID

from cyclopts import App

from aimbat.models import AimbatStation

from .common import (
    ConfirmParameters,
    DebugParameter,
    JsonDumpParameters,
    TableParameters,
    confirm_or_abort,
    event_parameter_is_all,
    event_parameter_with_all,
    event_table_title,
    handle_issues,
    id_label,
    id_parameter,
    make_note_app,
    print_json_dump,
    print_quality_table,
    station_parameter_is_all,
    station_parameter_with_all,
)

app = App(name="station", help=__doc__, help_format="markdown")
_note = make_note_app(
    "station",
    AimbatStation,
    id_parameter(AimbatStation, help="UUID (or unique prefix) of station."),
)
_quality = App(
    name="quality", help="View station quality metrics.", help_format="markdown"
)
app.command(_note)
app.command(_quality)


@app.command(name="delete")
@handle_issues
def cli_station_delete(
    station_id: Annotated[
        UUID,
        id_parameter(
            AimbatStation,
            help="UUID (or unique prefix) of station to delete.",
        ),
    ],
    *,
    confirm: ConfirmParameters = ConfirmParameters(),
) -> None:
    """Delete an existing station.

    Cascades to every seismogram recorded at this station across all events,
    including their data sources, parameters, quality records, and snapshot
    history.
    """
    from sqlmodel import Session

    from aimbat.core import delete_station
    from aimbat.db import engine

    confirm_or_abort(
        f"Delete station {station_id} and all of its seismograms?", yes=confirm.yes
    )
    with Session(engine) as session:
        delete_station(session, station_id)


@app.command(name="plotseis")
@handle_issues
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
    """Plot input seismograms for events recorded at this station.

    Keeps its database session open for as long as the plot window is:
    closing the window promptly releases the connection.
    """
    from sqlmodel import Session

    from aimbat.db import engine
    from aimbat.models import AimbatStation
    from aimbat.plot import plot_seismograms

    with Session(engine) as session:
        station = session.get(AimbatStation, station_id)
        if station is None:
            raise ValueError(f"Station with ID {station_id} not found.")
        plot_seismograms(station, return_fig=False)


@app.command(name="dump")
@handle_issues
def cli_station_dump(
    *, dump_parameters: JsonDumpParameters = JsonDumpParameters()
) -> None:
    """Dump the contents of the AIMBAT station table to JSON.

    Output can be piped or redirected for use in external tools or scripts.
    """
    from aimbat.core import dump_station_table

    print_json_dump(dump_station_table, by_alias=dump_parameters.by_alias)


@app.command(name="list")
@handle_issues
def cli_station_list(
    event_id: Annotated[UUID | Literal["all"], event_parameter_with_all()],
    *,
    table_parameters: TableParameters = TableParameters(),
) -> None:
    """Print information on the stations used in an event."""
    from sqlmodel import Session

    from aimbat.core import dump_station_table, resolve_event
    from aimbat.db import engine
    from aimbat.logger import logger
    from aimbat.models import AimbatStationRead

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
            title = event_table_title(session, event, subject="stations", raw=raw)

        json_to_table(data, model=AimbatStationRead, title=title, raw=raw)


@_quality.command(name="dump")
@handle_issues
def cli_station_quality_dump(
    *, dump_parameters: JsonDumpParameters = JsonDumpParameters()
) -> None:
    """Dump station quality statistics to JSON.

    Output can be piped or redirected for use in external tools or scripts.
    """
    from aimbat.core import dump_station_quality_table

    print_json_dump(dump_station_quality_table, by_alias=dump_parameters.by_alias)


@_quality.command(name="list")
@handle_issues
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

    raw = table_parameters.raw

    with Session(engine) as session:
        if station_parameter_is_all(station_id):
            title, filter_id = "Quality statistics for all stations", None
        else:
            label = id_label(session, AimbatStation, station_id, raw=raw)
            title, filter_id = f"Quality statistics for station: {label}", station_id

        print_quality_table(
            session,
            dump_station_quality_table,
            title=title,
            filter_id=filter_id,
            id_field="station_id",
            id_columns={"station_id": AimbatStation},
            raw=raw,
        )


if __name__ == "__main__":
    app()
