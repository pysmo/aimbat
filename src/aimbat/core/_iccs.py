"""Processing of data for AIMBAT."""

from dataclasses import dataclass
from uuid import UUID

from pandas import Timestamp
from sqlmodel import Session
from pysmo.tools.iccs import (
    ICCS,
    MiniICCSSeismogram,
    plot_seismograms as _plot_seismograms,
    plot_stack as _plot_stack,
    update_min_ccnorm as _update_min_ccnorm,
    update_pick as _update_pick,
    update_timewindow as _update_timewindow,
)
from aimbat import settings
from aimbat.logger import logger
from aimbat.models import AimbatSeismogram, AimbatEvent
from aimbat.models._parameters import (
    AimbatEventParametersBase,
    AimbatSeismogramParametersBase,
)

_RETURN_FIG_WARNING = (
    "Returning figure and axes objects instead of showing the plot. "
    "This is intended for testing purposes; in normal usage, return_fig should be False."
)

__all__ = [
    "BoundICCS",
    "create_iccs_instance",
    "clear_iccs_cache",
    "validate_iccs_construction",
    "sync_iccs_parameters",
    "run_iccs",
    "run_mccc",
    "plot_stack",
    "plot_iccs_seismograms",
    "update_pick",
    "update_timewindow",
    "update_min_ccnorm",
]


@dataclass
class BoundICCS:
    """An ICCS instance explicitly bound to a specific event.

    Use `is_stale` to detect whether the event's parameters have been modified
    (e.g. by a CLI command) since this instance was created.
    """

    iccs: ICCS
    event_id: UUID
    created_at: Timestamp

    def is_stale(self, event: AimbatEvent) -> bool:
        """Return True if the event has been modified since this ICCS was created.

        Args:
            event: The event to check against.
        """
        if event.id != self.event_id:
            return True
        if event.last_modified is None:
            return False
        return event.last_modified > self.created_at


# Process-level ICCS cache. In normal CLI use this is always cold (one command
# per process). In the shell a warm entry is reused across commands, avoiding
# redundant data loading and ICCS computation.
_iccs_cache: dict[UUID, BoundICCS] = {}


def clear_iccs_cache() -> None:
    """Clear the process-level ICCS cache."""
    _iccs_cache.clear()


def _build_iccs(event: AimbatEvent) -> ICCS:
    """Build an ICCS instance from an event's current parameters and seismograms.

    Args:
        event: AimbatEvent.

    Returns:
        A freshly constructed ICCS instance.
    """
    p = event.parameters
    seismograms = [
        MiniICCSSeismogram(
            begin_time=seis.begin_time,
            delta=seis.delta,
            data=seis.data,
            t0=seis.t0,
            t1=seis.t1,
            flip=seis.flip,
            select=seis.select,
            extra={"id": seis.id},
        )
        for seis in event.seismograms
    ]
    return ICCS(
        seismograms=seismograms,
        window_pre=p.window_pre,
        window_post=p.window_post,
        bandpass_apply=p.bandpass_apply,
        bandpass_fmin=p.bandpass_fmin,
        bandpass_fmax=p.bandpass_fmax,
        min_ccnorm=p.min_ccnorm,
        context_width=settings.context_width,
    )


def create_iccs_instance(session: Session, event: AimbatEvent) -> BoundICCS:
    """Return a BoundICCS instance for the given event.

    Returns the cached instance when it is still fresh (i.e. `event.last_modified`
    has not advanced since the instance was created). Otherwise builds a new one
    and updates the cache.

    `MiniICCSSeismogram` instances are constructed directly from each
    `AimbatSeismogram`, passing `data` by reference to the read-only io cache.
    No waveform data is copied. The session does not need to remain open after
    this call.

    Args:
        session: Database session.
        event: AimbatEvent.

    Returns:
        BoundICCS instance tied to the given event.
    """
    cached = _iccs_cache.get(event.id)
    if cached is not None and not cached.is_stale(event):
        logger.debug(f"Returning cached BoundICCS for event {event.id}.")
        return cached

    logger.info(f"Creating ICCS instance for event {event.id}.")
    bound = BoundICCS(
        iccs=_build_iccs(event),
        event_id=event.id,
        created_at=Timestamp.now("UTC"),
    )
    _iccs_cache[event.id] = bound
    return bound


