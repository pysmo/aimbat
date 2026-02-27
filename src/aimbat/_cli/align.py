"""Align seismograms using ICCS or MCCC.

This command aligns seismograms using either the ICCS or MCCC algorithm. Both
commands update the pick stored in `t1`. If `t1` is `None`, `t0` is used as
starting point instead, with the resulting pick stored in `t1`.
"""

from .common import GlobalParameters, simple_exception
from cyclopts import App, Parameter
from typing import Annotated

app = App(name="align", help=__doc__, help_format="markdown")


@app.command(name="iccs")
@simple_exception
def cli_iccs_run(
    *,
    autoflip: bool = False,
    autoselect: bool = False,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Run the ICCS algorithm to align seismograms for the active event.

    Iteratively cross-correlates seismograms against a running stack to refine
    arrival time picks (`t1`). If `t1` is not yet set, `t0` is used as the
    starting point.

    Args:
        autoflip: Whether to automatically flip seismograms (multiply data by -1)
            when the cross-correlation is negative.
        autoselect: Whether to automatically de-select seismograms whose
            cross-correlation with the stack falls below `min_ccnorm`.
    """
    from aimbat.db import engine
    from aimbat.core import create_iccs_instance, run_iccs
    from sqlmodel import Session

    with Session(engine) as session:
        iccs = create_iccs_instance(session)
        run_iccs(session, iccs, autoflip, autoselect)


@app.command(name="mccc")
@simple_exception
def cli_mccc_run(
    *,
    all_seismograms: Annotated[bool, Parameter(name="all")] = False,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Run the MCCC algorithm to refine arrival time picks for the active event.

    Multi-channel cross-correlation simultaneously determines the optimal time
    shifts for all seismograms. Results are stored in `t1`.

    Args:
        all_seismograms: Include all seismograms in MCCC processing, not just
            the currently selected ones.
    """
    from aimbat.db import engine
    from aimbat.core import create_iccs_instance, run_mccc
    from sqlmodel import Session

    with Session(engine) as session:
        iccs = create_iccs_instance(session)
        run_mccc(session, iccs, all_seismograms)


if __name__ == "__main__":
    app()
