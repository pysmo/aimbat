"""Align seismograms using ICCS or MCCC.

This command aligns seismograms using either the ICCS or MCCC algorithm. Both
commands update the pick stored in `t1`. If `t1` is `None`, `t0` is used as
starting point instead, with the resulting pick stored in `t1`.
"""

from ._common import GlobalParameters, simple_exception
from cyclopts import App, Parameter
from typing import Annotated

app = App(name="align", help=__doc__, help_format="markdown")


@app.command(name="iccs")
@simple_exception
def cli_iccs_run(
    *,
    autoflip: bool = False,
    autoselect: bool = False,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Run the ICCS algorithm.

    Args:
        autoflip: Whether to automatically flip seismograms (multiply data by -1).
        autoselect: Whether to automatically de-select seismograms.
    """
    from aimbat.db import engine
    from aimbat.core import create_iccs_instance, run_iccs
    from sqlmodel import Session

    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        iccs = create_iccs_instance(session)
        run_iccs(session, iccs, autoflip, autoselect)


@app.command(name="mccc")
@simple_exception
def cli_mccc_run(
    *,
    all_seismograms: Annotated[bool, Parameter(name="all")] = False,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Run the MCCC algorithm.

    Args:
        all_seismograms: Whether to include all seismograms in the MCCC processing, or just the selected ones.
    """
    from aimbat.db import engine
    from aimbat.core import create_iccs_instance, run_mccc
    from sqlmodel import Session

    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        iccs = create_iccs_instance(session)
        run_mccc(session, iccs, all_seismograms)


if __name__ == "__main__":
    app()
