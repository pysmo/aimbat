"""ICCS background-worker lifecycle for the AIMBAT TUI.

`_IccsLifecycleMixin` is the Textual-specific adapter around `IccsLifecycle`
(`aimbat.core._iccs`): it owns the actual I/O and threading (reading
waveform data in a background worker, marshalling results back to the main
thread via `call_from_thread`) and calls into the shared, framework-agnostic
`IccsLifecycle` object only to record outcomes and ask policy questions
("is this stale", "should I retry", "is an instance ready"). A future non-TUI
frontend (e.g. a Qt GUI) would reuse `IccsLifecycle` behind its own adapter
using its own threading/notification primitives.

Mixed into `AimbatTUI`, which provides `_current_event_id`,
`_current_phase`, `_get_current_event`, `_get_current_phase` and
`refresh_all` (declared below
only for the type checker; the real implementations live on the host class).
"""

import uuid

from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, col, select
from textual import work
from textual.app import App

from aimbat.actions import prepare_iccs
from aimbat.core import (
    AmbiguousPhaseError,
    BoundICCS,
    IccsLifecycle,
    NoSeismogramsError,
    NotReadyError,
    resolve_phase,
)
from aimbat.core._validity import compute_digests
from aimbat.db import engine
from aimbat.logger import logger
from aimbat.models import AimbatEvent, AimbatPhase, phase_label

type PhaseKey = tuple[str, str]
"""Name and component of a phase, the same across events."""


def phase_keys(session: Session, event_id: uuid.UUID) -> list[PhaseKey]:
    """Names and components of the phases of an event, without loading their rows."""
    return [
        (name, component)
        for name, component in session.exec(
            select(AimbatPhase.name, AimbatPhase.component)
            .where(AimbatPhase.event_id == event_id)
            .order_by(col(AimbatPhase.name), col(AimbatPhase.component))
        ).all()
    ]


def resolve_key(
    session: Session, event_id: uuid.UUID, key: PhaseKey | None
) -> AimbatPhase:
    """The phase of an event with that name and component, or its only phase.

    Raises:
        NoResultFound: If the event does not exist or has no such phase.
        AmbiguousPhaseError: If `key` is `None` and the event has several
            phases.
    """
    if key is None:
        return resolve_phase(session, event_id)
    return resolve_phase(session, event_id, *key)


def carry_key(carried: PhaseKey | None, keys: list[PhaseKey]) -> PhaseKey | None:
    """The phase to keep on another event with the phases `keys`.

    The same name and component, else the only phase of that name, else none.
    """
    if carried is None or carried in keys:
        return carried
    same_name = [key for key in keys if key[0] == carried[0]]
    return same_name[0] if len(same_name) == 1 else None


def several_phases_notice(error: AmbiguousPhaseError) -> str:
    """The notice shown when processing is refused because no phase is selected."""
    return f"This event has phases {', '.join(error.labels)}. Press p to select one."


