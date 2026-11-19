"""Align seismograms using ICCS or MCCC.

This command aligns seismograms using either the ICCS or MCCC algorithm. Both
commands update the refined pick (`refined_pick`). Where it is not yet set,
the initial pick is the starting point.
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
    phase_parameter,
    print_warning,
    resolve_phase_option,
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
    phase: Annotated[str | None, phase_parameter()] = None,
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
    """Run the ICCS algorithm to align the seismograms of a phase.

    Iteratively cross-correlates seismograms against a running stack to refine
    arrival time picks (`refined_pick`). Where a refined pick is not yet set,
    the initial pick is the starting point.
    """
    from aimbat.actions import run_iccs

    with _summarised_warnings():
        run = run_iccs(
            resolve_phase_option(event_id, phase),
            autoflip=autoflip,
            autoselect=autoselect,
        )
    _print_run_summary(run.summary)


@app.command(name="mccc")
@handle_issues
def cli_mccc_run(
    event_id: Annotated[UUID, event_parameter()],
    *,
    phase: Annotated[str | None, phase_parameter()] = None,
    all_seismograms: Annotated[
        bool,
        Parameter(
            name="all",
            help=(
                "Include all seismograms of the phase in MCCC processing, not just the"
                + " currently selected ones."
            ),
        ),
    ] = False,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Run the MCCC algorithm to refine the arrival time picks of a phase.

    Multi-channel cross-correlation simultaneously determines the optimal time
    shifts for all seismograms. Results are stored as refined picks
    (`refined_pick`).
    """
    from aimbat.actions import run_mccc

    with _summarised_warnings():
        run = run_mccc(
            resolve_phase_option(event_id, phase), all_seismograms=all_seismograms
        )
    _print_run_summary(run.summary)


if __name__ == "__main__":
    app()
