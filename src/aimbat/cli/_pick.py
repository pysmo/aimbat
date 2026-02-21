"""Interactively update parameters controlling the ICCS algorithm."""

from typing import Annotated
from ._common import GlobalParameters, IccsPlotParameters, simple_exception
from cyclopts import App, Parameter

app = App(name="pick", help=__doc__, help_format="markdown")


@app.command(name="phase")
@simple_exception
def cli_update_phase_pick(
    *,
    iccs_parameters: IccsPlotParameters | None = None,
    use_seismogram_image: Annotated[bool, Parameter(name="img")] = False,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Pick a new phase arrival time.

    Args:
        use_seismogram_image: Use the seismogram image to update pick.
    """
    from aimbat.db import engine
    from aimbat.core import create_iccs_instance, update_pick
    from sqlmodel import Session

    iccs_parameters = iccs_parameters or IccsPlotParameters()
    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        iccs = create_iccs_instance(session)
        update_pick(
            session,
            iccs,
            iccs_parameters.context,
            iccs_parameters.all,
            use_seismogram_image,
        )


@app.command(name="window")
@simple_exception
def cli_pick_timewindow(
    *,
    iccs_parameters: IccsPlotParameters | None = None,
    use_seismogram_image: Annotated[bool, Parameter(name="img")] = False,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Pick a new time window.

    Args:
        use_seismogram_image: Use the seismogram image to pick the time window.
    """
    from aimbat.db import engine
    from aimbat.core import create_iccs_instance, update_timewindow
    from sqlmodel import Session

    iccs_parameters = iccs_parameters or IccsPlotParameters()
    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        iccs = create_iccs_instance(session)
        update_timewindow(
            session,
            iccs,
            iccs_parameters.context,
            iccs_parameters.all,
            use_seismogram_image,
        )


@app.command(name="ccnorm")
@simple_exception
def cli_pick_min_ccnorm(
    *,
    iccs_parameters: IccsPlotParameters | None = None,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Pick a new minimum cross-correlation norm for auto-selection."""
    from aimbat.db import engine
    from aimbat.core import create_iccs_instance, update_min_ccnorm
    from sqlmodel import Session

    iccs_parameters = iccs_parameters or IccsPlotParameters()
    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        iccs = create_iccs_instance(session)
        update_min_ccnorm(session, iccs, iccs_parameters.context, iccs_parameters.all)


if __name__ == "__main__":
    app()
