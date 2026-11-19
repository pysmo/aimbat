"""View and complete the initial picks of the project.

Picks are stored as read from the data sources. A pick that has a phase name
and is matched to a seismogram is promoted: it becomes the initial pick of
that seismogram for the phase. The commands here read the picks of data
sources again, list the stored picks, name picks that have no phase name,
match picks to seismograms, promote picks that were left out, set manual
picks, and remove or restore picks. `aimbat data check` lists what remains
to be done. Commands that give a phase new initial picks snapshot it, except
`pick set`.
"""

import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal

from cyclopts import App, Parameter, validators
from sqlmodel import Session

from aimbat.io import DataType
from aimbat.models import AimbatEvent, AimbatPick, AimbatSeismogram, AimbatStation

from .common import (
    DebugParameter,
    JsonDumpParameters,
    PhaseNameConverter,
    TableParameters,
    UuidConverter,
    event_parameter_is_all,
    event_parameter_with_all,
    handle_issues,
    id_label,
    print_json_dump,
    print_pick_summary,
    print_warning,
)

if TYPE_CHECKING:
    from pandas import Timedelta, Timestamp

    from aimbat.actions import PickChangeResult

__all__ = [
    "cli_pick_add",
    "cli_pick_dump",
    "cli_pick_list",
    "cli_pick_match",
    "cli_pick_name",
    "cli_pick_promote",
    "cli_pick_remove",
    "cli_pick_restore",
    "cli_pick_set",
]

app = App(name="pick", help=__doc__, help_format="markdown")


def _ids_parameter(
    model_class: type[AimbatPick | AimbatSeismogram | AimbatStation],
    name: str,
    help: str,
) -> Parameter:
    return Parameter(
        name=name,
        help=help,
        converter=UuidConverter(model_class),
        consume_multiple=True,
        negative_iterable=(),
    )


def _absolute_time(value: str, *, relative: bool) -> "Timestamp":
    """Read an ISO 8601 time with an offset."""
    from pandas import Timestamp

    time = Timestamp(value)
    if time.tzinfo is None:
        also = ", or as seconds after the event origin" if relative else ""
        raise ValueError(
            f"Time {value!r} has no offset. Times are given in ISO 8601 with an "
            + f"offset (e.g. 2011-03-11T05:56:00+00:00){also}."
        )
    return time


def _time_bound(value: str | None) -> "Timestamp | Timedelta | None":
    """Read a time option: ISO 8601 with an offset, or seconds after the event origin."""
    from pandas import Timedelta

    if value is None:
        return None
    try:
        return Timedelta(seconds=float(value))
    except ValueError:
        pass
    return _absolute_time(value, relative=True)


_event_option = Parameter(
    name="event",
    help="Only picks of this event: UUID (or unique prefix).",
    converter=UuidConverter(AimbatEvent),
)

_snapshot_option = Parameter(
    name="snapshot",
    help="Automatically create a snapshot for each phase that gained initial picks.",
)


def _print_change(result: "PickChangeResult", first_line: str | None) -> None:
    from rich.console import Console

    from aimbat.utils.formatters import fmt_timestamp

    lines = [first_line] if first_line else []
    if result.promoted:
        per_phase = ", ".join(
            f"{name}: {count}" for name, count in sorted(result.promoted.items())
        )
        lines.append(f"Promoted {result.total_promoted} pick(s) ({per_phase}).")
    for phase in result.phases_created:
        lines.append(
            f"Phase {phase.name} created for event {fmt_timestamp(phase.event_time)}."
        )
    if result.replaced:
        lines.append(
            f"Replaced the pick of {len(result.replaced)} row(s). The replaced "
            + "picks are dismissed."
        )
    if result.conflicts:
        lines.append(
            f"Not promoted: {len(result.conflicts)} pick(s) whose row holds a pick "
            + "with another time. `aimbat pick promote --pick PICK --replace` "
            + "replaces it."
        )
    if result.invalid:
        lines.append(
            f"Not promoted: {len(result.invalid)} pick(s) that fail the pick "
            + "checks. Run `aimbat data check`."
        )
    lines.extend(f"Warning: {warning}" for warning in result.warnings)
    if result.snapshotted_phase_ids:
        lines.append(f"Snapshotted {len(result.snapshotted_phase_ids)} phase(s).")
    if result.dry_run:
        lines.append("Dry run: nothing was changed.")
    Console().print("\n".join(lines))
    for failed_id, error in result.snapshot_failures:
        print_warning(
            f"Could not create an automatic snapshot for phase {failed_id}: {error}"
        )


