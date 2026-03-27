"""Launch interactive tools for picking phase arrival times and processing parameters.

Each subcommand opens an interactive matplotlib plot for an event. Use
`--event-id` or set the `DEFAULT_EVENT_ID` environment variable to choose
which event to work with. Click on the plot to set the chosen value, then
close the window to save it.
"""

from typing import Annotated
from uuid import UUID

from cyclopts import App

from .common import (
    DebugParameter,
    IccsPlotParameters,
    event_parameter,
    simple_exception,
    use_matrix_image,
)

app = App(name="tool", help=__doc__, help_format="markdown")


@app.command(name="bandpass")
@simple_exception
def cli_update_bandpass(
    event_id: Annotated[UUID, event_parameter()],
    *,
    iccs_plot_parameters: IccsPlotParameters = IccsPlotParameters(),
    use_matrix_image: Annotated[bool, use_matrix_image()] = False,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Interactively update the bandpass filter parameters for an event.

    Opens an interactive plot with controls for enabling/disabling the bandpass
    filter and adjusting the minimum and maximum frequencies. Close the window
    to save the updated parameters.
    """
    from sqlmodel import Session

    from aimbat.core import create_iccs_instance, resolve_event
    from aimbat.db import engine
    from aimbat.plot import update_bandpass

    with Session(engine) as session:
        event = resolve_event(session, event_id)
        iccs = create_iccs_instance(session, event).iccs
        update_bandpass(
            session,
            event,
            iccs,
            context=iccs_plot_parameters.context,
            all_seismograms=iccs_plot_parameters.all_seismograms,
            use_matrix_image=use_matrix_image,
            return_fig=False,
        )


@app.command(name="phase")
@simple_exception
def cli_update_phase_pick(
    event_id: Annotated[UUID, event_parameter()],
    *,
    iccs_plot_parameters: IccsPlotParameters = IccsPlotParameters(),
    use_matrix_image: Annotated[bool, use_matrix_image()] = False,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Interactively pick a new phase arrival time (t1) for an event.

    Opens an interactive plot; click to place the new pick, then close the window
    to save. The pick is stored as `t1` for each seismogram in the ICCS instance.
    """
    from sqlmodel import Session

    from aimbat.core import create_iccs_instance, resolve_event
    from aimbat.db import engine
    from aimbat.plot import update_pick

    with Session(engine) as session:
        event = resolve_event(session, event_id)
        iccs = create_iccs_instance(session, event).iccs
        update_pick(
            session,
            iccs,
            context=iccs_plot_parameters.context,
            all_seismograms=iccs_plot_parameters.all_seismograms,
            use_matrix_image=use_matrix_image,
            return_fig=False,
        )


@app.command(name="window")
@simple_exception
def cli_pick_timewindow(
    event_id: Annotated[UUID, event_parameter()],
    *,
    iccs_plot_parameters: IccsPlotParameters = IccsPlotParameters(),
    use_matrix_image: Annotated[bool, use_matrix_image()] = False,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Interactively pick a new cross-correlation time window for an event.

    Opens an interactive plot; click to set the left and right window boundaries,
    then close the window to save. The window controls which portion of each
    seismogram is used during ICCS alignment.
    """
    from sqlmodel import Session

    from aimbat.core import create_iccs_instance, resolve_event
    from aimbat.db import engine
    from aimbat.plot import update_timewindow

    with Session(engine) as session:
        event = resolve_event(session, event_id)
        iccs = create_iccs_instance(session, event).iccs
        update_timewindow(
            session,
            event,
            iccs,
            iccs_plot_parameters.context,
            all_seismograms=iccs_plot_parameters.all_seismograms,
            use_matrix_image=use_matrix_image,
            return_fig=False,
        )


@app.command(name="cc")
@simple_exception
def cli_pick_min_cc(
    event_id: Annotated[UUID, event_parameter()],
    *,
    iccs_plot_parameters: IccsPlotParameters = IccsPlotParameters(),
    use_matrix_image: Annotated[bool, use_matrix_image()] = True,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Interactively pick a new minimum cross-correlation for auto-selection.

    Opens an interactive plot; scroll to set the cc threshold. Seismograms
    whose cross-correlation with the stack falls below this value will be
    automatically de-selected when running ICCS with `--autoselect`.
    """
    from sqlmodel import Session

    from aimbat.core import create_iccs_instance, resolve_event
    from aimbat.db import engine
    from aimbat.plot import update_min_cc

    with Session(engine) as session:
        event = resolve_event(session, event_id)
        iccs = create_iccs_instance(session, event).iccs
        update_min_cc(
            session,
            event,
            iccs,
            iccs_plot_parameters.context,
            all_seismograms=iccs_plot_parameters.all_seismograms,
            return_fig=False,
        )


if __name__ == "__main__":
    app()
