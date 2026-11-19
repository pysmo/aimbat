"""Interactive tool registry for the AIMBAT TUI.

Extend `TOOL_REGISTRY`/`CAUSAL_TOOL_REGISTRY` to register new interactive
tools. Each entry maps a key to a (label, callable) pair. Callables in
`TOOL_REGISTRY` receive (phase_id, iccs, context, all_seismograms); callables
in `CAUSAL_TOOL_REGISTRY` additionally receive a causal argument from
`InteractiveToolsModal`'s zero-phase toggle. Both return None.

A tool blocks for as long as its plot window is open, so none of them is
handed a database session. Those that change a value save it through
`aimbat.actions` once the window closes.
"""

from collections.abc import Callable
from uuid import UUID

from pysmo.tools.iccs import ICCS

from aimbat.actions import set_phase_parameters, set_refined_picks
from aimbat.plot import (
    plot_matrix_image,
    plot_stack,
    update_bandpass,
    update_min_cc,
    update_pick,
    update_timewindow,
)

type ToolFn = Callable[[UUID, ICCS, bool, bool], None]
type CausalToolFn = Callable[[UUID, ICCS, bool, bool, bool], None]


def _tool_pick(
    phase_id: UUID,
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
    causal: bool,
) -> None:
    """Launch the interactive tool for the refined pick."""
    picks = update_pick(
        iccs,
        context,
        all_seismograms=all_seismograms,
        use_matrix_image=False,
        causal=causal,
        return_fig=False,
    )
    set_refined_picks(phase_id, picks)


def _tool_window(
    phase_id: UUID,
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
    causal: bool,
) -> None:
    """Launch the interactive time-window selection tool."""
    changes = update_timewindow(
        iccs,
        context,
        all_seismograms=all_seismograms,
        use_matrix_image=False,
        causal=causal,
        return_fig=False,
    )
    set_phase_parameters(phase_id, changes)


def _tool_cc(
    phase_id: UUID,
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
    causal: bool,
) -> None:
    """Launch the interactive minimum-CC threshold tool."""
    changes = update_min_cc(
        iccs,
        context,
        all_seismograms=all_seismograms,
        causal=causal,
        return_fig=False,
    )
    set_phase_parameters(phase_id, changes)


def _tool_bandpass(
    phase_id: UUID,
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
) -> None:
    """Launch the interactive bandpass-filter tool."""
    changes = update_bandpass(
        iccs,
        context,
        all_seismograms=all_seismograms,
        use_matrix_image=False,
        return_fig=False,
    )
    set_phase_parameters(phase_id, changes)


def _tool_stack(
    phase_id: UUID,
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
) -> None:
    """Show the interactive stack plot."""
    # phase_id is unused here but required by ToolFn for a uniform
    # TOOL_REGISTRY signature.
    plot_stack(iccs, context, all_seismograms, return_fig=False)


def _tool_image(
    phase_id: UUID,
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
) -> None:
    """Show the interactive cross-correlation matrix image."""
    # phase_id is unused here but required by ToolFn for a uniform
    # TOOL_REGISTRY signature.
    plot_matrix_image(iccs, context, all_seismograms, return_fig=False)


TOOL_REGISTRY: dict[str, tuple[str, ToolFn]] = {
    "bandpass": ("Bandpass filter", _tool_bandpass),
    "stack": ("Stack plot", _tool_stack),
    "image": ("Matrix image", _tool_image),
}
CAUSAL_TOOL_REGISTRY: dict[str, tuple[str, CausalToolFn]] = {
    "pick": ("Refined pick", _tool_pick),
    "window": ("Time window", _tool_window),
    "cc": ("Min CC", _tool_cc),
}

VIEW_ONLY_TOOLS: frozenset[str] = frozenset({"stack", "image"})
"""Tools that only display; every other tool persists a parameter or pick change
and so requires the ICCS instance (and its `iccs_cc` quality) to be rebuilt."""
