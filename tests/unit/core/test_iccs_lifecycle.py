"""Unit tests for `aimbat.core._iccs.IccsLifecycle`.

Pure state-machine tests: `IccsLifecycle` owns no I/O or threading, so these
run without a database session or SQLModel persistence, unlike most of
`tests/integration/core/`.
"""

import uuid
from typing import cast

from pysmo.tools.iccs import ICCS

from aimbat.core._iccs import BoundICCS, IccsLifecycle


def _make_bound(phase_id: uuid.UUID, instance_digest: str | None = "a") -> BoundICCS:
    """Build a BoundICCS with a dummy ICCS payload — is_stale never touches it."""
    return BoundICCS(
        iccs=cast(ICCS, object()), phase_id=phase_id, instance_digest=instance_digest
    )


class TestReady:
    """Tests for IccsLifecycle.ready."""

    def test_not_ready_initially(self) -> None:
        """A fresh lifecycle has no bound instance."""
        assert IccsLifecycle().ready is False

    def test_ready_once_assigned(self) -> None:
        """Ready becomes True once an instance is assigned."""
        lifecycle = IccsLifecycle()
        lifecycle.assign(_make_bound(uuid.uuid4()))
        assert lifecycle.ready is True


class TestIsStale:
    """Tests for IccsLifecycle.is_stale."""

    def test_no_bound_instance_falls_back_to_the_digest_seen(self) -> None:
        """With no bound instance, staleness compares against note_checked's value."""
        lifecycle = IccsLifecycle()
        phase_id = uuid.uuid4()

        # Nothing recorded yet -> considered stale.
        assert lifecycle.is_stale(phase_id, "a") is True

        lifecycle.note_checked("a")
        assert lifecycle.is_stale(phase_id, "a") is False
        assert lifecycle.is_stale(phase_id, "b") is True

    def test_bound_instance_delegates_to_bound_is_stale(self) -> None:
        """With a bound instance, staleness delegates to BoundICCS.is_stale."""
        phase_id = uuid.uuid4()
        lifecycle = IccsLifecycle(bound=_make_bound(phase_id, "a"))

        assert lifecycle.is_stale(phase_id, "a") is False
        assert lifecycle.is_stale(phase_id, "b") is True
        assert lifecycle.is_stale(uuid.uuid4(), "a") is True


class TestBoundIccsIsStale:
    """Tests for BoundICCS.is_stale."""

    def test_same_digest_is_fresh(self) -> None:
        phase_id = uuid.uuid4()
        assert _make_bound(phase_id, "a").is_stale(phase_id, "a") is False

    def test_other_digest_is_stale(self) -> None:
        phase_id = uuid.uuid4()
        assert _make_bound(phase_id, "a").is_stale(phase_id, "b") is True

    def test_other_event_is_stale(self) -> None:
        assert _make_bound(uuid.uuid4(), "a").is_stale(uuid.uuid4(), "a") is True

    def test_instance_from_a_snapshot_is_always_stale(self) -> None:
        """An instance built from a snapshot does not reflect the live parameters."""
        phase_id = uuid.uuid4()
        assert _make_bound(phase_id, None).is_stale(phase_id, "a") is True


class TestStartCreating:
    """Tests for IccsLifecycle.start_creating."""

    def test_returns_true_and_resets_state(self) -> None:
        """Starting a fresh attempt discards any bound instance and pending retry."""
        lifecycle = IccsLifecycle(bound=_make_bound(uuid.uuid4()))
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
        bound = _make_bound(uuid.uuid4())

        lifecycle.assign(bound)

        assert lifecycle.bound is bound
        assert lifecycle.ready is True
        assert lifecycle.start_creating() is True


class TestClear:
    """Tests for IccsLifecycle.clear."""

    def test_discards_bound_without_arming_retry(self) -> None:
        """Clearing (e.g. the bound event was deleted) does not schedule a retry."""
        lifecycle = IccsLifecycle(bound=_make_bound(uuid.uuid4()))

        lifecycle.clear()

        assert lifecycle.bound is None
        assert lifecycle.retry_pending is False


class TestNoteChecked:
    """Tests for IccsLifecycle.note_checked."""

    def test_records_the_digest(self) -> None:
        lifecycle = IccsLifecycle()

        lifecycle.note_checked("a")

        assert lifecycle.instance_digest_seen == "a"