@app.command(name="add")
@handle_issues
def cli_pick_add(
    sources: Annotated[
        list[Path],
        Parameter(
            name="sources",
            help="One or more data source paths to read.",
            consume_multiple=1,
            negative_iterable=(),
            validator=validators.Path(exists=True, dir_okay=False),
        ),
    ],
    *,
    data_type: Annotated[
        DataType,
        Parameter(name="type", help="Format of the data sources."),
    ] = DataType.SAC,
    unlabelled_as: Annotated[
        str | None,
        Parameter(
            name="unlabelled-as",
            help=(
                "Phase name given to new picks that have no label in the data "
                + "source. Without it, such picks are stored but belong to no phase."
            ),
        ),
    ] = None,
    skip_unnamed: Annotated[
        bool,
        Parameter(
            name="skip-unnamed",
            help="Do not store new picks that have no phase name.",
        ),
    ] = False,
    phases: Annotated[
        list[str] | None,
        Parameter(
            name="phase",
            negative_iterable=(),
            help=(
                "Phase that picks may be added to, or created for. Repeatable. "
                + "Named picks of other phases are stored but belong to no phase. "
                + "Without it, every phase."
            ),
        ),
    ] = None,
    update: Annotated[
        bool,
        Parameter(
            name="update",
            negative=(),
            help="Apply the times and labels that changed in the data sources.",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        Parameter(
            name="dry-run",
            negative=(),
            help="Show what would change without changing the project.",
        ),
    ] = False,
    show_progress_bar: Annotated[
        bool,
        Parameter(name="progress", help="Display a progress bar while reading."),
    ] = True,
    auto_snapshot: Annotated[
        bool,
        Parameter(
            name="snapshot",
            help=(
                "Automatically create a snapshot for each phase that gained "
                + "initial picks."
            ),
        ),
    ] = True,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Read the picks of data sources that are already in the project.

    New picks are stored and promoted as by `aimbat data add`, which does not
    read a data source again once it is in the project. Picks already stored
    are skipped. A stored pick whose time or label changed in the data source
    is counted, and updated with `--update`. A promoted pick keeps its row,
    whose initial pick changes with it, unless its new label gives another
    phase name: its row is then deleted and the pick is promoted to the new
    phase. Dismissed picks are left as they are. A pick deleted with
    `aimbat pick remove --purge` is stored again.
    """
    from rich.console import Console
    from rich.progress import Progress

    from aimbat.actions import add_picks
    from aimbat.core import PickNaming

    naming = PickNaming(unlabelled_as=unlabelled_as, skip_unnamed=skip_unnamed)

    with Progress(disable=not show_progress_bar) as progress:
        task = progress.add_task("Reading picks ...", total=len(sources))

        def on_progress(done: int, _total: int) -> None:
            progress.update(task, completed=done)

        result = add_picks(
            sources,
            data_type,
            naming=naming,
            phases=phases,
            update=update,
            dry_run=dry_run,
            auto_snapshot=auto_snapshot,
            on_progress=on_progress,
        )

    picks = result.picks
    if picks.stored or picks.already_present or picks.skipped_unnamed or picks.changed:
        print_pick_summary(picks, len(result.snapshotted_phase_ids))
    else:
        Console().print("No picks read.")
    if dry_run:
        Console().print("Dry run: nothing was changed.")
    for failed_id, error in result.snapshot_failures:
        print_warning(
            f"Could not create an automatic snapshot for phase {failed_id}: {error}"
        )
    if result.blocking_items:
        n = result.blocking_items
        print_warning(
            f"Not ready: {n} blocking item{'' if n == 1 else 's'}. "
            + "Run `aimbat data check`."
        )


@app.command(name="list")
@handle_issues
def cli_pick_list(
    event_id: Annotated[uuid.UUID | Literal["all"], event_parameter_with_all()],
    *,
    unnamed: Annotated[
        bool, Parameter(help="Only show picks without a phase name.", negative=())
    ] = False,
    unmatched: Annotated[
        bool,
        Parameter(help="Only show picks not matched to a seismogram.", negative=()),
    ] = False,
    phase: Annotated[
        str | None,
        Parameter(
            name="phase",
            help="Only show picks with this phase name.",
            converter=PhaseNameConverter(),
        ),
    ] = None,
    dismissed: Annotated[
        bool, Parameter(help="Show dismissed picks instead of the others.", negative=())
    ] = False,
    table_parameters: TableParameters = TableParameters(),
) -> None:
    """Print a table of the stored picks of an event or of all events.

    Shows the time, label, phase name and state of each pick, the seismogram
    it is matched to or the target it was read with, and its source. Picks
    whose event is not in the project are listed for all events only.
    """
    from aimbat.core import PickSelection, dump_pick_table, resolve_event
    from aimbat.db import engine
    from aimbat.models import AimbatPickRead

    from .common import json_to_table

    raw = table_parameters.raw
    exclude = {"short_id", "short_seismogram_id"} if raw else {"id", "seismogram_id"}

    with Session(engine) as session:
        if event_parameter_is_all(event_id):
            title, filter_id = "Picks for all events", None
        else:
            event = resolve_event(session, event_id)
            label = id_label(session, AimbatEvent, event.id, raw=raw)
            title, filter_id = f"Picks for event: {label}", event.id
            exclude.add("event_time")
        selection = PickSelection(
            event_id=filter_id,
            phase_name=phase,
            unnamed=unnamed,
            unmatched=unmatched,
            dismissed=dismissed,
        )
        json_to_table(
            data=dump_pick_table(
                session, from_read_model=True, exclude=exclude, selection=selection
            ),
            model=AimbatPickRead,
            title=title,
            raw=raw,
        )


@app.command(name="dump")
@handle_issues
def cli_pick_dump(
    *, dump_parameters: JsonDumpParameters = JsonDumpParameters()
) -> None:
    """Dump the stored picks, with their state, to JSON.

    Output can be piped or redirected for use in external tools or scripts.
    """
    from aimbat.core import dump_pick_table

    print_json_dump(dump_pick_table, by_alias=dump_parameters.by_alias)


@app.command(name="name")
@handle_issues
def cli_pick_name(
    name: Annotated[str, Parameter(help="Phase name to give the picks.")],
    *,
    pick_ids: Annotated[
        list[uuid.UUID] | None,
        _ids_parameter(AimbatPick, "pick", "UUIDs (or unique prefixes) of picks."),
    ] = None,
    event_id: Annotated[uuid.UUID | None, _event_option] = None,
    unnamed: Annotated[
        bool, Parameter(help="Only picks without a phase name.", negative=())
    ] = False,
    label: Annotated[
        str | None, Parameter(help="Only picks read with this label.")
    ] = None,
    seismogram_ids: Annotated[
        list[uuid.UUID] | None,
        _ids_parameter(
            AimbatSeismogram,
            "seismogram",
            "Only picks matched to these seismograms: UUIDs (or unique prefixes).",
        ),
    ] = None,
    station_ids: Annotated[
        list[uuid.UUID] | None,
        _ids_parameter(
            AimbatStation,
            "station",
            "Only picks matched to seismograms of these stations: UUIDs (or "
            + "unique prefixes).",
        ),
    ] = None,
    time_from: Annotated[
        str | None,
        Parameter(
            name="from",
            help="Only picks at or after this time: ISO 8601 with an offset, or "
            + "seconds after the event origin.",
        ),
    ] = None,
    time_to: Annotated[
        str | None,
        Parameter(
            name="to",
            help="Only picks at or before this time: ISO 8601 with an offset, or "
            + "seconds after the event origin.",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        Parameter(name="dry-run", help="Show what would change without saving it."),
    ] = False,
    auto_snapshot: Annotated[bool, _snapshot_option] = True,
) -> None:
    """Give the selected picks a phase name.

    Picks are selected by ID, or by the criteria given, which all apply.
    Promoted picks keep the name of their phase and cannot be selected.
    Named picks that are matched are promoted, and phases missing for them
    are created. Each phase that gains initial picks is snapshotted.
    """
    from aimbat.actions import name_picks
    from aimbat.core import PickSelection

    selection = PickSelection(
        pick_ids=tuple(pick_ids or ()),
        event_id=event_id,
        seismogram_ids=tuple(seismogram_ids or ()),
        station_ids=tuple(station_ids or ()),
        label=label,
        unnamed=unnamed,
        time_from=_time_bound(time_from),
        time_to=_time_bound(time_to),
    )
    result = name_picks(selection, name, dry_run=dry_run, auto_snapshot=auto_snapshot)
    _print_change(result, f"Named {len(result.picks)} pick(s) {name}.")


@app.command(name="promote")
@handle_issues
def cli_pick_promote(
    *,
    event_id: Annotated[
        uuid.UUID | Literal["all"] | None, event_parameter_with_all()
    ] = None,
    phase: Annotated[
        str | None,
        Parameter(
            name="phase",
            help="Promote the matched picks with this phase name.",
            converter=PhaseNameConverter(),
        ),
    ] = None,
    pick_ids: Annotated[
        list[uuid.UUID] | None,
        _ids_parameter(AimbatPick, "pick", "UUIDs (or unique prefixes) of picks."),
    ] = None,
    replace: Annotated[
        bool,
        Parameter(
            help="With `--pick`: replace the pick of a row that holds a pick with "
            + "another time. The replaced pick is dismissed.",
            negative=(),
        ),
    ] = False,
    auto_snapshot: Annotated[bool, _snapshot_option] = True,
) -> None:
    """Promote named, matched picks that have no row.

    With `--phase`, the picks of that name of an event (or of all events)
    are promoted. With `--pick`, the given picks are. Phases missing for the
    picks are created. Each phase that gains initial picks is snapshotted.
    """
    from aimbat.actions import promote_phase_picks, promote_picks

    if (phase is None) == (not pick_ids):
        raise ValueError("Give either `--phase` or `--pick`.")
    if pick_ids:
        result = promote_picks(pick_ids, replace=replace, auto_snapshot=auto_snapshot)
    else:
        assert phase is not None
        if replace:
            raise ValueError("`--replace` is given with `--pick` only.")
        if event_id is None:
            raise ValueError("Give the event with `--event`, or `all`.")
        result = promote_phase_picks(event_id, phase, auto_snapshot=auto_snapshot)
    changed = result.promoted or result.replaced
    _print_change(result, None if changed else "No picks promoted.")


@app.command(name="match")
@handle_issues
def cli_pick_match(
    pick_id: Annotated[
        uuid.UUID | None,
        Parameter(
            name="pick",
            help="UUID (or unique prefix) of an unmatched pick.",
            converter=UuidConverter(AimbatPick),
        ),
    ] = None,
    seismogram_id: Annotated[
        uuid.UUID | None,
        Parameter(
            name="seismogram",
            help="UUID (or unique prefix) of a seismogram of the pick's event.",
            converter=UuidConverter(AimbatSeismogram),
        ),
    ] = None,
    *,
    retry: Annotated[
        bool,
        Parameter(
            help="Retry matching the unmatched picks read with a station code.",
            negative=(),
        ),
    ] = False,
    event_id: Annotated[
        uuid.UUID | Literal["all"] | None, event_parameter_with_all()
    ] = None,
    auto_snapshot: Annotated[bool, _snapshot_option] = True,
) -> None:
    """Match an unmatched pick to a seismogram, and promote it if named.

    The seismogram must belong to the event of the pick. A station code the
    pick was read with that differs from the seismogram's is reported. With
    `--retry`, matching is retried for the unmatched picks of an event (all
    events by default) and for picks whose event is not in the project.
    `--event` applies to `--retry` only. Matched picks are promoted, phases
    missing for them are created, and each phase that gains initial picks is
    snapshotted.
    """
    from aimbat.actions import match_pick, retry_pick_matching

    if retry:
        if pick_id is not None or seismogram_id is not None:
            raise ValueError("`--retry` takes no pick or seismogram.")
        result = retry_pick_matching(
            event_id if event_id is not None else "all", auto_snapshot=auto_snapshot
        )
        _print_change(result, f"Matched {len(result.picks)} pick(s).")
        return
    if pick_id is None or seismogram_id is None:
        raise ValueError("Give a pick and a seismogram, or `--retry`.")
    result = match_pick(pick_id, seismogram_id, auto_snapshot=auto_snapshot)
    _print_change(result, "Matched 1 pick(s).")


@app.command(name="set")
@handle_issues
def cli_pick_set(
    seismogram_id: Annotated[
        uuid.UUID,
        Parameter(
            name="seismogram",
            help="UUID (or unique prefix) of the seismogram.",
            converter=UuidConverter(AimbatSeismogram),
        ),
    ],
    phase: Annotated[
        str, Parameter(help="Name of the phase.", converter=PhaseNameConverter())
    ],
    time: Annotated[str, Parameter(help="Time of the pick: ISO 8601 with an offset.")],
    *,
    replace: Annotated[
        bool,
        Parameter(
            help="Replace the pick of an existing row. The replaced pick is "
            + "dismissed.",
            negative=(),
        ),
    ] = False,
) -> None:
    """Set the initial pick of a seismogram for a phase from a manual pick.

    The manual pick is stored and promoted, and the phase is created if it
    is missing. A seismogram that already has an initial pick for the phase
    keeps it unless `--replace` is given. Refined picks are set with
    `aimbat tool pick`.
    """
    from aimbat.actions import set_initial_pick

    result = set_initial_pick(
        seismogram_id, phase, _absolute_time(time, relative=False), replace=replace
    )
    _print_change(result, None)


@app.command(name="remove")
@handle_issues
def cli_pick_remove(
    pick_ids: Annotated[
        list[uuid.UUID] | None,
        Parameter(
            name="pick",
            help="UUIDs (or unique prefixes) of picks.",
            converter=UuidConverter(AimbatPick),
            consume_multiple=True,
            negative_iterable=(),
        ),
    ] = None,
    *,
    event_id: Annotated[uuid.UUID | None, _event_option] = None,
    unnamed: Annotated[
        bool, Parameter(help="Only picks without a phase name.", negative=())
    ] = False,
    unmatched: Annotated[
        bool, Parameter(help="Only picks not matched to a seismogram.", negative=())
    ] = False,
    label: Annotated[
        str | None, Parameter(help="Only picks read with this label.")
    ] = None,
    purge: Annotated[
        bool,
        Parameter(
            help="Delete the picks instead of dismissing them. Dismissed picks "
            + "are selected too.",
            negative=(),
        ),
    ] = False,
) -> None:
    """Dismiss the selected picks, and delete their rows.

    Picks are selected by ID, or by the criteria given, which all apply. A
    dismissed pick is kept but left out of promotion and of `aimbat data
    check`, and `aimbat pick restore` brings it back. With `--purge`, the
    picks are deleted. A deleted pick of a data source is stored again when
    the source is read again.
    """
    from rich.console import Console

    from aimbat.actions import remove_picks
    from aimbat.core import PickSelection

    selection = PickSelection(
        pick_ids=tuple(pick_ids or ()),
        event_id=event_id,
        label=label,
        unnamed=unnamed,
        unmatched=unmatched,
    )
    result = remove_picks(selection, purge=purge)
    verb = "Deleted" if purge else "Dismissed"
    Console().print(
        f"{verb} {len(result.picks)} pick(s). Deleted {result.rows_deleted} row(s)."
    )


@app.command(name="restore")
@handle_issues
def cli_pick_restore(
    pick_ids: Annotated[
        list[uuid.UUID] | None,
        Parameter(
            name="pick",
            help="UUIDs (or unique prefixes) of dismissed picks.",
            converter=UuidConverter(AimbatPick),
            consume_multiple=True,
            negative_iterable=(),
        ),
    ] = None,
    *,
    event_id: Annotated[
        uuid.UUID | None,
        Parameter(
            name="event",
            help="Every dismissed pick of this event: UUID (or unique prefix).",
            converter=UuidConverter(AimbatEvent),
        ),
    ] = None,
    auto_snapshot: Annotated[bool, _snapshot_option] = True,
) -> None:
    """Undo the dismissal of picks, and promote those named and matched.

    Picks are selected by ID, or as every dismissed pick of an event. Phases
    missing for the picks are created, and each phase that gains initial
    picks is snapshotted.
    """
    from aimbat.actions import restore_picks
    from aimbat.core import PickSelection

    selection = PickSelection(pick_ids=tuple(pick_ids or ()), event_id=event_id)
    result = restore_picks(selection, auto_snapshot=auto_snapshot)
    _print_change(result, f"Restored {len(result.picks)} pick(s).")


if __name__ == "__main__":
    app()
