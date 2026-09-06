"""Unit tests for the bounded waveform cache in `aimbat.io._base`."""

from collections import OrderedDict
from weakref import WeakKeyDictionary

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlmodel import Session

from aimbat.io import _base
from aimbat.io._data import DataType


def _session() -> Session:
    """A throwaway Session; these tests never touch the database through it."""
    return Session(create_engine("sqlite://"))


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give each test a fresh cache, staging buffer, and a fake SAC reader."""
    monkeypatch.setattr(_base, "_cache", OrderedDict())
    monkeypatch.setattr(_base, "_pending", WeakKeyDictionary())
    monkeypatch.setitem(
        _base._seismogram_data_readers,
        DataType.SAC,
        lambda src: np.array([float(len(str(src)))]),
    )


def test_lru_evicts_least_recently_used(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_base, "_CACHE_MAX_ENTRIES", 2)

    calls: list[str] = []

    def recording_reader(src: object) -> np.ndarray:
        calls.append(str(src))
        return np.array([1.0])

    monkeypatch.setitem(_base._seismogram_data_readers, DataType.SAC, recording_reader)

    _base.read_seismogram_data("a", DataType.SAC)
    _base.read_seismogram_data("b", DataType.SAC)
    _base.read_seismogram_data("a", DataType.SAC)  # hit -> 'a' most recent, 'b' oldest
    _base.read_seismogram_data("c", DataType.SAC)  # over cap -> evict 'b'

    assert {k[0] for k in _base._cache} == {"a", "c"}

    _base.read_seismogram_data("b", DataType.SAC)  # evicted -> re-read
    assert calls == ["a", "b", "c", "b"]


def test_hit_returns_cached_array_without_re_reading() -> None:
    first = _base.read_seismogram_data("x", DataType.SAC)
    second = _base.read_seismogram_data("x", DataType.SAC)
    assert first is second


def test_clear_seismogram_data_cache_empties_it() -> None:
    _base.read_seismogram_data("x", DataType.SAC)
    assert _base._cache
    _base.clear_seismogram_data_cache()
    assert not _base._cache


def test_staged_value_shadows_lru_for_that_session_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        _base._seismogram_data_writers, DataType.SAC, lambda src, data: None
    )
    session = _session()
    other = _session()

    on_disk = _base.read_seismogram_data("x", DataType.SAC)  # populates the LRU
    _base.stage_seismogram_data(session, "x", DataType.SAC, np.array([42.0]))

    staged = _base.read_seismogram_data("x", DataType.SAC, session=session)
    assert staged.tolist() == [42.0]
    assert not staged.flags.writeable

    # A different session, and the no-session path, still see the LRU value.
    assert _base.read_seismogram_data("x", DataType.SAC, session=other) is on_disk
    assert _base.read_seismogram_data("x", DataType.SAC) is on_disk


def test_stage_copies_the_caller_array(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        _base._seismogram_data_writers, DataType.SAC, lambda src, data: None
    )
    session = _session()
    caller = np.array([1.0, 2.0])
    _base.stage_seismogram_data(session, "x", DataType.SAC, caller)
    caller[0] = 99.0

    staged = _base.read_seismogram_data("x", DataType.SAC, session=session)
    assert staged.tolist() == [1.0, 2.0]


def test_stage_without_writer_raises() -> None:
    with pytest.raises(NotImplementedError):
        _base.stage_seismogram_data(
            _session(), "x", DataType.JSON_EVENT, np.array([1.0])
        )


def test_stage_without_session_writes_eagerly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    written: list[tuple[object, object]] = []
    monkeypatch.setitem(
        _base._seismogram_data_writers,
        DataType.SAC,
        lambda src, data: written.append((src, data)),
    )
    _base.stage_seismogram_data(None, "x", DataType.SAC, np.array([7.0]))
    assert written and written[0][0] == "x"


def test_clear_cache_keeps_staged_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        _base._seismogram_data_writers, DataType.SAC, lambda src, data: None
    )
    session = _session()
    _base.stage_seismogram_data(session, "x", DataType.SAC, np.array([5.0]))
    _base.clear_seismogram_data_cache()
    assert _base.read_seismogram_data("x", DataType.SAC, session=session).tolist() == [
        5.0
    ]
