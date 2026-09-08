"""Public I/O interface for AIMBAT data sources.

Data source modules register their capabilities using the `register_*`
functions. Not all data sources need to support all capabilities. A source
providing waveform data only, for example, would register
`register_seismogram_data_reader` and `register_seismogram_data_writer` but
not the creator functions.

The SAC data source (`aimbat.io.sac`) registers its capabilities
automatically when imported.
"""

from __future__ import annotations

import os
import stat as stat_module
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING
from weakref import WeakKeyDictionary

import numpy as np
import numpy.typing as npt

from aimbat.logger import logger

from ._data import DataType

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from aimbat.models import (
        AimbatEvent,
        AimbatSeismogram,
        AimbatStation,
    )


__all__ = [
    "SeismogramReadContext",
    "SourceUnavailableError",
    "clear_seismogram_data_cache",
    "create_event",
    "create_seismogram",
    "create_station",
    "event_creator",
    "file_source_present",
    "read_seismogram_data",
    "register_event_creator",
    "register_seismogram_creator",
    "register_seismogram_data_reader",
    "register_seismogram_data_writer",
    "register_source_probe",
    "register_station_creator",
    "seismogram_creator",
    "seismogram_data_reader",
    "seismogram_data_writer",
    "source_present",
    "source_probe",
    "stage_seismogram_data",
    "station_creator",
    "supports_event_creation",
    "supports_seismogram_creation",
    "supports_seismogram_data_reading",
    "supports_seismogram_data_writing",
    "supports_source_probe",
    "supports_station_creation",
    "write_seismogram_data",
]


class SourceUnavailableError(Exception):
    """A probe could not determine whether a data source is present.

    Distinct from a clean "absent": raised when the answer is unknowable
    right now (an unreadable file, an unreachable mount). `aimbat data prune`
    treats this as a hard stop, never as a licence to delete.
    """


@dataclass(frozen=True, slots=True)
class SeismogramReadContext:
    """What a registered seismogram-data reader is handed for one read."""

    sourcename: str
    datatype: DataType
    session: Session | None = None


type SeismogramDataReader = Callable[[SeismogramReadContext], npt.NDArray[np.floating]]
"""A registered seismogram-data reader: given a read context, return the waveform data as a NumPy array."""

type SourcePresenceProbe = Callable[[SeismogramReadContext], bool]
"""A registered source-presence probe: given a read context, return whether the source still provides this seismogram.

Returns `True` when the source is reachable and provides the seismogram,
`False` when it is reachable and definitely does not. Raises
`SourceUnavailableError` when it cannot tell.
"""

# LRU cache of waveform arrays keyed by (datasource, datatype); evicting an
# entry only costs a re-read.
_CACHE_MAX_ENTRIES = 1024
_cache: OrderedDict[tuple[str, DataType], npt.NDArray[np.floating]] = OrderedDict()

# Per-session staged waveform writes, keyed weakly by the owning `Session`.
# `stage_seismogram_data` fills this; the listeners in `aimbat.io._flush`
# flush a session's pages to disk on its commit and drop them on rollback.
# Weak keys mean an abandoned session (never committed or rolled back) loses
# its staged pages when it is garbage-collected.
_pending: WeakKeyDictionary[
    Session, dict[tuple[str, DataType], npt.NDArray[np.floating]]
] = WeakKeyDictionary()

# Per-capability registries, populated by data source modules (e.g. _sac)
_station_creators: dict[DataType, Callable[[str | PathLike[str]], AimbatStation]] = {}
_event_creators: dict[DataType, Callable[[str | PathLike[str]], AimbatEvent]] = {}
_seismogram_creators: dict[
    DataType, Callable[[str | PathLike[str]], AimbatSeismogram]
] = {}
_seismogram_data_readers: dict[DataType, SeismogramDataReader] = {}
_seismogram_data_writers: dict[
    DataType, Callable[[str | PathLike[str], npt.NDArray[np.floating]], None]
] = {}
_source_probes: dict[DataType, SourcePresenceProbe] = {}


def register_station_creator(
    datatype: DataType,
    fn: Callable[[str | PathLike[str]], AimbatStation],
) -> None:
    """Register a function that creates an `AimbatStation` from a data source.

    Args:
        datatype: The data type this creator handles.
        fn: Callable that accepts a logical source identifier and returns an
            `AimbatStation` instance.
    """
    logger.debug(f"Registering station creator for {datatype}.")
    _station_creators[datatype] = fn


