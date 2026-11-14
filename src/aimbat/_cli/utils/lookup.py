"""Find out what an ID refers to."""

from aimbat._cli.common import DebugParameter, describe_records

__all__ = ["cli_utils_lookup"]


def cli_utils_lookup(id: str, *, _: DebugParameter = DebugParameter()) -> None:
    """Show which event, station, seismogram or snapshot an ID belongs to.

    Every record whose ID starts with `id` is listed, with a short
    description. A short ID is unique only among records of the same kind, so
    it may match records of more than one kind.

    Args:
        id: A full ID or its first few characters, with or without dashes.
    """
    from rich.console import Console
    from rich.markup import escape
    from rich.table import Table
    from sqlmodel import Session

    from aimbat.db import engine
    from aimbat.models import (
        AimbatEvent,
        AimbatSeismogram,
        AimbatSnapshot,
        AimbatStation,
        AimbatTypes,
    )

    if not id.replace("-", ""):
        raise ValueError("Give at least the first character of an ID.")
    kinds: dict[type[AimbatTypes], str] = {
        AimbatEvent: "Event",
        AimbatStation: "Station",
        AimbatSeismogram: "Seismogram",
        AimbatSnapshot: "Snapshot",
    }
    table = Table(title=f"Records matching {escape(id)}")
    table.add_column("Type")
    table.add_column("ID", style="magenta")
    table.add_column("Description")
    with Session(engine) as session:
        for model_class, kind in kinds.items():
            for _id, short_id, description in describe_records(
                session, model_class, id_prefix=id
            ):
                table.add_row(kind, short_id, escape(description))
    if not table.rows:
        raise ValueError(f"No event, station, seismogram or snapshot has ID {id}.")
    Console().print(table)