class _IccsLifecycleMixin(App[None]):
    """ICCS instance lifecycle: creation, staleness detection, readiness checks."""

    _iccs_lifecycle: IccsLifecycle

    # Tracked digest observed at the last staleness check, used to repaint
    # panels (without rebuilding ICCS) after a non-stack parameter change
    # (MCCC parameters or `min_cc`) made in another process.
    _ui_tracked_seen: str | None

    # Set when `_create_iccs` is called while a build is in flight, so the
    # request is replayed when that build ends without an instance.
    _creation_requested: bool

    # Provided by AimbatTUI; declared here only so the type checker accepts
    # the calls below - the host class's own definitions take precedence.
    _current_event_id: uuid.UUID | None
    _current_phase: PhaseKey | None

    def _get_current_event(self, session: Session) -> AimbatEvent:
        raise NotImplementedError

    def _get_current_phase(self, session: Session) -> AimbatPhase:
        raise NotImplementedError

    def refresh_all(self) -> None:
        raise NotImplementedError

    def _init_iccs_lifecycle(self) -> None:
        """Reset ICCS lifecycle state and start the periodic staleness check."""
        self._iccs_lifecycle = IccsLifecycle()
        self._ui_tracked_seen = None
        self._creation_requested = False
        self.set_interval(5, self._check_iccs_staleness)

    def _create_iccs(self, *, is_retry: bool = False) -> None:
        """Discard the existing ICCS instance and create a new one in a background worker.

        ICCS construction reads waveform data, so it must not block the asyncio event loop.
        Concurrent calls are ignored: only one worker runs at a time. Also records the
        current event's instance digest via `IccsLifecycle.note_checked` (and its
        tracked digest for the UI-repaint check), so that a later staleness poll
        correctly falls through to the one-shot retry branch instead of treating the
        still-in-progress attempt as newly detected staleness.

        Args:
            is_retry: Whether this call is the one-shot retry made in
                response to `IccsLifecycle.retry_pending` after a previous
                failure. A retry call is not itself allowed to re-arm the
                retry flag, so a persistently failing event gets exactly one
                automatic retry rather than retrying forever.
        """
        if self._iccs_lifecycle.aligning:
            logger.debug("Alignment running; not replacing its ICCS instance.")
            return
        if not self._iccs_lifecycle.start_creating():
            logger.debug(
                "ICCS creation already in progress; replaying the request after it."
            )
            self._creation_requested = True
            return
        self._creation_requested = False
        try:
            with Session(engine) as session:
                phase_id = self._get_current_phase(session).id
        except (NoResultFound, AmbiguousPhaseError, RuntimeError):
            logger.debug("No phase to build ICCS for; skipping creation.")
            self._iccs_lifecycle.mark_aborted()
            return
        except Exception as exc:
            logger.exception(f"Resolving the phase for ICCS failed: {exc}")
            self._iccs_lifecycle.mark_aborted()
            return
        try:
            with Session(engine) as session:
                digests = compute_digests(session, phase_id)[phase_id]
                self._iccs_lifecycle.note_checked(digests.instance)
                self._ui_tracked_seen = digests.tracked
        except Exception:
            # Best-effort bookkeeping only: any failure here (a locked DB,
            # ...) must not prevent the worker below from running, since it
            # alone resets `start_creating()`'s guard.
            pass
        self._worker_create_iccs(phase_id, is_retry)

    @work(thread=True)
    def _worker_create_iccs(self, phase_id: uuid.UUID, is_retry: bool = False) -> None:
        """Create the ICCS instance for a phase without blocking the UI.

        On success, hands the new `BoundICCS` instance to `_assign_iccs` on
        the main thread. On failure, notifies the user and, unless this call
        is itself a retry, arms a one-shot retry for one further automatic
        attempt.

        Args:
            phase_id: ID of the phase, resolved on the main thread by
                `_create_iccs`.
            is_retry: Whether this call is the one-shot retry after a
                previous failure.
        """
        try:
            bound_iccs = prepare_iccs(phase_id)
        except (NoResultFound, NoSeismogramsError, RuntimeError):
            logger.debug(
                "ICCS worker: phase gone, phase has no seismograms, or no data; "
                + "aborting."
            )
            self.call_from_thread(self._end_creation_without_instance, None)
            return
        except NotReadyError as exc:
            self.call_from_thread(self.notify, str(exc), severity="warning")
            self.call_from_thread(self._end_creation_without_instance, is_retry)
            return
        except Exception as exc:
            logger.exception(f"ICCS worker: unexpected error during creation: {exc}")
            self.call_from_thread(
                self.notify, f"ICCS init failed: {exc}", severity="error"
            )
            # Give the staleness poller one retry attempt on the next tick.
            self.call_from_thread(self._end_creation_without_instance, is_retry)
            return
        logger.debug("ICCS worker: instance created successfully.")
        self.call_from_thread(self._assign_iccs, bound_iccs)

    def _end_creation_without_instance(self, failed_retry: bool | None) -> None:
        """Record a build that produced no instance, then replay a dropped request.

        Args:
            failed_retry: `None` if the build was aborted (nothing to build
                for), else whether the failed build was itself the one-shot
                retry.
        """
        if failed_retry is None:
            self._iccs_lifecycle.mark_aborted()
        else:
            self._iccs_lifecycle.mark_failed(is_retry=failed_retry)
        if self._creation_requested:
            self._creation_requested = False
            self._create_iccs()

    def _assign_iccs(self, bound_iccs: BoundICCS) -> None:
        """Store the newly created ICCS instance and refresh all panels.

        Discards the instance instead if the current phase changed while
        the worker was building it (the event was deleted, or another event
        or phase was selected, before this call ran); otherwise a slow,
        stale worker could bind an instance for a phase that is no longer
        current. When a phase is still current, immediately starts a fresh
        attempt for it.

        Args:
            bound_iccs: The instance created by `_worker_create_iccs`.
        """
        current_phase_id: uuid.UUID | None
        try:
            with Session(engine) as session:
                current_phase_id = self._get_current_phase(session).id
        except (NoResultFound, AmbiguousPhaseError):
            current_phase_id = None
        if bound_iccs.phase_id != current_phase_id:
            logger.debug(
                "ICCS worker: discarding instance for a phase that is no longer "
                + "current."
            )
            self._iccs_lifecycle.mark_aborted()
            self._creation_requested = False
            if current_phase_id is not None:
                self._create_iccs()
            self.refresh_all()
            return
        self._iccs_lifecycle.assign(bound_iccs)
        if self._creation_requested:
            # Requested during the build, after a change the instance may
            # predate (parameters, membership, a rollback).
            self._creation_requested = False
            self._create_iccs()
            self.refresh_all()
            return
        logger.info("ICCS instance ready and assigned.")
        # Rebuilding ICCS re-upserts iccs_cc per seismogram, which also feeds
        # ProjectPanel's quality panel and station cc_mean/cc_sem column.
        self.refresh_all()

    def _check_iccs_staleness(self) -> bool:
        """React to an external change to the current event.

        A change to a parameter the instance is built from (the instance
        digest) rebuilds the ICCS instance; any other parameter change (the
        tracked digest, e.g. an MCCC-only tweak made via the CLI) only
        repaints the panels so they reflect the new DB state. When ICCS
        creation previously failed (e.g. an invalid parameter set via the
        CLI), retries once, then waits for a further change before retrying
        again. This avoids retrying forever against a persistently failing
        event. Does nothing while an alignment runs, since the run's own
        commits change the digests.

        Returns:
            Whether the panels were refreshed.
        """
        if self._current_event_id is None or self._iccs_lifecycle.aligning:
            return False
        try:
            with Session(engine) as session:
                phase_id = self._get_current_phase(session).id
                digests = compute_digests(session, phase_id)[phase_id]
                stale = self._iccs_lifecycle.is_stale(phase_id, digests.instance)
        except NoResultFound:
            return self._drop_missing_phase()
        except (AmbiguousPhaseError, RuntimeError):
            return False
        ui_changed = digests.tracked != self._ui_tracked_seen
        self._ui_tracked_seen = digests.tracked
        if stale:
            logger.debug(
                "ICCS staleness detected; recreating instance and refreshing UI."
            )
            self._create_iccs()
        elif self._iccs_lifecycle.retry_pending:
            logger.debug("Retrying ICCS creation after a previous failure.")
            self._create_iccs(is_retry=True)
        elif ui_changed:
            logger.debug("Event modified without a stack change; refreshing UI only.")
        else:
            return False
        self.refresh_all()
        return True

    def _drop_missing_phase(self) -> bool:
        """Clear a selected phase that the active event no longer has.

        A phase can be renamed or removed from another process. The event's
        only phase, if it has just one, is then used again.

        Returns:
            Whether the selection was cleared.
        """
        event_id, key = self._current_event_id, self._current_phase
        if event_id is None or key is None:
            return False
        with Session(engine) as session:
            if session.get(AimbatEvent, event_id) is None:
                return False
            if key in phase_keys(session, event_id):
                return False
        self._current_phase = None
        self.notify(
            f"The event has no phase {phase_label(*key)} any more. The phase "
            + "selection is cleared.",
            severity="warning",
        )
        self._create_iccs()
        self.refresh_all()
        return True

    def _require_iccs(self) -> bool:
        """Check that the ICCS instance is ready, showing a contextual warning otherwise.

        Returns:
            Whether the ICCS instance is ready to use.
        """
        if self._iccs_lifecycle.ready:
            return True
        if self._current_event_id is not None:
            try:
                with Session(engine) as session:
                    self._get_current_phase(session)
            except AmbiguousPhaseError as exc:
                self.notify(several_phases_notice(exc), severity="warning")
                return False
            except NoResultFound:
                if self._drop_missing_phase():
                    return False
                # No phase at all: the generic notice below applies.
            self.notify(
                "ICCS not ready: check phase parameters (press P)",
                severity="warning",
            )
        else:
            self.notify(
                "No event selected: select one on the Project tab",
                severity="warning",
            )
        return False