def register_event_creator(
    datatype: DataType,
    fn: Callable[[str | PathLike[str]], AimbatEvent],
) -> None:
    """Register a function that creates an `AimbatEvent` from a data source.

    Args:
        datatype: The data type this creator handles.
        fn: Callable that accepts a logical source identifier and returns an
            `AimbatEvent` instance.
    """
    logger.debug(f"Registering event creator for {datatype}.")
    _event_creators[datatype] = fn


def register_seismogram_creator(
    datatype: DataType,
    fn: Callable[[str | PathLike[str]], AimbatSeismogram],
) -> None:
    """Register a function that creates an `AimbatSeismogram` from a data source.

    Args:
        datatype: The data type this creator handles.
        fn: Callable that accepts a logical source identifier and returns an
            `AimbatSeismogram` instance.
    """
    logger.debug(f"Registering seismogram creator for {datatype}.")
    _seismogram_creators[datatype] = fn


def register_seismogram_data_reader(
    datatype: DataType,
    fn: SeismogramDataReader,
) -> None:
    """Register a function that reads seismogram waveform data from a data source.

    Args:
        datatype: The data type this reader handles.
        fn: Callable that accepts a `SeismogramReadContext` and returns the
            waveform data as a NumPy array.
    """
    logger.debug(f"Registering seismogram data reader for {datatype}.")
    _seismogram_data_readers[datatype] = fn


def register_seismogram_data_writer(
    datatype: DataType,
    fn: Callable[[str | PathLike[str], npt.NDArray[np.floating]], None],
) -> None:
    """Register a function that writes seismogram waveform data to a data source.

    Args:
        datatype: The data type this writer handles.
        fn: Callable that accepts a logical source identifier and a NumPy array,
            and writes the data to the source.
    """
    logger.debug(f"Registering seismogram data writer for {datatype}.")
    _seismogram_data_writers[datatype] = fn


def register_source_probe(
    datatype: DataType,
    fn: SourcePresenceProbe,
) -> None:
    """Register a function that checks whether a data source is still present.

    Args:
        datatype: The data type this probe handles.
        fn: Callable that accepts a `SeismogramReadContext` and returns whether
            the source still provides the seismogram, raising
            `SourceUnavailableError` when it cannot tell.
    """
    logger.debug(f"Registering source presence probe for {datatype}.")
    _source_probes[datatype] = fn


def station_creator(
    datatype: DataType,
) -> Callable[
    [Callable[[str | PathLike[str]], AimbatStation]],
    Callable[[str | PathLike[str]], AimbatStation],
]:
    """Decorator that registers a function as a station creator for `datatype`.

    Args:
        datatype: The data type the decorated function creates stations from.

    Example:
        ```python
        @station_creator(DataType.SAC)
        def create_station_from_sacfile(
            sacfile: str | PathLike[str],
        ) -> AimbatStation: ...
        ```
    """

    def decorator(
        fn: Callable[[str | PathLike[str]], AimbatStation],
    ) -> Callable[[str | PathLike[str]], AimbatStation]:
        register_station_creator(datatype, fn)
        return fn

    return decorator


def event_creator(
    datatype: DataType,
) -> Callable[
    [Callable[[str | PathLike[str]], AimbatEvent]],
    Callable[[str | PathLike[str]], AimbatEvent],
]:
    """Decorator that registers a function as an event creator for `datatype`.

    Args:
        datatype: The data type the decorated function creates events from.

    Example:
        ```python
        @event_creator(DataType.SAC)
        def create_event_from_sacfile(sacfile: str | PathLike[str]) -> AimbatEvent: ...
        ```
    """

    def decorator(
        fn: Callable[[str | PathLike[str]], AimbatEvent],
    ) -> Callable[[str | PathLike[str]], AimbatEvent]:
        register_event_creator(datatype, fn)
        return fn

    return decorator


