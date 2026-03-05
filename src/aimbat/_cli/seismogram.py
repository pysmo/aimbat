"""View and manage seismograms in the AIMBAT project."""

from .common import (
    GlobalParameters,
    TableParameters,
    simple_exception,
    id_parameter,
    ALL_EVENTS_PARAMETER,
)
from aimbat.models import AimbatSeismogram
from aimbat._types import SeismogramParameter
from typing import Annotated
from cyclopts import App
import uuid

app = App(name="seismogram", help=__doc__, help_format="markdown")
parameter = App(
    name="parameter", help="Manage seismogram parameters.", help_format="markdown"
)
app.command(parameter)


@app.command(name="delete")
@simple_exception
def cli_seismogram_delete(
    seismogram_id: Annotated[uuid.UUID, id_parameter(AimbatSeismogram)],
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Delete existing seismogram."""
    from aimbat.db import engine
    from aimbat.core import delete_seismogram_by_id
    from sqlmodel import Session

    with Session(engine) as session:
        delete_seismogram_by_id(session, seismogram_id)


@app.command(name="dump")
@simple_exception
def cli_seismogram_dump(
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Dump the contents of the AIMBAT seismogram table to JSON.

    Output can be piped or redirected for use in external tools or scripts.
    """
    from aimbat.db import engine
    from aimbat.core import dump_seismogram_table_to_json
    from sqlmodel import Session
    from rich import print_json

    with Session(engine) as session:
        print_json(dump_seismogram_table_to_json(session))


@parameter.command(name="get")
@simple_exception
def cli_seismogram_parameter_get(
    seismogram_id: Annotated[uuid.UUID, id_parameter(AimbatSeismogram)],
    name: SeismogramParameter,
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Get the value of a processing parameter.

    Args:
        name: Name of the seismogram parameter.
    """
    from aimbat.db import engine
    from aimbat.core import get_seismogram_parameter_by_id
    from sqlmodel import Session

    with Session(engine) as session:
        print(get_seismogram_parameter_by_id(session, seismogram_id, name))


@parameter.command(name="set")
@simple_exception
def cli_seismogram_parameter_set(
    seismogram_id: Annotated[uuid.UUID, id_parameter(AimbatSeismogram)],
    name: SeismogramParameter,
    value: str,
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Set value of a processing parameter.

    Args:
        name: Name of the seismogram parameter.
        value: Value of the seismogram parameter.
    """
    from aimbat.db import engine
    from aimbat.core import set_seismogram_parameter_by_id
    from sqlmodel import Session

    with Session(engine) as session:
        set_seismogram_parameter_by_id(session, seismogram_id, name, value)


@parameter.command(name="reset")
@simple_exception
def cli_seismogram_parameter_reset(
    seismogram_id: Annotated[uuid.UUID, id_parameter(AimbatSeismogram)],
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Reset all processing parameters to their default values."""
    from aimbat.db import engine
    from aimbat.core import reset_seismogram_parameters_by_id
    from sqlmodel import Session

    with Session(engine) as session:
        reset_seismogram_parameters_by_id(session, seismogram_id)


@parameter.command(name="dump")
@simple_exception
def cli_seismogram_parameter_dump(
    all_events: Annotated[bool, ALL_EVENTS_PARAMETER] = False,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Dump seismogram parameter table to json."""
    from aimbat.db import engine
    from aimbat.core import dump_seismogram_parameter_table_to_json, resolve_event
    from sqlmodel import Session
    from rich import print_json

    with Session(engine) as session:
        event = (
            resolve_event(session, global_parameters.event_id)
            if not all_events
            else None
        )
        print_json(
            dump_seismogram_parameter_table_to_json(
                session, all_events, as_string=True, event=event
            )
        )


@parameter.command(name="list")
@simple_exception
def cli_seismogram_parameter_list(
    global_parameters: GlobalParameters = GlobalParameters(),
    table_parameters: TableParameters = TableParameters(),
) -> None:
    """List processing parameter values for seismograms in an event.

    Displays per-seismogram parameters (e.g. `select`, `flip`, `t1` pick)
    in a table. Use `seismogram parameter set` to modify individual values.
    """

    from aimbat.db import engine
    from aimbat.core import resolve_event, dump_seismogram_parameter_table_to_json
    from aimbat.utils import uuid_shortener, json_to_table, TABLE_STYLING
    from aimbat.logger import logger
    from sqlmodel import Session

    short = table_parameters.short

    with Session(engine) as session:
        logger.info("Printing AIMBAT seismogram parameters table.")

        event = resolve_event(session, global_parameters.event_id)
        title = f"Seismogram parameters for event: {uuid_shortener(session, event) if short else str(event.id)}"

        json_to_table(
            data=dump_seismogram_parameter_table_to_json(
                session, all_events=False, as_string=False, event=event
            ),
            title=title,
            skip_keys=["id"],
            column_order=["seismogram_id", "select"],
            common_column_kwargs={"highlight": True},
            formatters={
                "seismogram_id": lambda x: (
                    uuid_shortener(session, AimbatSeismogram, str_uuid=x)
                    if short
                    else x
                ),
            },
            column_kwargs={
                "seismogram_id": {
                    "header": "Seismogram ID (shortened)" if short else "Seismogram ID",
                    "justify": "center",
                    "style": TABLE_STYLING.mine,
                },
            },
        )


@app.command(name="list")
@simple_exception
def cli_seismogram_list(
    *,
    all_events: Annotated[bool, ALL_EVENTS_PARAMETER] = False,
    table_parameters: TableParameters = TableParameters(),
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Print information on the seismograms in an event."""
    from aimbat.db import engine
    from aimbat.core import resolve_event
    from aimbat.utils import uuid_shortener, make_table, TABLE_STYLING
    from aimbat.logger import logger
    from rich.console import Console
    from sqlmodel import Session, select

    short = table_parameters.short

    with Session(engine) as session:
        logger.info("Printing AIMBAT seismogram table.")

        title = "AIMBAT seismograms for all events"

        if all_events:
            logger.debug("Selecting seismograms for all events.")
            seismograms = session.exec(select(AimbatSeismogram)).all()
        else:
            logger.debug("Selecting seismograms for event.")
            event = resolve_event(session, global_parameters.event_id)
            seismograms = event.seismograms
            if short:
                title = f"AIMBAT seismograms for event {event.time.strftime('%Y-%m-%d %H:%M:%S')} (ID={uuid_shortener(session, event)})"
            else:
                title = f"AIMBAT seismograms for event {event.time} (ID={event.id})"

        logger.debug(f"Found {len(seismograms)} seismograms for the table.")

        table = make_table(title=title)
        table.add_column(
            "ID (shortened)" if short else "ID",
            justify="center",
            style=TABLE_STYLING.id,
            no_wrap=True,
        )
        table.add_column(
            "Selected", justify="center", style=TABLE_STYLING.mine, no_wrap=True
        )
        table.add_column(
            "NPTS", justify="center", style=TABLE_STYLING.mine, no_wrap=True
        )
        table.add_column(
            "Delta", justify="center", style=TABLE_STYLING.mine, no_wrap=True
        )
        table.add_column(
            "Data ID", justify="center", style=TABLE_STYLING.linked, no_wrap=True
        )
        table.add_column("Station ID", justify="center", style=TABLE_STYLING.linked)
        table.add_column("Station Name", justify="center", style=TABLE_STYLING.linked)
        if all_events:
            table.add_column("Event ID", justify="center", style=TABLE_STYLING.linked)

        for seismogram in seismograms:
            logger.debug(f"Adding seismogram with ID {seismogram.id} to the table.")
            row = [
                (uuid_shortener(session, seismogram) if short else str(seismogram.id)),
                TABLE_STYLING.bool_formatter(seismogram.parameters.select),
                str(len(seismogram.data)),
                str(seismogram.delta.total_seconds()),
                (
                    uuid_shortener(session, seismogram.datasource)
                    if short
                    else str(seismogram.datasource.id)
                ),
                (
                    uuid_shortener(session, seismogram.station)
                    if short
                    else str(seismogram.station.id)
                ),
                f"{seismogram.station.name} - {seismogram.station.network}",
            ]

            if all_events:
                row.append(
                    uuid_shortener(session, seismogram.event)
                    if short
                    else str(seismogram.event.id)
                )
            table.add_row(*row)

        console = Console()
        console.print(table)


if __name__ == "__main__":
    app()
