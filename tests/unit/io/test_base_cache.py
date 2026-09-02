"""Unit tests for the bounded waveform cache in `aimbat.io._base`."""

from collections import OrderedDict

import numpy as np
import pytest

from aimbat.io import _base
from aimbat.io._data import DataType


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give each test a fresh cache and a fake SAC reader."""
    monkeypatch.setattr(_base, "_cache", OrderedDict())
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
