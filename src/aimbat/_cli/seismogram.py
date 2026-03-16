"""View and manage seismograms in the AIMBAT project."""

import uuid
from typing import Annotated

from cyclopts import App

from aimbat._types import SeismogramParameter

from .common import (
    ALL_EVENTS_PARAMETER,
    DebugParameter,
    GlobalParameters,
    JsonDumpParameters,
    TableParameters,
    seismogram_parameter,
    simple_exception,
)

app = App(name="seismogram", help=__doc__, help_format="markdown")
parameter = App(
    name="parameter", help="Manage seismogram parameters.", help_format="markdown"
)
app.command(parameter)


@app.command(name="delete")
@simple_exception
def cli_seismogram_delete(
    seismogram_id: Annotated[uuid.UUID, seismogram_parameter()],
    *,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Delete existing seismogram."""
    from sqlmodel import Session

    from aimbat.core import delete_seismogram
    from aimbat.db import engine

    with Session(engine) as session:
        delete_seismogram(session, seismogram_id)


@app.command(name="dump")
@simple_exception
def cli_seismogram_dump(
    *,
    dump_parameters: JsonDumpParameters = JsonDumpParameters(),
) -> None:
    """Dump the contents of the AIMBAT seismogram table to JSON.

    Output can be piped or redirected for use in external tools or scripts.
    """
    from rich import print_json
    from sqlmodel import Session

    from aimbat.core import dump_seismogram_table
    from aimbat.db import engine

    with Session(engine) as session:
        print_json(
            data=dump_seismogram_table(session, by_alias=dump_parameters.by_alias)
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
    from sqlmodel import Session

    from aimbat.core import dump_seismogram_table, resolve_event
    from aimbat.db import engine
    from aimbat.utils import TABLE_STYLING, json_to_table, uuid_shortener

    if short := table_parameters.short:
        exclude = {"id", "event_id"}
    else:
        exclude = {"short_id", "short_event_id"}

    with Session(engine) as session:
        if all_events is True:
            title = "AIMBAT seismograms for all events"
            data = dump_seismogram_table(
                session, from_read_model=True, by_title=True, exclude=exclude
            )
        else:
            event = resolve_event(session, global_parameters.event_id)
            if short:
                title = f"AIMBAT seismograms for event {event.time.strftime('%Y-%m-%d %H:%M:%S')}"
                title += f" (ID={uuid_shortener(session, event)})"
                exclude.add("short_event_id")
            else:
                title = f"AIMBAT seismograms for event {event.time} (ID={event.id})"
                exclude.add("event_id")
            data = dump_seismogram_table(
                session,
                from_read_model=True,
                by_title=True,
                event_id=event.id,
                exclude=exclude,
            )

        json_to_table(
            data,
            title=title,
            formatters={
                "Flip": TABLE_STYLING.flip_formatter,
            },
        )


if __name__ == "__main__":
    app()


@parameter.command(name="get")
@simple_exception
def cli_seismogram_parameter_get(
    seismogram_id: Annotated[uuid.UUID, seismogram_parameter()],
    name: SeismogramParameter,
    *,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Get the value of a processing parameter.

    Args:
        name: Name of the seismogram parameter.
    """
    from sqlalchemy.exc import NoResultFound
    from sqlmodel import Session

    from aimbat.db import engine
    from aimbat.models import AimbatSeismogram

    with Session(engine) as session:
        seismogram = session.get(AimbatSeismogram, seismogram_id)
        if seismogram is None:
            raise NoResultFound(f"Unable to find seismogram with id: {seismogram_id}.")
        value = seismogram.parameters.model_dump(mode="json").get(name)
        print(value)


@parameter.command(name="set")
@simple_exception
def cli_seismogram_parameter_set(
    seismogram_id: Annotated[uuid.UUID, seismogram_parameter()],
    name: SeismogramParameter,
    value: str,
    *,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Set value of a processing parameter.

    Args:
        name: Name of the seismogram parameter.
        value: Value of the seismogram parameter.
    """
    from sqlmodel import Session

    from aimbat.core import set_seismogram_parameter
    from aimbat.db import engine

    with Session(engine) as session:
        set_seismogram_parameter(session, seismogram_id, name, value)


@parameter.command(name="reset")
@simple_exception
def cli_seismogram_parameter_reset(
    seismogram_id: Annotated[uuid.UUID, seismogram_parameter()],
    *,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Reset all processing parameters to their default values."""
    from sqlmodel import Session

    from aimbat.core import reset_seismogram_parameters
    from aimbat.db import engine

    with Session(engine) as session:
        reset_seismogram_parameters(session, seismogram_id)


@parameter.command(name="dump")
@simple_exception
def cli_seismogram_parameter_dump(
    *,
    dump_parameters: JsonDumpParameters = JsonDumpParameters(),
) -> None:
    """Dump seismogram parameter table to json."""
    from rich import print_json
    from sqlmodel import Session

    from aimbat.core import dump_seismogram_parameter_table
    from aimbat.db import engine

    with Session(engine) as session:
        print_json(
            data=dump_seismogram_parameter_table(
                session, by_alias=dump_parameters.by_alias
            )
        )


@parameter.command(name="list")
@simple_exception
def cli_seismogram_parameter_list(
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
    table_parameters: TableParameters = TableParameters(),
) -> None:
    """List processing parameter values for seismograms in an event.

    Displays per-seismogram parameters (e.g. `select`, `flip`, `t1` pick)
    in a table. Use `seismogram parameter set` to modify individual values.
    """

    from sqlmodel import Session

    from aimbat.core import dump_seismogram_parameter_table, resolve_event
    from aimbat.db import engine
    from aimbat.models import AimbatSeismogram, AimbatSeismogramParameters
    from aimbat.utils import TABLE_STYLING, json_to_table, uuid_shortener

    short = table_parameters.short

    with Session(engine) as session:
        if global_parameters.all_events:
            event = None
            title = "Seismogram parameters for all events"
        else:
            event = resolve_event(session, global_parameters.event_id)
            title = f"Seismogram parameters for event: {uuid_shortener(session, event) if short else str(event.id)}"

        data = dump_seismogram_parameter_table(
            session, event_id=event.id if event else None, by_title=True
        )

        json_to_table(
            data=data,
            title=title,
            column_order=["ID", "Seismogram ID", "Select"],
            formatters={
                "ID": lambda x: (
                    uuid_shortener(session, AimbatSeismogramParameters, str_uuid=x)
                    if short
                    else x
                ),
                "Seismogram ID": lambda x: (
                    uuid_shortener(session, AimbatSeismogram, str_uuid=x)
                    if short
                    else x
                ),
                "Flip": TABLE_STYLING.flip_formatter,
            },
        )
