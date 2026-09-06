"""Unit tests for the session-scoped flush listeners in `aimbat.io._flush`.

These call the listener functions directly with hand-built transaction
objects. The event-surface behaviour they stand in for (`before_commit` /
`after_soft_rollback` firing, and `nested` on a real SAVEPOINT rollback) is
covered end to end in `tests/integration/io/test_datasource_sac.py`.
"""

from collections import OrderedDict
from types import SimpleNamespace
from weakref import WeakKeyDictionary

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlmodel import Session

from aimbat.io import _base, _flush
from aimbat.io._data import DataType


def _session() -> Session:
    """A throwaway Session; the listeners here never touch the database."""
    return Session(create_engine("sqlite://"))


def _txn(*, nested: bool) -> SimpleNamespace:
    """Stand-in for the `SessionTransaction` passed to `after_soft_rollback`."""
    return SimpleNamespace(nested=nested)


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, list[float]]]:
    """Fresh cache/staging buffers and a recording SAC writer."""
    monkeypatch.setattr(_base, "_cache", OrderedDict())
    monkeypatch.setattr(_base, "_pending", WeakKeyDictionary())
    written: list[tuple[str, list[float]]] = []
    monkeypatch.setitem(
        _base._seismogram_data_writers,
        DataType.SAC,
        lambda src, data: written.append((str(src), list(data))),
    )
    return written


def test_flush_writes_only_the_committing_session(
    isolated_state: list[tuple[str, list[float]]],
) -> None:
    written = isolated_state
    a, b = _session(), _session()
    _base.stage_seismogram_data(a, "file_a", DataType.SAC, np.array([1.0]))
    _base.stage_seismogram_data(b, "file_b", DataType.SAC, np.array([2.0]))

    _flush._flush_pending(b)

    assert written == [("file_b", [2.0])]
    assert b not in _base._pending
    assert a in _base._pending  # session A's stage is untouched


def test_flush_invalidates_the_read_cache(
    isolated_state: list[tuple[str, list[float]]],
) -> None:
    session = _session()
    _base._cache[("file_a", DataType.SAC)] = np.array([0.0])
    _base.stage_seismogram_data(session, "file_a", DataType.SAC, np.array([9.0]))

    _flush._flush_pending(session)

    assert ("file_a", DataType.SAC) not in _base._cache


def test_full_rollback_discards_without_writing(
    isolated_state: list[tuple[str, list[float]]],
) -> None:
    written = isolated_state
    session = _session()
    _base.stage_seismogram_data(session, "file_a", DataType.SAC, np.array([1.0]))

    _flush._discard_pending(session, _txn(nested=False))

    assert session not in _base._pending
    assert written == []


def test_savepoint_rollback_keeps_the_stage(
    isolated_state: list[tuple[str, list[float]]],
) -> None:
    session = _session()
    _base.stage_seismogram_data(session, "file_a", DataType.SAC, np.array([1.0]))

    _flush._discard_pending(session, _txn(nested=True))

    assert session in _base._pending


def test_listeners_ignore_unknown_sessions(
    isolated_state: list[tuple[str, list[float]]],
) -> None:
    _flush._flush_pending(_session())
    _flush._discard_pending(_session(), _txn(nested=False))
    _flush._discard_pending(_session(), None)
    assert isolated_state == []


def test_second_stage_for_the_same_source_replaces_the_first(
    isolated_state: list[tuple[str, list[float]]],
) -> None:
    written = isolated_state
    session = _session()
    _base.stage_seismogram_data(session, "file_a", DataType.SAC, np.array([1.0]))
    _base.stage_seismogram_data(session, "file_a", DataType.SAC, np.array([2.0]))

    _flush._flush_pending(session)

    assert written == [("file_a", [2.0])]


def test_failed_flush_leaves_every_page_staged_for_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session()
    _base.stage_seismogram_data(session, "ok", DataType.SAC, np.array([1.0]))
    _base.stage_seismogram_data(session, "boom", DataType.SAC, np.array([2.0]))

    fail = {"on": True}

    def flaky_writer(src: object, data: object) -> None:
        if fail["on"] and str(src) == "boom":
            raise OSError("disk full")

    monkeypatch.setitem(_base._seismogram_data_writers, DataType.SAC, flaky_writer)

    with pytest.raises(OSError, match="disk full"):
        _flush._flush_pending(session)

    # Nothing cleared: a retry commit rewrites "ok" and retries "boom".
    assert set(_base._pending[session]) == {
        ("ok", DataType.SAC),
        ("boom", DataType.SAC),
    }

    fail["on"] = False
    _flush._flush_pending(session)
    assert session not in _base._pending
