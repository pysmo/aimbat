"""View and manage events in the AIMBAT project."""

import uuid
from typing import Annotated

from cyclopts import App
from sqlmodel import Session

from aimbat.models import AimbatEvent

from .common import (
    ConfirmParameters,
    JsonDumpParameters,
    TableParameters,
    confirm_or_abort,
    event_parameter,
    handle_issues,
    make_note_app,
    print_json_dump,
)

__all__ = [
    "cli_event_delete",
    "cli_event_dump",
    "cli_event_list",
]

app = App(name="event", help=__doc__, help_format="markdown")
_note = make_note_app("event", AimbatEvent, event_parameter())
app.command(_note)


@app.command(name="delete")
@handle_issues
def cli_event_delete(
    event_id: Annotated[uuid.UUID, event_parameter()],
    *,
    confirm: ConfirmParameters = ConfirmParameters(),
) -> None:
    """Delete an existing event.

    Cascades to all of the event's seismograms (with their data sources,
    parameters, and quality records) and to every snapshot taken for it.
    """
    from aimbat.actions import delete_events
    from aimbat.core import resolve_event
    from aimbat.db import engine

    with Session(engine) as session:
        event = resolve_event(session, event_id)
        resolved_id, event_time = event.id, event.time
    confirm_or_abort(
        f"Delete event at {event_time} and all of its seismograms?",
        yes=confirm.yes,
    )
    delete_events([resolved_id])


@app.command(name="dump")
@handle_issues
def cli_event_dump(
    *, dump_parameters: JsonDumpParameters = JsonDumpParameters()
) -> None:
    """Dump the contents of the AIMBAT event table to JSON.

    Output can be piped or redirected for use in external tools or scripts.
    """
    from aimbat.core import dump_event_table

    print_json_dump(dump_event_table, by_alias=dump_parameters.by_alias)


@app.command(name="list")
@handle_issues
def cli_event_list(
    *,
    table_parameters: TableParameters = TableParameters(),
) -> None:
    """Print a table of events stored in the AIMBAT project."""

    from aimbat.core import dump_event_table
    from aimbat.db import engine
    from aimbat.logger import logger
    from aimbat.models import AimbatEventRead

    from .common import json_to_table

    if raw := table_parameters.raw:
        exclude = {"short_id"}
    else:
        exclude = {"id"}

    with Session(engine) as session:
        logger.info("Printing AIMBAT events table.")

        json_to_table(
            data=dump_event_table(
                session, from_read_model=True, by_title=False, exclude=exclude
            ),
            model=AimbatEventRead,
            title="AIMBAT Events",
            raw=raw,
        )


if __name__ == "__main__":
    app()