def seismogram_creator(
    datatype: DataType,
) -> Callable[
    [Callable[[str | PathLike[str]], AimbatSeismogram]],
    Callable[[str | PathLike[str]], AimbatSeismogram],
]:
    """Decorator that registers a function as a seismogram creator for `datatype`.

    Args:
        datatype: The data type the decorated function creates seismograms from.

    Example:
        ```python
        @seismogram_creator(DataType.SAC)
        def create_seismogram_from_sacfile(
            sacfile: str | PathLike[str],
        ) -> AimbatSeismogram: ...
        ```
    """

    def decorator(
        fn: Callable[[str | PathLike[str]], AimbatSeismogram],
    ) -> Callable[[str | PathLike[str]], AimbatSeismogram]:
        register_seismogram_creator(datatype, fn)
        return fn

    return decorator


def seismogram_data_reader(
    datatype: DataType,
) -> Callable[[SeismogramDataReader], SeismogramDataReader]:
    """Decorator that registers a function as a seismogram data reader for `datatype`.

    Args:
        datatype: The data type the decorated function reads waveform data from.

    Example:
        ```python
        @seismogram_data_reader(DataType.SAC)
        def read_seismogram_data_from_sacfile(
            context: SeismogramReadContext,
        ) -> npt.NDArray[np.floating]: ...
        ```
    """

    def decorator(fn: SeismogramDataReader) -> SeismogramDataReader:
        register_seismogram_data_reader(datatype, fn)
        return fn

    return decorator


def seismogram_data_writer(
    datatype: DataType,
) -> Callable[
    [Callable[[str | PathLike[str], npt.NDArray[np.floating]], None]],
    Callable[[str | PathLike[str], npt.NDArray[np.floating]], None],
]:
    """Decorator that registers a function as a seismogram data writer for `datatype`.

    Args:
        datatype: The data type the decorated function writes waveform data to.

    Example:
        ```python
        @seismogram_data_writer(DataType.SAC)
        def write_seismogram_data_to_sacfile(
            sacfile: str | PathLike[str], data: npt.NDArray[np.floating]
        ) -> None: ...
        ```
    """

    def decorator(
        fn: Callable[[str | PathLike[str], npt.NDArray[np.floating]], None],
    ) -> Callable[[str | PathLike[str], npt.NDArray[np.floating]], None]:
        register_seismogram_data_writer(datatype, fn)
        return fn

    return decorator


def source_probe(
    datatype: DataType,
) -> Callable[[SourcePresenceProbe], SourcePresenceProbe]:
    """Decorator that registers a function as a source-presence probe for `datatype`.

    Args:
        datatype: The data type the decorated function probes.

    Example:
        ```python
        @source_probe(DataType.SAC)
        def sac_source_present(context: SeismogramReadContext) -> bool: ...
        ```
    """

    def decorator(fn: SourcePresenceProbe) -> SourcePresenceProbe:
        register_source_probe(datatype, fn)
        return fn

    return decorator


def supports_station_creation(datatype: DataType) -> bool:
    """Return whether `datatype` has a registered station creator."""
    return datatype in _station_creators


def supports_event_creation(datatype: DataType) -> bool:
    """Return whether `datatype` has a registered event creator."""
    return datatype in _event_creators


def supports_seismogram_creation(datatype: DataType) -> bool:
    """Return whether `datatype` has a registered seismogram creator."""
    return datatype in _seismogram_creators


def supports_seismogram_data_reading(datatype: DataType) -> bool:
    """Return whether `datatype` has a registered seismogram data reader."""
    return datatype in _seismogram_data_readers


def supports_seismogram_data_writing(datatype: DataType) -> bool:
    """Return whether `datatype` has a registered seismogram data writer."""
    return datatype in _seismogram_data_writers


def supports_source_probe(datatype: DataType) -> bool:
    """Return whether `datatype` has a registered source-presence probe."""
    return datatype in _source_probes


def source_present(
    sourcename: str, datatype: DataType, session: Session | None = None
) -> bool:
    """Check whether a data source is still present and provides its seismogram.

    Args:
        sourcename: Logical source identifier for the data source.
        datatype: Data type of the source.
        session: Session made available to the probe (needed by sources whose
            identity is resolved through the database).

    Returns:
        `True` if the source is reachable and provides the seismogram,
        `False` if it is reachable and definitely does not.

    Raises:
        NotImplementedError: If `datatype` has no registered probe.
        SourceUnavailableError: If the probe cannot determine presence right
            now (e.g. an unreadable file or an unreachable mount).
    """
    probe = _source_probes.get(datatype)
    if probe is None:
        raise NotImplementedError(f"{datatype} does not support source probing.")
    context = SeismogramReadContext(
        sourcename=str(sourcename), datatype=datatype, session=session
    )
    return probe(context)


