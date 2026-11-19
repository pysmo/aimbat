"""Launch interactive tools for setting refined picks and processing parameters.

Each subcommand opens an interactive matplotlib plot for one phase of an
event. The event is chosen with `--event-id` or the `DEFAULT_EVENT_ID`
environment variable, and the phase with `--phase` or `DEFAULT_PHASE`, which
may be omitted when the event has only one phase. Interact with the plot
(click or scroll, depending on the tool) to set the chosen value, then close
the window to save it.

No database session is open while the window is, so an open plot holds no
database connection. The new value is saved once the window closes.
"""

from typing import Annotated
from uuid import UUID

from cyclopts import App

from .common import (
    CAUSAL_DEFAULTS,
    DebugParameter,
    IccsPlotParameters,
    event_parameter,
    handle_issues,
    phase_parameter,
    resolve_phase_option,
)
from .common import (
    causal as causal_param,
)
from .common import (
    use_matrix_image as use_matrix_image_param,
)

app = App(name="tool", help=__doc__, help_format="markdown")


@app.command(name="bandpass")
@handle_issues
def cli_update_bandpass(
    event_id: Annotated[UUID, event_parameter()],
    *,
    phase: Annotated[str | None, phase_parameter()] = None,
    iccs_plot_parameters: IccsPlotParameters = IccsPlotParameters(),
    use_matrix_image: Annotated[bool, use_matrix_image_param()] = False,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Interactively update the bandpass filter parameters of a phase.

    Opens an interactive plot with controls for enabling/disabling the bandpass
    filter and adjusting the minimum and maximum frequencies. Close the window
    to save the updated parameters.
    """
    from aimbat.actions import prepare_iccs, set_phase_parameters
    from aimbat.plot import update_bandpass

    bound = prepare_iccs(resolve_phase_option(event_id, phase))
    changes = update_bandpass(
        bound.iccs,
        context=iccs_plot_parameters.context,
        all_seismograms=iccs_plot_parameters.all_seismograms,
        use_matrix_image=use_matrix_image,
        return_fig=False,
    )
    set_phase_parameters(bound.phase_id, changes)


@app.command(name="pick")
@handle_issues
def cli_update_pick(
    event_id: Annotated[UUID, event_parameter()],
    *,
    phase: Annotated[str | None, phase_parameter()] = None,
    iccs_plot_parameters: IccsPlotParameters = IccsPlotParameters(),
    use_matrix_image: Annotated[bool, use_matrix_image_param()] = False,
    causal: Annotated[bool, causal_param()] = CAUSAL_DEFAULTS["pick"],
    _: DebugParameter = DebugParameter(),
) -> None:
    """Interactively set the refined pick of every seismogram of a phase.

    Opens an interactive plot; click on the stack to place the new pick,
    then close the window to save. The pick is stored as the refined pick
    (`refined_pick`) of each seismogram. The initial picks are unchanged.
    """
    from aimbat.actions import prepare_iccs, set_refined_picks
    from aimbat.plot import update_pick

    bound = prepare_iccs(resolve_phase_option(event_id, phase))
    picks = update_pick(
        bound.iccs,
        context=iccs_plot_parameters.context,
        all_seismograms=iccs_plot_parameters.all_seismograms,
        use_matrix_image=use_matrix_image,
        causal=causal,
        return_fig=False,
    )
    set_refined_picks(bound.phase_id, picks)


@app.command(name="window")
@handle_issues
def cli_pick_timewindow(
    event_id: Annotated[UUID, event_parameter()],
    *,
    phase: Annotated[str | None, phase_parameter()] = None,
    iccs_plot_parameters: IccsPlotParameters = IccsPlotParameters(),
    use_matrix_image: Annotated[bool, use_matrix_image_param()] = False,
    causal: Annotated[bool, causal_param()] = CAUSAL_DEFAULTS["window"],
    _: DebugParameter = DebugParameter(),
) -> None:
    """Interactively pick a new cross-correlation time window for a phase.

    Opens an interactive plot; click to set the left and right window boundaries,
    then close the window to save. The window controls which portion of each
    seismogram is used during ICCS alignment.
    """
    from aimbat.actions import prepare_iccs, set_phase_parameters
    from aimbat.plot import update_timewindow

    bound = prepare_iccs(resolve_phase_option(event_id, phase))
    changes = update_timewindow(
        bound.iccs,
        iccs_plot_parameters.context,
        all_seismograms=iccs_plot_parameters.all_seismograms,
        use_matrix_image=use_matrix_image,
        causal=causal,
        return_fig=False,
    )
    set_phase_parameters(bound.phase_id, changes)


@app.command(name="cc")
@handle_issues
def cli_pick_min_cc(
    event_id: Annotated[UUID, event_parameter()],
    *,
    phase: Annotated[str | None, phase_parameter()] = None,
    iccs_plot_parameters: IccsPlotParameters = IccsPlotParameters(),
    use_matrix_image: Annotated[bool, use_matrix_image_param()] = True,
    causal: Annotated[bool, causal_param()] = CAUSAL_DEFAULTS["cc"],
    _: DebugParameter = DebugParameter(),
) -> None:
    """Interactively pick a new minimum cross-correlation for auto-selection.

    Opens an interactive plot; scroll to set the cc threshold. Seismograms
    whose cross-correlation with the stack falls below this value will be
    automatically de-selected when running ICCS with `--autoselect`.
    """
    from aimbat.actions import prepare_iccs, set_phase_parameters
    from aimbat.plot import update_min_cc

    bound = prepare_iccs(resolve_phase_option(event_id, phase))
    changes = update_min_cc(
        bound.iccs,
        iccs_plot_parameters.context,
        all_seismograms=iccs_plot_parameters.all_seismograms,
        causal=causal,
        return_fig=False,
    )
    set_phase_parameters(bound.phase_id, changes)


if __name__ == "__main__":
    app()
