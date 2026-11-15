"""Align seismograms using ICCS or MCCC.

This command aligns seismograms using either the ICCS or MCCC algorithm. Both
commands update the pick stored in `t1`. If `t1` is `None`, `t0` is used as
starting point instead, with the resulting pick stored in `t1`.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from cyclopts import App, Parameter

from .common import (
    DebugParameter,
    event_parameter,
    handle_issues,
    print_warning,
)

__all__ = ["cli_iccs_run", "cli_mccc_run"]

if TYPE_CHECKING:
    from aimbat.core import RunSummary

app = App(name="align", help=__doc__, help_format="markdown")


@contextmanager
def _summarised_warnings() -> Iterator[None]:
    """Silence the pysmo warnings that the printed run summary already covers."""
    import warnings

    from aimbat.core import ignore_run_summary_warnings

    with warnings.catch_warnings():
        ignore_run_summary_warnings()
        yield


def _print_run_summary(summary: "RunSummary") -> None:
    """Print a run summary, as a warning if it needs the user's attention."""
    if summary.warning:
        print_warning(summary.message)
    else:
        from rich.console import Console

        Console().print(summary.message, markup=False, highlight=False)


@app.command(name="iccs")
@handle_issues
def cli_iccs_run(
    event_id: Annotated[UUID, event_parameter()],
    *,
    autoselect: Annotated[
        bool,
        Parameter(
            name="autoselect",
            help=(
                "Whether to automatically de-select seismograms whose "
                + "cross-correlation with the stack falls below `min_cc`, and re-select"
                + " them if the cross-correlation later exceeds `min_cc`."
            ),
        ),
    ] = False,
    autoflip: Annotated[
        bool,
        Parameter(
            name="autoflip",
            help=(
                "Whether to automatically flip seismograms (multiply data by -1) when"
                + " the cross-correlation is negative."
            ),
        ),
    ] = False,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Run the ICCS algorithm to align seismograms for an event.

    Iteratively cross-correlates seismograms against a running stack to refine
    arrival time picks (`t1`). If `t1` is not yet set, `t0` is used as the
    starting point.
    """
    from sqlmodel import Session

    from aimbat.core import (
        create_iccs_instance,
        resolve_event,
        run_iccs,
        summarise_iccs_result,
    )
    from aimbat.db import engine

    with Session(engine) as session:
        event = resolve_event(session, event_id)
        iccs = create_iccs_instance(session, event).iccs
        with _summarised_warnings():
            result = run_iccs(session, event, iccs, autoflip, autoselect)
        _print_run_summary(summarise_iccs_result(result, len(iccs.seismograms)))


@app.command(name="mccc")
@handle_issues
def cli_mccc_run(
    event_id: Annotated[UUID, event_parameter()],
    *,
    all_seismograms: Annotated[
        bool,
        Parameter(
            name="all",
            help=(
                "Include all seismograms of an event in MCCC processing, not just the"
                + " currently selected ones."
            ),
        ),
    ] = False,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Run the MCCC algorithm to refine arrival time picks for an event.

    Multi-channel cross-correlation simultaneously determines the optimal time
    shifts for all seismograms. Results are stored in `t1`.
    """
    from sqlmodel import Session

    from aimbat.core import (
        create_iccs_instance,
        resolve_event,
        run_mccc,
        summarise_mccc_result,
    )
    from aimbat.db import engine

    with Session(engine) as session:
        event = resolve_event(session, event_id)
        iccs = create_iccs_instance(session, event).iccs
        with _summarised_warnings():
            result = run_mccc(session, event, iccs, all_seismograms)
        _print_run_summary(summarise_mccc_result(result))


if __name__ == "__main__":
    app()