def file_source_present(sourcename: str | PathLike[str]) -> bool:
    """Return whether a filesystem-backed data source is present.

    Shared implementation for the file-based probes (SAC, miniSEED, JSON). A
    reachable regular file is present; a reachable directory that simply does
    not contain the named entry is a clean `False`. Anything that leaves the
    answer unknowable right now - a missing or unreadable parent directory (a
    moved or unmounted tree), a permission error, an unreachable mount -
    raises `SourceUnavailableError` rather than being mistaken for a deletion.

    Args:
        sourcename: Path to the file backing the data source.

    Raises:
        SourceUnavailableError: If presence cannot be determined right now.
    """
    path = Path(sourcename)
    try:
        mode = os.stat(path).st_mode
    except FileNotFoundError as exc:
        # The file is gone. Only trust that as a real deletion if the parent
        # directory is still reachable; an unmounted volume whose mountpoint
        # lingers would otherwise look like a clean absence.
        if os.path.isdir(path.parent):
            return False
        raise SourceUnavailableError(
            f"Neither {os.fspath(path)!r} nor its parent directory could be "
            + "reached; this looks like a moved or unmounted data tree, not a "
            + "deletion."
        ) from exc
    except OSError as exc:
        raise SourceUnavailableError(
            f"Could not determine whether {os.fspath(path)!r} is present: {exc}"
        ) from exc
    return stat_module.S_ISREG(mode)


def create_station(
    datasource: str | PathLike[str], datatype: DataType
) -> AimbatStation:
    """Create an `AimbatStation` from a data source.

    Args:
        datasource: Logical source identifier for the data source.
        datatype: Data type of the source.

    Returns:
        A new `AimbatStation` instance.

    Raises:
        NotImplementedError: If `datatype` has no registered station creator.
    """
    logger.debug(f"Creating AimbatStation from {datasource}.")
    creator = _station_creators.get(datatype)
    if creator is None:
        raise NotImplementedError(f"{datatype} does not support station creation.")
    return creator(datasource)


def create_event(datasource: str | PathLike[str], datatype: DataType) -> AimbatEvent:
    """Create an `AimbatEvent` from a data source.

    Args:
        datasource: Logical source identifier for the data source.
        datatype: Data type of the source.

    Returns:
        A new `AimbatEvent` instance.

    Raises:
        NotImplementedError: If `datatype` has no registered event creator.
    """
    logger.debug(f"Creating AimbatEvent from {datasource}.")
    creator = _event_creators.get(datatype)
    if creator is None:
        raise NotImplementedError(f"{datatype} does not support event creation.")
    return creator(datasource)


def create_seismogram(
    datasource: str | PathLike[str], datatype: DataType
) -> AimbatSeismogram:
    """Create an `AimbatSeismogram` from a data source.

    Args:
        datasource: Logical source identifier for the data source.
        datatype: Data type of the source.

    Returns:
        A new `AimbatSeismogram` instance.

    Raises:
        NotImplementedError: If `datatype` has no registered seismogram creator.
    """
    logger.debug(f"Creating AimbatSeismogram from {datasource}.")
    creator = _seismogram_creators.get(datatype)
    if creator is None:
        raise NotImplementedError(f"{datatype} does not support seismogram creation.")
    return creator(datasource)


