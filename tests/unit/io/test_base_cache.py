"""Unit tests for the bounded waveform cache in `aimbat.io._base`."""

import os
from collections import OrderedDict
from pathlib import Path
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
        lambda context: np.array([float(len(context.sourcename))]),
    )


def test_lru_evicts_least_recently_used(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_base, "_CACHE_MAX_ENTRIES", 2)

    calls: list[str] = []

    def recording_reader(context: _base.SeismogramReadContext) -> np.ndarray:
        calls.append(context.sourcename)
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


def test_reader_receives_read_context(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[_base.SeismogramReadContext] = []

    def capturing_reader(context: _base.SeismogramReadContext) -> np.ndarray:
        seen.append(context)
        return np.array([1.0])

    monkeypatch.setitem(_base._seismogram_data_readers, DataType.SAC, capturing_reader)

    _base.read_seismogram_data("x", DataType.SAC)
    session = _session()
    _base.read_seismogram_data("y", DataType.SAC, session=session)

    assert isinstance(seen[0], _base.SeismogramReadContext)
    assert (seen[0].sourcename, seen[0].datatype, seen[0].session) == (
        "x",
        DataType.SAC,
        None,
    )
    assert (seen[1].sourcename, seen[1].datatype, seen[1].session) == (
        "y",
        DataType.SAC,
        session,
    )


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


def _file_backed_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    """Register a reader that returns whatever numbers its source file holds."""
    monkeypatch.setitem(
        _base._seismogram_data_readers,
        DataType.SAC,
        lambda context: np.array(
            [float(x) for x in Path(context.sourcename).read_text().split(",")]
        ),
    )


def test_source_written_behind_our_back_is_re_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A write that never goes through `write_seismogram_data` still invalidates."""
    _file_backed_reader(monkeypatch)
    source = tmp_path / "waveform"
    source.write_text("1.0")

    assert _base.read_seismogram_data(source, DataType.SAC).tolist() == [1.0]

    source.write_text("1.0,2.0")

    assert _base.read_seismogram_data(source, DataType.SAC).tolist() == [1.0, 2.0]


def test_same_sized_rewrite_is_re_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Size alone would miss this one; the modification time catches it."""
    _file_backed_reader(monkeypatch)
    source = tmp_path / "waveform"
    source.write_text("1.0")

    assert _base.read_seismogram_data(source, DataType.SAC).tolist() == [1.0]

    stat = source.stat()
    source.write_text("2.0")
    # Set the time explicitly: two writes can land in one tick of a coarse
    # filesystem clock, which is the case this cache cannot detect.
    os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))

    assert _base.read_seismogram_data(source, DataType.SAC).tolist() == [2.0]


def test_unchanged_source_is_served_from_the_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reads: list[str] = []

    def counting_reader(context: _base.SeismogramReadContext) -> np.ndarray:
        reads.append(context.sourcename)
        return np.array([1.0])

    monkeypatch.setitem(_base._seismogram_data_readers, DataType.SAC, counting_reader)
    source = tmp_path / "waveform"
    source.write_text("1.0")

    first = _base.read_seismogram_data(source, DataType.SAC)
    second = _base.read_seismogram_data(source, DataType.SAC)

    assert first is second
    assert len(reads) == 1


def test_source_that_is_not_a_file_caches_as_before(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An identifier that no `stat()` can answer for keeps its cached array."""
    reads: list[str] = []

    def counting_reader(context: _base.SeismogramReadContext) -> np.ndarray:
        reads.append(context.sourcename)
        return np.array([1.0])

    monkeypatch.setitem(_base._seismogram_data_readers, DataType.SAC, counting_reader)

    first = _base.read_seismogram_data("not-a-path", DataType.SAC)
    second = _base.read_seismogram_data("not-a-path", DataType.SAC)

    assert first is second
    assert len(reads) == 1