def validate_iccs_construction(event: AimbatEvent) -> None:
    """Try to construct an ICCS instance for the event without caching the result.

    Use this to check whether the event's current (possibly uncommitted) parameters
    are compatible with ICCS construction before persisting them to the database.

    Args:
        event: AimbatEvent.

    Raises:
        Any exception raised by ICCS construction (e.g. invalid parameter values).
    """
    _build_iccs(event)


def _write_back_seismograms(session: Session, iccs: ICCS) -> None:
    """Write t1, flip, and select from ICCS seismograms back to the database.

    Args:
        session: Database session.
        iccs: ICCS instance whose seismograms carry UUIDs in their extra dict.
    """
    for seis in iccs.seismograms:
        db_seis = session.get(AimbatSeismogram, seis.extra["id"])
        if db_seis is not None:
            db_seis.parameters.t1 = seis.t1
            db_seis.parameters.flip = seis.flip
            db_seis.parameters.select = seis.select
    session.commit()


def sync_iccs_parameters(session: Session, event: AimbatEvent, iccs: ICCS) -> None:
    """Sync an existing ICCS instance's parameters from the database.

    Updates event-level and per-seismogram parameters without re-reading waveform
    data. Use this after operations that change parameters but not the
    seismogram list (e.g. rolling back to a snapshot).

    Args:
        session: Database session.
        event: AimbatEvent.
        iccs: ICCS instance to update in-place.
    """

    logger.info(f"Syncing ICCS parameters from database for event {event.id}.")

    event_params = AimbatEventParametersBase.model_validate(event.parameters)
    for field_name in AimbatEventParametersBase.model_fields:
        if hasattr(iccs, field_name):
            setattr(iccs, field_name, getattr(event_params, field_name))

    for iccs_seis in iccs.seismograms:
        db_seis = session.get(AimbatSeismogram, iccs_seis.extra["id"])
        if db_seis is not None:
            seis_params = AimbatSeismogramParametersBase.model_validate(
                db_seis.parameters
            )
            for field_name in AimbatSeismogramParametersBase.model_fields:
                setattr(iccs_seis, field_name, getattr(seis_params, field_name))

    iccs.clear_cache()


def run_iccs(session: Session, iccs: ICCS, autoflip: bool, autoselect: bool) -> None:
    """Run ICCS algorithm.

    Args:
        session: Database session.
        iccs: ICCS instance.
        autoflip: Whether to automatically flip seismograms.
        autoselect: Whether to automatically select seismograms.
    """

    logger.info(f"Running ICCS with {autoflip=}, {autoselect=}.")

    results = iccs(autoflip=autoflip, autoselect=autoselect)
    logger.info(f"ICCS {results = }")
    _write_back_seismograms(session, iccs)


def run_mccc(
    session: Session, event: AimbatEvent, iccs: ICCS, all_seismograms: bool
) -> None:
    """Run MCCC algorithm.

    Args:
        session: Database session.
        event: AimbatEvent.
        iccs: ICCS instance.
        all_seismograms: Whether to include all seismograms in the MCCC processing, or just the selected ones.
    """

    logger.info(f"Running MCCC for event {event.id} with {all_seismograms=}.")

    iccs.run_mccc(
        all_seismograms=all_seismograms,
        min_cc=event.parameters.mccc_min_ccnorm,
        damping=event.parameters.mccc_damp,
    )
    _write_back_seismograms(session, iccs)


