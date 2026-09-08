"""Unit tests for the source-presence probe capability in aimbat.io._base."""

from pathlib import Path

import pytest

from aimbat.io import (
    DataType,
    SeismogramReadContext,
    SourceUnavailableError,
    file_source_present,
    register_source_probe,
    source_present,
    supports_source_probe,
)
from aimbat.io._base import _source_probes


def test_file_probes_registered() -> None:
    """Every file-based data type ships a probe."""
    for datatype in (
        DataType.SAC,
        DataType.MSEED,
        DataType.JSON_EVENT,
        DataType.JSON_STATION,
    ):
        assert supports_source_probe(datatype)


def test_source_present_true_for_existing_file(tmp_path: Path) -> None:
    """A present SAC file probes `True`."""
    sacfile = tmp_path / "present.sac"
    sacfile.write_bytes(b"")
    assert source_present(str(sacfile), DataType.SAC) is True


def test_source_present_false_for_missing_file(tmp_path: Path) -> None:
    """A missing SAC file probes `False`."""
    assert source_present(str(tmp_path / "gone.sac"), DataType.SAC) is False


def test_missing_file_with_present_parent_is_clean_absent(tmp_path: Path) -> None:
    """A gone file whose directory is still reachable probes `False`."""
    assert file_source_present(tmp_path / "gone.sac") is False


def test_missing_parent_directory_raises(tmp_path: Path) -> None:
    """A gone file whose parent directory is also gone is unknowable."""
    with pytest.raises(SourceUnavailableError, match="parent directory"):
        file_source_present(tmp_path / "no_such_dir" / "x.sac")


def test_unreadable_parent_directory_raises(tmp_path: Path) -> None:
    """A file under a directory we cannot search is unknowable, not absent."""
    locked = tmp_path / "locked"
    locked.mkdir()
    (locked / "x.sac").write_bytes(b"")
    locked.chmod(0o000)
    try:
        result: object = file_source_present(locked / "x.sac")
    except SourceUnavailableError:
        return
    finally:
        locked.chmod(0o755)
    if result is True:
        pytest.skip("running as a user that bypasses directory permissions")
    pytest.fail(f"expected SourceUnavailableError, got {result!r}")


def test_source_present_unknown_datatype_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A data type with no registered probe raises `NotImplementedError`."""
    monkeypatch.delitem(_source_probes, DataType.SAC)
    assert not supports_source_probe(DataType.SAC)
    with pytest.raises(NotImplementedError):
        source_present("whatever", DataType.SAC)


def test_probe_raising_source_unavailable_propagates() -> None:
    """`SourceUnavailableError` from a probe is not swallowed."""
    sentinel = DataType.SAC
    original = _source_probes[sentinel]

    def _boom(_context: SeismogramReadContext) -> bool:
        raise SourceUnavailableError("mount unreachable")

    register_source_probe(sentinel, _boom)
    try:
        with pytest.raises(SourceUnavailableError, match="mount unreachable"):
            source_present("x", sentinel)
    finally:
        register_source_probe(sentinel, original)
