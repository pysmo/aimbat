"""Session-scoped flushing of staged waveform writes.

Assigning `AimbatSeismogram.data` stages the array in the per-session buffer
in `aimbat.io._base` instead of writing it to the data source. The listeners
here write a session's staged pages to their data sources just before it
commits, and discard them when it rolls back. They are registered on the
`Session` class, so they fire for every session in the process, but both are
no-ops for a session that never staged a write: they only ever touch
`_pending[session]` for the committing or rolling-back session, and one unit
of work never flushes another's staged writes. Registering on the class
(rather than a `sessionmaker` owned by `aimbat.db`) is deliberate - any
session bound to the project database gets the deferred-write behaviour,
including one opened by a downstream consumer, so `seis.data = ...` can never
be silently dropped for want of the "right" session factory.

Flushing happens in `before_commit`. The listener first calls
`session.flush()` so that any ORM-level failure in the pending unit of work
(a constraint violation, a failed validator, an `IntegrityError` on an
unrelated row) is raised before a single byte is written to a data source.
Only then are the staged pages written. A failed data-source write (disk
full, permissions) aborts `session.commit()` from a recoverable state: the
staged pages stay in `_pending`, so calling `session.commit()` again retries
them, and `session.rollback()` discards them.

The residual inconsistency window is narrow but real: a data-source write
succeeds and then the database `COMMIT` itself fails (or the process crashes
between the two). The file is left updated with the database unchanged, and
there is no journal to replay. This is strictly smaller than the pre-deferral
eager write, which mutated the file at assignment time - long before the
commit - but it is not eliminated. `session.rollback()` after such a failure
drops the staged pages; the already-written file is not reverted.

`_discard_pending` is on `after_soft_rollback`, which fires for every
rollback and receives the transaction that ended. `after_rollback` is
deliberately not used: it also fires for a SAVEPOINT
(`session.begin_nested()`) rollback, which must not drop pages staged on the
enclosing transaction. `after_soft_rollback` reports `nested=True` for a
SAVEPOINT rollback (ignored) and `nested=False` for a full rollback (pages
dropped). An abandoned session - never committed or rolled back - drops its
pages when it is garbage-collected (weak keys in `_pending`).

Thread-safety: the TUI commits on its main thread while a background thread
builds ICCS and reads staged values through the getter. Each thread uses its
own `Session` (sessions are not thread-safe), so no two threads stage or
flush the same `_pending` key, and every staged array is copied on stage and
read-only on read. Reads of another thread's staged pages are best-effort.
Concurrent staging from multiple threads is not supported and would need its
own synchronisation.
"""

from sqlalchemy import event
from sqlalchemy.orm import Session, SessionTransaction

from aimbat.logger import logger

from . import _base


@event.listens_for(Session, "before_commit")
def _flush_pending(session: Session) -> None:
    """Write `session`'s staged waveform pages to their data sources.

    Flushes the ORM unit of work first, so a constraint or validation
    failure aborts the commit before any data source is touched. A
    subsequent data-source write failure also aborts the commit and leaves
    every staged page in place for a retry (pages already written are simply
    rewritten with the same bytes).
    """
    staged = _base._pending.get(session)
    if not staged:
        return
    # Surface ORM-level failures before writing any file: after this returns
    # cleanly, only the raw COMMIT can still fail.
    session.flush()
    for (sourcename, datatype), data in staged.items():
        logger.debug(f"Flushing staged seismogram data to {sourcename}.")
        _base.write_seismogram_data(sourcename, datatype, data)
    _base._pending.pop(session, None)


@event.listens_for(Session, "after_soft_rollback")
def _discard_pending(
    session: Session, previous_transaction: SessionTransaction | None
) -> None:
    """Drop `session`'s staged pages on a full rollback, keep them on SAVEPOINT."""
    if previous_transaction is not None and previous_transaction.nested:
        return
    _base._pending.pop(session, None)