def plot_stack(iccs: ICCS, context: bool, all: bool, return_fig: bool) -> tuple | None:
    """Plot the ICCS stack.

    Args:
        iccs: ICCS instance.
        context: Whether to use seismograms with extra context.
        all: Whether to plot all seismograms.
        return_fig: If True, return the figure and axes objects instead of showing the plot.

    Returns:
        A tuple of (Figure, Axes) if return_fig is True, otherwise None.
    """

    logger.info("Plotting ICCS stack for default event.")
    return _plot_stack(iccs, context, all, return_fig=return_fig)  # type: ignore[call-overload]


def plot_iccs_seismograms(
    iccs: ICCS, context: bool, all: bool, return_fig: bool
) -> tuple | None:
    """Plot the ICCS seismograms as an image.

    Args:
        iccs: ICCS instance.
        context: Whether to use seismograms with extra context.
        all: Whether to plot all seismograms.
        return_fig: If True, return the figure and axes objects instead of showing the plot.

    Returns:
        A tuple of (Figure, Axes) if return_fig is True, otherwise None.
    """

    logger.info("Plotting ICCS seismograms for default event.")

    return _plot_seismograms(iccs, context, all, return_fig=return_fig)  # type: ignore[call-overload]


def update_pick(
    session: Session,
    iccs: ICCS,
    context: bool,
    all: bool,
    use_seismogram_image: bool,
    return_fig: bool,
) -> tuple | None:
    """Update the pick for the default event.

    Args:
        iccs: ICCS instance.
        context: Whether to use seismograms with extra context.
        all: Whether to plot all seismograms.
        use_seismogram_image: Whether to use the seismogram image to update pick.
        return_fig: If True, return the figure and axes objects instead of showing the plot.

    Returns:
        A tuple of (Figure, Axes, widgets) if return_fig is True, otherwise None.
    """

    logger.info("Updating pick for default event.")

    result = _update_pick(  # type: ignore[call-overload]
        iccs, context, all, use_seismogram_image, return_fig=return_fig
    )

    if not return_fig:
        _write_back_seismograms(session, iccs)
        return None

    logger.warning(_RETURN_FIG_WARNING)
    return result


def update_timewindow(
    session: Session,
    event: AimbatEvent,
    iccs: ICCS,
    context: bool,
    all: bool,
    use_seismogram_image: bool,
    return_fig: bool,
) -> tuple | None:
    """Update the time window for the given event.

    Args:
        session: Database session.
        event: AimbatEvent.
        iccs: ICCS instance.
        context: Whether to use seismograms with extra context.
        all: Whether to plot all seismograms.
        use_seismogram_image: Whether to use the seismogram image to update pick.
        return_fig: If True, return the figure and axes objects instead of showing the plot.

    Returns:
        A tuple of (Figure, Axes, widgets) if return_fig is True, otherwise None.
    """

    logger.info(f"Updating time window for event {event.id}.")

    result = _update_timewindow(  # type: ignore[call-overload]
        iccs, context, all, use_seismogram_image, return_fig=return_fig
    )

    if not return_fig:
        event.parameters.window_pre = iccs.window_pre
        event.parameters.window_post = iccs.window_post
        session.commit()
        return None

    logger.warning(_RETURN_FIG_WARNING)
    return result


def update_min_ccnorm(
    session: Session,
    event: AimbatEvent,
    iccs: ICCS,
    context: bool,
    all: bool,
    return_fig: bool,
) -> tuple | None:
    """Update the minimum cross correlation coefficient for the given event.

    Args:
        session: Database session.
        event: AimbatEvent.
        iccs: ICCS instance.
        context: Whether to use seismograms with extra context.
        all: Whether to plot all seismograms.
        return_fig: If True, return the figure and axes objects instead of showing the plot.

    Returns:
        A tuple of (Figure, Axes, widgets) if return_fig is True, otherwise None.
    """

    logger.info(f"Updating minimum cross correlation coefficient for event {event.id}.")

    result = _update_min_ccnorm(iccs, context, all, return_fig=return_fig)  # type: ignore[call-overload]

    if not return_fig:
        event.parameters.min_ccnorm = float(iccs.min_ccnorm)
        session.commit()
        return None

    logger.warning(_RETURN_FIG_WARNING)
    return result
