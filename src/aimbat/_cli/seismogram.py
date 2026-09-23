"""View and manage seismograms in the AIMBAT project."""

from typing import Annotated, Literal
from uuid import UUID

from cyclopts import App

from aimbat.models import AimbatSeismogram
from aimbat.types import SeismogramParameter

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
)

app = App(name="seismogram", help=__doc__, help_format="markdown")
_note = make_note_app(
    "seismogram",
    AimbatSeismogram,
    id_parameter(AimbatSeismogram, help="UUID (or unique prefix) of seismogram."),
)
parameter = App(
    name="parameter", help="Manage seismogram parameters.", help_format="markdown"
)
app.command(_note)
app.command(parameter)


@app.command(name="delete")
@handle_issues
def cli_seismogram_delete(
    seismogram_id: Annotated[
        UUID,
        id_parameter(
            AimbatSeismogram, help="UUID (or unique prefix) of seismogram to delete."
        ),
    ],
    *,
    confirm: ConfirmParameters = ConfirmParameters(),
) -> None:
    """Delete an existing seismogram.

    Cascades to its data source, processing parameters, and quality record.
    Also removes this seismogram's parameter and quality data from every
    snapshot that recorded it, including snapshots taken before deletion.
    """
    from sqlmodel import Session

    from aimbat.core import delete_seismogram
    from aimbat.db import engine

    confirm_or_abort(f"Delete seismogram {seismogram_id}?", yes=confirm.yes)
    with Session(engine) as session:
        delete_seismogram(session, seismogram_id)


@app.command(name="dump")
@handle_issues
def cli_seismogram_dump(
    *,
    dump_parameters: JsonDumpParameters = JsonDumpParameters(),
) -> None:
    """Dump the contents of the AIMBAT seismogram table to JSON.

    Output can be piped or redirected for use in external tools or scripts.
    """
    from aimbat.core import dump_seismogram_table

    print_json_dump(dump_seismogram_table, by_alias=dump_parameters.by_alias)


@app.command(name="list")
@handle_issues
def cli_seismogram_list(
    event_id: Annotated[UUID | Literal["all"], event_parameter_with_all()],
    *,
    table_parameters: TableParameters = TableParameters(),
) -> None:
    """Print information on the seismograms in an event."""
    from sqlmodel import Session

    from aimbat.core import dump_seismogram_table, resolve_event
    from aimbat.db import engine
    from aimbat.models import AimbatSeismogramRead

    from .common import json_to_table

    if raw := table_parameters.raw:
        exclude = {"short_id", "short_event_id"}
    else:
        exclude = {"id", "event_id"}

    with Session(engine) as session:
        if event_parameter_is_all(event_id):
            title = "AIMBAT seismograms for all events"
            data = dump_seismogram_table(session, from_read_model=True, exclude=exclude)
        else:
            event = resolve_event(session, event_id)
            title = event_table_title(session, event, subject="seismograms", raw=raw)
            exclude.add("event_id" if raw else "short_event_id")
            data = dump_seismogram_table(
                session,
                from_read_model=True,
                event_id=event.id,
                exclude=exclude,
            )

        json_to_table(data, model=AimbatSeismogramRead, title=title, raw=raw)


@parameter.command(name="get")
@handle_issues
def cli_seismogram_parameter_get(
    name: SeismogramParameter,
    *,
    seismogram_id: Annotated[
        UUID,
        id_parameter(
            AimbatSeismogram, help="UUID (or unique prefix) of seismogram to query."
        ),
    ],
    _: DebugParameter = DebugParameter(),
) -> None:
    """Get the value of a processing parameter.

    Args:
        name: Name of the seismogram parameter.
        seismogram_id: UUID (or unique prefix) of the seismogram to query.
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
@handle_issues
def cli_seismogram_parameter_set(
    name: SeismogramParameter,
    value: str,
    *,
    seismogram_id: Annotated[
        UUID,
        id_parameter(
            AimbatSeismogram, help="UUID (or unique prefix) of seismogram to modify."
        ),
    ],
    _: DebugParameter = DebugParameter(),
) -> None:
    """Set value of a processing parameter.

    Args:
        name: Name of the seismogram parameter.
        value: Value of the seismogram parameter.
        seismogram_id: UUID (or unique prefix) of the seismogram to modify.
    """
    from sqlmodel import Session

    from aimbat.core import set_seismogram_parameter
    from aimbat.db import engine

    with Session(engine) as session:
        set_seismogram_parameter(session, seismogram_id, name, value)


@parameter.command(name="reset")
@handle_issues
def cli_seismogram_parameter_reset(
    seismogram_id: Annotated[
        UUID,
        id_parameter(
            AimbatSeismogram,
            help="UUID (or unique prefix) of seismogram to reset parameters for.",
        ),
    ],
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
@handle_issues
def cli_seismogram_parameter_dump(
    *,
    dump_parameters: JsonDumpParameters = JsonDumpParameters(),
) -> None:
    """Dump seismogram parameter table to json."""
    from aimbat.core import dump_seismogram_parameter_table

    print_json_dump(dump_seismogram_parameter_table, by_alias=dump_parameters.by_alias)


@parameter.command(name="list")
@handle_issues
def cli_seismogram_parameter_list(
    event_id: Annotated[UUID | Literal["all"], event_parameter_with_all()],
    *,
    table_parameters: TableParameters = TableParameters(),
) -> None:
    """List processing parameter values for seismograms in an event.

    Displays per-seismogram parameters (e.g. `select`, `flip`, `t1` pick)
    in a table. Use `seismogram parameter set` to modify individual values.
    """

    from sqlmodel import Session

    from aimbat.core import dump_seismogram_parameter_table, resolve_event
    from aimbat.db import engine
    from aimbat.models import (
        AimbatEvent,
        AimbatSeismogram,
        AimbatSeismogramParameters,
    )
    from aimbat.models._format import RichColSpec
    from aimbat.utils import uuid_shortener
    from aimbat.utils.formatters import fmt_flip

    from .common import json_to_table

    raw = table_parameters.raw

    with Session(engine) as session:
        if event_parameter_is_all(event_id):
            event = None
            title = "Seismogram parameters for all events"
        else:
            event = resolve_event(session, event_id)
            label = id_label(session, AimbatEvent, event.id, raw=raw)
            title = f"Seismogram parameters for event: {label}"

        data = dump_seismogram_parameter_table(
            session, event_id=event.id if event else None
        )

        json_to_table(
            data=data,
            model=AimbatSeismogramParameters,
            title=title,
            raw=raw,
            col_specs={
                "id": RichColSpec(
                    style="yellow",
                    no_wrap=True,
                    highlight=False,
                    formatter=lambda x: uuid_shortener(
                        session, AimbatSeismogramParameters, str_uuid=str(x)
                    ),
                ),
                "seismogram_id": RichColSpec(
                    style="magenta",
                    no_wrap=True,
                    highlight=False,
                    formatter=lambda x: uuid_shortener(
                        session, AimbatSeismogram, str_uuid=str(x)
                    ),
                ),
                "flip": RichColSpec(formatter=fmt_flip),
            },
            column_order=["id"],
        )


if __name__ == "__main__":
    app()
