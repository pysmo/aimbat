"""Interactive tool registry for the AIMBAT TUI.

Extend `TOOL_REGISTRY`/`CAUSAL_TOOL_REGISTRY` to register new interactive
tools. Each entry maps a key to a (label, callable) pair. Callables in
`TOOL_REGISTRY` receive (session, event, iccs, context, all_seismograms);
callables in `CAUSAL_TOOL_REGISTRY` additionally receive a causal argument
from `InteractiveToolsModal`'s zero-phase toggle. Both return None.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlmodel import Session

from pysmo.tools.iccs import ICCS

from aimbat.models import AimbatEvent
from aimbat.plot import (
    plot_matrix_image,
    plot_stack,
    update_bandpass,
    update_min_cc,
    update_pick,
    update_timewindow,
)

type ToolFn = Callable[[Session, AimbatEvent, ICCS, bool, bool], None]
type CausalToolFn = Callable[[Session, AimbatEvent, ICCS, bool, bool, bool], None]


def _tool_phase(
    session: Session,
    event: AimbatEvent,
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
    causal: bool,
) -> None:
    """Launch the interactive phase-arrival (t1) picking tool."""
    update_pick(
        session,
        iccs,
        context,
        all_seismograms=all_seismograms,
        use_matrix_image=False,
        causal=causal,
        return_fig=False,
    )


def _tool_window(
    session: Session,
    event: AimbatEvent,
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
    causal: bool,
) -> None:
    """Launch the interactive time-window selection tool."""
    update_timewindow(
        session,
        event,
        iccs,
        context,
        all_seismograms=all_seismograms,
        use_matrix_image=False,
        causal=causal,
        return_fig=False,
    )


def _tool_cc(
    session: Session,
    event: AimbatEvent,
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
    causal: bool,
) -> None:
    """Launch the interactive minimum-CC threshold tool."""
    update_min_cc(
        session,
        event,
        iccs,
        context,
        all_seismograms=all_seismograms,
        causal=causal,
        return_fig=False,
    )


def _tool_bandpass(
    session: Session,
    event: AimbatEvent,
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
) -> None:
    """Launch the interactive bandpass-filter tool."""
    update_bandpass(
        session,
        event,
        iccs,
        context,
        all_seismograms=all_seismograms,
        use_matrix_image=False,
        return_fig=False,
    )


def _tool_stack(
    session: Session,
    event: AimbatEvent,
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
) -> None:
    """Show the interactive stack plot."""
    # session/event are unused here but required by ToolFn for a uniform
    # TOOL_REGISTRY signature.
    plot_stack(iccs, context, all_seismograms, return_fig=False)


def _tool_image(
    session: Session,
    event: AimbatEvent,
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
) -> None:
    """Show the interactive cross-correlation matrix image."""
    # session/event are unused here but required by ToolFn for a uniform
    # TOOL_REGISTRY signature.
    plot_matrix_image(iccs, context, all_seismograms, return_fig=False)


TOOL_REGISTRY: dict[str, tuple[str, ToolFn]] = {
    "bandpass": ("Bandpass filter", _tool_bandpass),
    "stack": ("Stack plot", _tool_stack),
    "image": ("Matrix image", _tool_image),
}
CAUSAL_TOOL_REGISTRY: dict[str, tuple[str, CausalToolFn]] = {
    "phase": ("Phase arrival (t1)", _tool_phase),
    "window": ("Time window", _tool_window),
    "cc": ("Min CC", _tool_cc),
}
