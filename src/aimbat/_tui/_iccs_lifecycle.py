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
`_get_current_event`, and `refresh_all` (declared below only for the type
checker; the real implementations live on the host class).
"""

from __future__ import annotations

import uuid

from sqlalchemy.exc import NoResultFound
from sqlmodel import Session
from textual import work
from textual.app import App

from aimbat.core import BoundICCS, IccsLifecycle, create_iccs_instance
from aimbat.db import engine
from aimbat.logger import logger
from aimbat.models import AimbatEvent


class _IccsLifecycleMixin(App[None]):
    """ICCS instance lifecycle: creation, staleness detection, readiness checks."""

    _iccs_lifecycle: IccsLifecycle

    # Provided by AimbatTUI; declared here only so the type checker accepts
    # the calls below - the host class's own definitions take precedence.
    _current_event_id: uuid.UUID | None

    def _get_current_event(self, session: Session) -> AimbatEvent:
        raise NotImplementedError

    def refresh_all(self) -> None:
        raise NotImplementedError

    def _init_iccs_lifecycle(self) -> None:
        """Reset ICCS lifecycle state and start the periodic staleness check."""
        self._iccs_lifecycle = IccsLifecycle()
        self.set_interval(5, self._check_iccs_staleness)

    def _create_iccs(self, *, is_retry: bool = False) -> None:
        """Discard the existing ICCS instance and create a new one in a background worker.

        ICCS construction reads waveform data, so it must not block the asyncio event loop.
        Concurrent calls are ignored — only one worker runs at a time.

        Args:
            is_retry: Whether this call is the one-shot retry made in
                response to `IccsLifecycle.retry_pending` after a previous
                failure. A retry call is not itself allowed to re-arm the
                retry flag, so a persistently failing event gets exactly one
                automatic retry rather than retrying forever.
        """
        if not self._iccs_lifecycle.start_creating():
            logger.debug(
                "ICCS creation already in progress; skipping duplicate request."
            )
            return
        self._worker_create_iccs(is_retry)

    @work(thread=True)
    def _worker_create_iccs(self, is_retry: bool = False) -> None:
        """Create the ICCS instance for the current event without blocking the UI.

        On success, hands the new `BoundICCS` instance to `_assign_iccs` on
        the main thread. On failure, notifies the user and, unless this call
        is itself a retry, arms a one-shot retry for one further automatic
        attempt.

        Args:
            is_retry: Whether this call is the one-shot retry after a
                previous failure.
        """
        try:
            with Session(engine) as session:
                event = self._get_current_event(session)
                bound_iccs = create_iccs_instance(session, event)
        except (NoResultFound, RuntimeError):
            logger.debug("ICCS worker: no event selected or no data; aborting.")
            self.call_from_thread(self._iccs_lifecycle.mark_aborted)
            return
        except Exception as exc:
            logger.exception(f"ICCS worker: unexpected error during creation: {exc}")
            self.call_from_thread(
                self.notify, f"ICCS init failed: {exc}", severity="error"
            )
            # Give the staleness poller one retry attempt on the next tick.
            self.call_from_thread(self._iccs_lifecycle.mark_failed, is_retry=is_retry)
            return
        logger.debug("ICCS worker: instance created successfully.")
        self.call_from_thread(self._assign_iccs, bound_iccs)

    def _assign_iccs(self, bound_iccs: BoundICCS) -> None:
        """Store the newly created ICCS instance and refresh all panels.

        Discards the instance instead if the selected event changed while
        the worker was building it (e.g. the event was deleted, or a
        different event was selected, before this call ran) — otherwise a
        slow, stale worker could bind an instance for an event that is no
        longer current. When an event is still selected, immediately starts
        a fresh attempt for it.

        Args:
            bound_iccs: The instance created by `_worker_create_iccs`.
        """
        if bound_iccs.event_id != self._current_event_id:
            logger.debug(
                "ICCS worker: discarding instance for an event that is no "
                "longer selected."
            )
            self._iccs_lifecycle.mark_aborted()
            if self._current_event_id is not None:
                self._create_iccs()
            return
        self._iccs_lifecycle.assign(bound_iccs)
        logger.info("ICCS instance ready and assigned.")
        # Rebuilding ICCS re-upserts iccs_cc per seismogram, which also feeds
        # ProjectPanel's quality panel and station cc_mean/cc_sem column.
        self.refresh_all()

    def _check_iccs_staleness(self) -> None:
        """Trigger ICCS recreation if the current event has been modified externally.

        When ICCS creation previously failed (e.g. due to an invalid parameter set via
        the CLI), retries once, then waits for `event.last_modified` to change again
        before retrying further — this avoids retrying forever against a persistently
        failing event. On any detected change the full UI is refreshed so panels
        reflect the new DB state immediately.
        """
        if self._current_event_id is None:
            return
        try:
            with Session(engine) as session:
                event = self._get_current_event(session)
                stale = self._iccs_lifecycle.is_stale(event)
        except (NoResultFound, RuntimeError):
            return
        if stale:
            logger.debug(
                "ICCS staleness detected; recreating instance and refreshing UI."
            )
            self._iccs_lifecycle.note_checked(event.last_modified)
            self._create_iccs()
            self.refresh_all()
        elif self._iccs_lifecycle.retry_pending:
            logger.debug("Retrying ICCS creation after a previous failure.")
            self._create_iccs(is_retry=True)
            self.refresh_all()

    def _require_iccs(self) -> bool:
        """Check that the ICCS instance is ready, showing a contextual warning otherwise.

        Returns:
            Whether the ICCS instance is ready to use.
        """
        if self._iccs_lifecycle.ready:
            return True
        if self._current_event_id is not None:
            self.notify(
                "ICCS not ready — check event parameters (Parameters tab)",
                severity="warning",
            )
        else:
            self.notify(
                "No event selected — select one on the Project tab",
                severity="warning",
            )
        return False
