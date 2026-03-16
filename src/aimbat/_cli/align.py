"""Align seismograms using ICCS or MCCC.

This command aligns seismograms using either the ICCS or MCCC algorithm. Both
commands update the pick stored in `t1`. If `t1` is `None`, `t0` is used as
starting point instead, with the resulting pick stored in `t1`.
"""

from dataclasses import dataclass
from typing import Annotated

from cyclopts import App, Parameter

from .common import GlobalParameters, _DebugTrait, _EventContextTrait, simple_exception

__all__ = ["cli_iccs_run", "cli_mccc_run"]

app = App(name="align", help=__doc__, help_format="markdown")


@Parameter(name="*")
@dataclass
class _IccsParametersTrait:
    autoflip: Annotated[
        bool,
        Parameter(
            name="autoflip",
            help="Whether to automatically flip seismograms (multiply data"
            " by -1) when the cross-correlation is negative.",
        ),
    ] = False
    autoselect: Annotated[
        bool,
        Parameter(
            name="autoselect",
            help="Whether to automatically de-select seismograms whose"
            " cross-correlation with the stack falls below `min_cc`, and"
            " re-select them if the cross-correlation later exceeds `min_cc`.",
        ),
    ] = False


@dataclass
class _IccsParameters(_IccsParametersTrait, _EventContextTrait, _DebugTrait):
    pass


@app.command(name="iccs")
@simple_exception
def cli_iccs_run(
    *,
    iccs_parameters: _IccsParameters = _IccsParameters(),
) -> None:
    """Run the ICCS algorithm to align seismograms for the default event.

    Iteratively cross-correlates seismograms against a running stack to refine
    arrival time picks (`t1`). If `t1` is not yet set, `t0` is used as the
    starting point.

    Args:
        autoflip: Whether to automatically flip seismograms (multiply data by -1)
            when the cross-correlation is negative.
        autoselect: Whether to automatically de-select seismograms whose
            cross-correlation with the stack falls below `min_cc`.
    """
    from sqlmodel import Session

    from aimbat.core import create_iccs_instance, resolve_event, run_iccs
    from aimbat.db import engine

    with Session(engine) as session:
        event = resolve_event(session, iccs_parameters.event_id)
        iccs = create_iccs_instance(session, event).iccs
        run_iccs(
            session, event, iccs, iccs_parameters.autoflip, iccs_parameters.autoselect
        )


@app.command(name="mccc")
@simple_exception
def cli_mccc_run(
    *,
    all_seismograms: Annotated[
        bool,
        Parameter(
            name="all",
            help="Include all seismograms in MCCC processing, not just the "
            "currently selected ones",
        ),
    ] = False,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Run the MCCC algorithm to refine arrival time picks for the default event.

    Multi-channel cross-correlation simultaneously determines the optimal time
    shifts for all seismograms. Results are stored in `t1`.
    """
    from sqlmodel import Session

    from aimbat.core import create_iccs_instance, resolve_event, run_mccc
    from aimbat.db import engine

    with Session(engine) as session:
        event = resolve_event(session, global_parameters.event_id)
        iccs = create_iccs_instance(session, event).iccs
        run_mccc(session, event, iccs, all_seismograms)


if __name__ == "__main__":
    app()
