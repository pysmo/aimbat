"""Interactively pick phase arrival times and processing parameters.

These commands open an interactive matplotlib plot for the default event.
Click on the plot to set the chosen value, then close the window to save it.
Use `aimbat event default` to switch the default event before picking.
"""

from typing import Annotated

from cyclopts import App, Parameter

from .common import GlobalParameters, IccsPlotParameters, simple_exception

app = App(name="pick", help=__doc__, help_format="markdown")


@app.command(name="phase")
@simple_exception
def cli_update_phase_pick(
    *,
    iccs_parameters: IccsPlotParameters = IccsPlotParameters(),
    use_seismogram_image: Annotated[bool, Parameter(name="img")] = False,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Interactively pick a new phase arrival time (t1) for the default event.

    Opens an interactive plot; click on the waveform to place the new pick,
    then close the window to save. The pick is stored as `t1` for each
    selected seismogram.

    Args:
        use_seismogram_image: Use the seismogram image to update pick.
    """
    from sqlmodel import Session

    from aimbat.core import create_iccs_instance, resolve_event, update_pick
    from aimbat.db import engine

    with Session(engine) as session:
        event = resolve_event(session, global_parameters.event_id)
        iccs = create_iccs_instance(session, event).iccs
        update_pick(
            session,
            iccs,
            iccs_parameters.context,
            iccs_parameters.all,
            use_seismogram_image,
            return_fig=False,
        )


@app.command(name="window")
@simple_exception
def cli_pick_timewindow(
    *,
    iccs_parameters: IccsPlotParameters = IccsPlotParameters(),
    use_seismogram_image: Annotated[bool, Parameter(name="img")] = False,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Interactively pick a new cross-correlation time window for an event.

    Opens an interactive plot; click to set the left and right window boundaries,
    then close the window to save. The window controls which portion of the
    seismogram is used during ICCS alignment.

    Args:
        use_seismogram_image: Use the seismogram image to pick the time window.
    """
    from sqlmodel import Session

    from aimbat.core import create_iccs_instance, resolve_event, update_timewindow
    from aimbat.db import engine

    with Session(engine) as session:
        event = resolve_event(session, global_parameters.event_id)
        iccs = create_iccs_instance(session, event).iccs
        update_timewindow(
            session,
            event,
            iccs,
            iccs_parameters.context,
            iccs_parameters.all,
            use_seismogram_image,
            return_fig=False,
        )


@app.command(name="ccnorm")
@simple_exception
def cli_pick_min_ccnorm(
    *,
    iccs_parameters: IccsPlotParameters = IccsPlotParameters(),
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Interactively pick a new minimum cross-correlation norm for auto-selection.

    Opens an interactive plot; click to set the ccnorm threshold. Seismograms
    whose cross-correlation with the stack falls below this value will be
    automatically de-selected when running ICCS with `--autoselect`.
    """
    from sqlmodel import Session

    from aimbat.core import create_iccs_instance, resolve_event, update_min_ccnorm
    from aimbat.db import engine

    with Session(engine) as session:
        event = resolve_event(session, global_parameters.event_id)
        iccs = create_iccs_instance(session, event).iccs
        update_min_ccnorm(
            session,
            event,
            iccs,
            iccs_parameters.context,
            iccs_parameters.all,
            return_fig=False,
        )


if __name__ == "__main__":
    app()
