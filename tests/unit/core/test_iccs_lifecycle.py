"""Unit tests for `aimbat.core._iccs.IccsLifecycle`.

Pure state-machine tests: `IccsLifecycle` owns no I/O or threading, so these
run without a database session or SQLModel persistence, unlike most of
`tests/integration/core/`.
"""

import uuid
from typing import cast

from pandas import Timedelta, Timestamp

from pysmo.tools.iccs import ICCS

from aimbat.core._iccs import BoundICCS, IccsLifecycle
from aimbat.models import AimbatEvent


def _make_event(
    *, event_id: uuid.UUID | None = None, stack_modified: Timestamp | None = None
) -> AimbatEvent:
    """Build a detached AimbatEvent with just the fields IccsLifecycle reads."""
    return AimbatEvent(
        id=event_id or uuid.uuid4(),
        time=Timestamp("2020-01-01T00:00:00", tz="UTC"),
        latitude=0.0,
        longitude=0.0,
        stack_modified=stack_modified,
    )


def _make_bound(event_id: uuid.UUID, created_at: Timestamp) -> BoundICCS:
    """Build a BoundICCS with a dummy ICCS payload — is_stale never touches it."""
    return BoundICCS(
        iccs=cast(ICCS, object()), event_id=event_id, created_at=created_at
    )


class TestReady:
    """Tests for IccsLifecycle.ready."""

    def test_not_ready_initially(self) -> None:
        """A fresh lifecycle has no bound instance."""
        assert IccsLifecycle().ready is False

    def test_ready_once_assigned(self) -> None:
        """Ready becomes True once an instance is assigned."""
        lifecycle = IccsLifecycle()
        lifecycle.assign(_make_bound(uuid.uuid4(), Timestamp.now("UTC")))
        assert lifecycle.ready is True


class TestIsStale:
    """Tests for IccsLifecycle.is_stale."""

    def test_no_bound_instance_falls_back_to_stack_modified_seen(self) -> None:
        """With no bound instance, staleness compares against note_checked's value."""
        lifecycle = IccsLifecycle()
        event = _make_event(stack_modified=Timestamp("2020-01-01T00:00:00", tz="UTC"))

        # Nothing recorded yet -> considered stale.
        assert lifecycle.is_stale(event) is True

        lifecycle.note_checked(event.stack_modified)
        assert lifecycle.is_stale(event) is False

        event.stack_modified = Timestamp("2020-01-02T00:00:00", tz="UTC")
        assert lifecycle.is_stale(event) is True

    def test_bound_instance_delegates_to_bound_is_stale(self) -> None:
        """With a bound instance, staleness delegates to BoundICCS.is_stale."""
        event_id = uuid.uuid4()
        created_at = Timestamp("2020-01-01T00:00:00", tz="UTC")
        lifecycle = IccsLifecycle(bound=_make_bound(event_id, created_at))

        fresh_event = _make_event(event_id=event_id, stack_modified=None)
        assert lifecycle.is_stale(fresh_event) is False

        modified_event = _make_event(
            event_id=event_id, stack_modified=created_at + Timedelta(seconds=1)
        )
        assert lifecycle.is_stale(modified_event) is True

        other_event = _make_event(event_id=uuid.uuid4())
        assert lifecycle.is_stale(other_event) is True


class TestStartCreating:
    """Tests for IccsLifecycle.start_creating."""

    def test_returns_true_and_resets_state(self) -> None:
        """Starting a fresh attempt discards any bound instance and pending retry."""
        lifecycle = IccsLifecycle(bound=_make_bound(uuid.uuid4(), Timestamp.now("UTC")))
        lifecycle.retry_pending = True

        assert lifecycle.start_creating() is True
        assert lifecycle.bound is None
        assert lifecycle.retry_pending is False

    def test_returns_false_while_already_creating(self) -> None:
        """A second concurrent attempt is rejected while one is in progress."""
        lifecycle = IccsLifecycle()
        assert lifecycle.start_creating() is True
        assert lifecycle.start_creating() is False


class TestMarkAborted:
    """Tests for IccsLifecycle.mark_aborted."""

    def test_clears_creating_without_arming_retry(self) -> None:
        """Aborting (e.g. no event selected) does not schedule a retry."""
        lifecycle = IccsLifecycle()
        lifecycle.start_creating()

        lifecycle.mark_aborted()

        assert lifecycle.retry_pending is False
        assert lifecycle.start_creating() is True


class TestMarkFailed:
    """Tests for IccsLifecycle.mark_failed."""

    def test_fresh_failure_arms_one_shot_retry(self) -> None:
        """A failure that wasn't itself a retry arms exactly one retry."""
        lifecycle = IccsLifecycle()
        lifecycle.start_creating()

        lifecycle.mark_failed(is_retry=False)

        assert lifecycle.retry_pending is True

    def test_retry_failure_does_not_rearm(self) -> None:
        """A failed retry attempt does not schedule another retry."""
        lifecycle = IccsLifecycle()
        lifecycle.start_creating()

        lifecycle.mark_failed(is_retry=True)

        assert lifecycle.retry_pending is False

    def test_clears_creating_guard(self) -> None:
        """A failed attempt allows a new attempt to start."""
        lifecycle = IccsLifecycle()
        lifecycle.start_creating()

        lifecycle.mark_failed(is_retry=False)

        assert lifecycle.start_creating() is True


class TestAssign:
    """Tests for IccsLifecycle.assign."""

    def test_stores_bound_and_clears_creating(self) -> None:
        """A successful creation stores the instance and clears the in-progress guard."""
        lifecycle = IccsLifecycle()
        lifecycle.start_creating()
        bound = _make_bound(uuid.uuid4(), Timestamp.now("UTC"))

        lifecycle.assign(bound)

        assert lifecycle.bound is bound
        assert lifecycle.ready is True
        assert lifecycle.start_creating() is True


class TestClear:
    """Tests for IccsLifecycle.clear."""

    def test_discards_bound_without_arming_retry(self) -> None:
        """Clearing (e.g. the bound event was deleted) does not schedule a retry."""
        lifecycle = IccsLifecycle(bound=_make_bound(uuid.uuid4(), Timestamp.now("UTC")))

        lifecycle.clear()

        assert lifecycle.bound is None
        assert lifecycle.retry_pending is False


class TestNoteChecked:
    """Tests for IccsLifecycle.note_checked."""

    def test_updates_stack_modified_seen(self) -> None:
        """The observed timestamp is recorded verbatim."""
        lifecycle = IccsLifecycle()
        ts = Timestamp("2020-01-01T00:00:00", tz="UTC")

        lifecycle.note_checked(ts)

        assert lifecycle.stack_modified_seen == ts