def read_seismogram_data(
    datasource: str | PathLike[str],
    datatype: DataType,
    session: Session | None = None,
) -> npt.NDArray[np.floating]:
    """Read seismogram waveform data from a data source.

    Results are cached in memory by `(datasource, datatype)` key. The returned
    array is read-only.

    If `session` is given and has a staged write for this key (from
    `stage_seismogram_data`), the staged value is returned instead of reading
    the data source, so a session sees its own uncommitted waveform write.

    Args:
        datasource: Logical source identifier for the data source.
        datatype: Data type of the source.
        session: Session whose staged writes should be consulted first.

    Returns:
        Read-only seismogram waveform data as a NumPy array.

    Raises:
        NotImplementedError: If `datatype` has no registered data reader.
    """
    logger.debug(f"Reading seismogram data from {datasource}.")
    key = (str(datasource), datatype)
    if session is not None:
        staged = _pending.get(session)
        if staged is not None and key in staged:
            logger.debug(f"Retrieved staged seismogram data for {datasource}.")
            return staged[key]
    reader = _seismogram_data_readers.get(datatype)
    if reader is None:
        raise NotImplementedError(
            f"{datatype} does not support reading seismogram data."
        )
    if key in _cache:
        logger.debug(f"Retrieved seismogram data from cache for {datasource}.")
        _cache.move_to_end(key)
    else:
        context = SeismogramReadContext(
            sourcename=key[0], datatype=datatype, session=session
        )
        arr = reader(context)
        arr.flags.writeable = False
        _cache[key] = arr
        if len(_cache) > _CACHE_MAX_ENTRIES:
            _cache.popitem(last=False)
    return _cache[key]


def write_seismogram_data(
    datasource: str | PathLike[str],
    datatype: DataType,
    data: npt.NDArray[np.floating],
) -> None:
    """Write seismogram waveform data to a data source.

    Writes eagerly and invalidates the cache entry for `(datasource,
    datatype)`. `AimbatSeismogram.data` assignment no longer calls this
    directly - it stages the write via `stage_seismogram_data` and the flush
    listener in `aimbat.io._flush` calls this on the owning session's commit.

    Args:
        datasource: Logical source identifier for the data source.
        datatype: Data type of the source.
        data: Seismogram waveform data to write.

    Raises:
        NotImplementedError: If `datatype` has no registered data writer.
    """
    logger.debug(f"Writing seismogram data to {datasource}.")
    writer = _seismogram_data_writers.get(datatype)
    if writer is None:
        raise NotImplementedError(
            f"{datatype} does not support writing seismogram data."
        )
    writer(datasource, data)
    _cache.pop((str(datasource), datatype), None)


def stage_seismogram_data(
    session: Session | None,
    datasource: str | PathLike[str],
    datatype: DataType,
    data: npt.NDArray[np.floating],
) -> None:
    """Stage a waveform write to flush when `session` commits.

    The write is validated immediately (a datatype with no registered writer
    raises straight away), but the data source is not touched until `session`
    commits. The staged value is discarded if `session` rolls back or is
    abandoned, and is visible to reads made through the same session before
    the commit.

    A copy of `data` is taken at call time, so later mutation of the caller's
    array does not change what is persisted. The `(datasource, datatype)` key
    is also captured now: renaming the data source on the model before the
    commit would flush to the old path. Staged pages are held in memory until
    the commit with no eviction (unlike the read cache), so staging waveform
    writes for a very large event holds every new array at once.

    Staging is keyed by `(datasource, datatype)`, not by seismogram: staging
    a second write for the same data source in one session before committing
    replaces the first, and only the last survives the flush.

    If `session` is `None` (a detached instance, attached to no session)
    there is no transaction to bind to, so the write falls back to an eager
    `write_seismogram_data` call.

    Args:
        session: The session that owns the seismogram, or `None`.
        datasource: Logical source identifier for the data source.
        datatype: Data type of the source.
        data: Seismogram waveform data to write.

    Raises:
        NotImplementedError: If `datatype` has no registered data writer.
    """
    if datatype not in _seismogram_data_writers:
        raise NotImplementedError(
            f"{datatype} does not support writing seismogram data."
        )
    if session is None:
        msg = f"Waveform write for detached seismogram {datasource}: "
        logger.warning(msg + "no session to bind to, writing eagerly.")
        write_seismogram_data(datasource, datatype, data)
        return
    logger.debug(f"Staging seismogram data write to {datasource}.")
    staged = np.array(data, copy=True)
    staged.flags.writeable = False
    session_pending = _pending.setdefault(session, {})
    key = (str(datasource), datatype)
    if key in session_pending:
        logger.warning(
            f"Replacing an earlier staged waveform write for {datasource}; "
            + "only the latest is flushed on commit."
        )
    session_pending[key] = staged


def clear_seismogram_data_cache() -> None:
    """Drop every entry from the in-memory waveform read cache.

    Staged (uncommitted) writes in `_pending` are left intact.
    """
    _cache.clear()
