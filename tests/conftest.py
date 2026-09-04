import json
import os
import random
import shutil
import subprocess
import uuid
from collections.abc import Callable, Generator, Sequence
from pathlib import Path
from typing import Any, Literal

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pytest
from pandas import Timedelta
from sqlalchemy import Engine, event
from sqlmodel import Session, create_engine

from pysmo.classes import SAC

import aimbat.db
from aimbat.app import app
from aimbat.core import add_data_to_project, create_project
from aimbat.io import DataType
from aimbat.logger import configure_logging

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_AIMBAT_LOG_LEVEL: Literal["DEBUG"] = "DEBUG"


def _worker_logfile() -> str:
    """Log file name for the current test session, unique per xdist worker.

    Under ``pytest-xdist`` every worker runs in its own process but shares the
    working directory, so a fixed name would have all workers appending to one
    file. ``PYTEST_XDIST_WORKER`` is unset on a non-parallel run (``"master"``).
    """
    worker = os.environ.get("PYTEST_XDIST_WORKER", "master")
    return f"aimbat_test_{worker}.log"


# ---------------------------------------------------------------------------
# Autouse mocks
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def patch_debug_setting(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Automatically patches settings to enable debug logging for tests.

    Args:
        monkeypatch: The pytest monkeypatch fixture.

    Yields:
        None
    """
    monkeypatch.setattr(aimbat.settings, "logfile", _worker_logfile())
    monkeypatch.setattr(aimbat.settings, "log_level", _AIMBAT_LOG_LEVEL)
    configure_logging()

    yield


@pytest.fixture(autouse=True)
def mock_uuid4(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mocks uuid.uuid4 to produce deterministic UUIDs.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
    """

    def make_generator() -> Callable[[], uuid.UUID]:
        rand = random.Random(42)
        return lambda: uuid.UUID(int=rand.getrandbits(128), version=4)

    monkeypatch.setattr(uuid, "uuid4", make_generator())


@pytest.fixture(autouse=True)
def mock_show(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mocks plt.show to prevent plots from displaying during tests.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
    """
    monkeypatch.setattr(plt, "show", lambda: None)


@pytest.fixture(autouse=True)
def increase_columns(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Increases the COLUMNS environment variable for wider output in tests.

    Args:
        monkeypatch: The pytest monkeypatch fixture.

    Yields:
        None
    """
    monkeypatch.setenv("COLUMNS", "1000")
    yield


# ---------------------------------------------------------------------------
# File fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """Path for the temporary project database file (does not exist yet).

    Args:
        tmp_path: The pytest tmp_path fixture.

    Returns:
        Path to the temporary project database file.
    """
    return tmp_path / "test_project.db"


@pytest.fixture()
def sac_file_good(
    reference_event_assets: dict[str, Path],
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    """Provides a path to a temporary copy of a known good SAC file.

    testkit's reference event file has no pick headers set, but aimbat tests
    rely on t0/t1 being populated (e.g. to test pick-header selection), so
    they are written onto the copy rather than onto the shared testkit asset.

    Args:
        reference_event_assets: testkit fixture with paths to the reference event's files.
        tmp_path_factory: The pytest tmp_path_factory fixture.

    Returns:
        Path to the temporary SAC file.
    """
    orgfile = reference_event_assets["sac_bhz"]
    tmpdir = tmp_path_factory.mktemp("aimbat")
    testfile = tmpdir / "good.sac"
    shutil.copy(orgfile, testfile)

    sac = SAC.from_file(testfile)
    sac.timestamps.t0 = sac.seismogram.begin_time + Timedelta(seconds=30)
    sac.timestamps.t1 = sac.seismogram.begin_time + Timedelta(seconds=30.2)
    sac.write(testfile)

    return testfile


@pytest.fixture
def multi_event_data(
    iccs_events_assets: dict[str, dict[str, Path]],
    tmp_path_factory: pytest.TempPathFactory,
) -> list[Path]:
    """Provides a list of paths to temporary copies of multi-event SAC files.

    Flattens testkit's per-event station files into a single directory, keyed
    only by filename. Several stations recur across events (it's the same
    Alaska array recording different teleseisms), so files from a later event
    overwrite an earlier event's file of the same name — deliberately, since
    this is what produces multiple distinct events sharing overlapping
    station coverage in the ingested set.

    Args:
        iccs_events_assets: testkit fixture with paths to the ICCS array's SAC files.
        tmp_path_factory: The pytest tmp_path_factory fixture.

    Returns:
        A list of paths to the temporary SAC files.
    """
    tmpdir = tmp_path_factory.mktemp("aimbat")
    for event_label in sorted(iccs_events_assets):
        for orgfile in sorted(iccs_events_assets[event_label].values()):
            shutil.copy(orgfile, tmpdir / orgfile.name)
    return sorted(tmpdir.glob("*.bhz", case_sensitive=False))


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


@pytest.fixture
def engine_from_file(
    db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[Engine, None, None]:
    """Creates an empty project database backed by a file.

    Args:
        db_path: Path to the temporary project database file.
        monkeypatch: The pytest monkeypatch fixture.

    Yields:
        A SQLAlchemy Engine connected to the file database.
    """
    db_url: str = rf"sqlite+pysqlite:///{db_path}"
    engine: Engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    monkeypatch.setattr(aimbat.db, "engine", engine)

    yield engine
    engine.dispose()


@pytest.fixture
def engine() -> Generator[Engine, None, None]:
    """Creates an in memory database with a new project.

    Yields:
        A SQLAlchemy Engine connected to the in-memory database with project.
    """
    engine: Engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    create_project(engine)

    yield engine
    engine.dispose()


@pytest.fixture
def patched_engine(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> Generator[Engine, None, None]:
    """Monkeypatches ``aimbat.db.engine`` so CLI functions use the test database.

    Args:
        engine: The SQLAlchemy Engine for the test database.
        monkeypatch: The pytest monkeypatch fixture.

    Yields:
        The monkeypatched SQLAlchemy Engine.
    """
    monkeypatch.setattr(aimbat.db, "engine", engine)
    yield engine


@pytest.fixture()
def loaded_engine(patched_engine: Engine, multi_event_data: Sequence[Path]) -> Engine:
    """A patched engine pre-populated with multi-event data and an default event.

    Args:
        patched_engine: The monkeypatched SQLAlchemy Engine.
        multi_event_data: Paths to temporary copies of multi-event SAC files.

    Returns:
        The monkeypatched SQLAlchemy Engine with data loaded.
    """

    datasources = multi_event_data
    with Session(patched_engine) as session:
        add_data_to_project(session, datasources, DataType.SAC)
    return patched_engine


@pytest.fixture()
def loaded_engine_from_file(
    engine_from_file: Engine, multi_event_data: Sequence[Path]
) -> Engine:
    """A file-backed engine pre-populated with multi-event data.

    Use instead of `loaded_engine` when a test exercises code that opens its own
    `Session(engine)` from a background thread (e.g. Textual's `@work(thread=True)`
    workers). SQLAlchemy's default pool for `sqlite:///:memory:` hands each thread
    an independent, empty database, so `loaded_engine` cannot be used there; a real
    file is shared correctly across threads.

    Args:
        engine_from_file: The monkeypatched, file-backed SQLAlchemy Engine.
        multi_event_data: Paths to temporary copies of multi-event SAC files.

    Returns:
        The monkeypatched SQLAlchemy Engine with a project and data loaded.
    """
    create_project(engine_from_file)
    with Session(engine_from_file) as session:
        add_data_to_project(session, multi_event_data, DataType.SAC)
    return engine_from_file


@pytest.fixture()
def patched_session(patched_engine: Engine) -> Generator[Session, None, None]:
    """A session bound to the patched engine for CLI tests.

    Args:
        patched_engine: The monkeypatched SQLAlchemy Engine.

    Yields:
        A SQLModel Session bound to the patched engine.
    """
    with Session(patched_engine) as session:
        yield session


@pytest.fixture()
def loaded_session(loaded_engine: Engine) -> Generator[Session, None, None]:
    """A session pre-populated with multi-event data and an default event.

    Args:
        loaded_engine: The monkeypatched SQLAlchemy Engine with data loaded.

    Yields:
        A SQLModel Session with data populated.
    """
    with Session(loaded_engine) as session:
        yield session


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@pytest.fixture()
def cli() -> Callable[[str | list[str]], None]:
    """Returns a callable that invokes ``app()`` in-process with command tokens.

    Accepts either a command string (split via ``shlex``) or a pre-tokenised
    list of strings.  Pass a list when tokens contain platform-specific path
    separators (e.g. Windows backslashes) that ``shlex`` would otherwise mangle.

    Returns:
        A callable that accepts a command string or token list and runs it via the app.
    """

    def _run(command: str | list[str]) -> None:
        try:
            app(command)
        except SystemExit as exc:
            if exc.code != 0:
                raise

    return _run


@pytest.fixture()
def cli_json(capsys: pytest.CaptureFixture[str]) -> Callable[[str], list | dict]:
    """Returns a callable that runs a ``dump`` sub-command and returns parsed JSON.

    Args:
        capsys: The pytest capsys fixture.

    Returns:
        A callable that accepts a command string and returns the parsed JSON output.
    """

    def _run(command: str) -> list | dict:
        capsys.readouterr()  # discard output from prior commands
        try:
            app(command)
        except SystemExit as exc:
            if exc.code != 0:
                raise
        captured = capsys.readouterr()
        return json.loads(captured.out)

    return _run


@pytest.fixture()
def event_id(loaded_engine: Engine, cli_json: Callable[[str], list | dict]) -> str:
    """Returns the ID of the first event from the loaded engine.

    Args:
        loaded_engine: The monkeypatched SQLAlchemy Engine with data loaded.
        cli_json: The CLI JSON callable to query event dump.

    Returns:
        The ID string of the first event.
    """
    events = cli_json("event dump")
    return events[0]["id"]


@pytest.fixture()
def aimbat_subprocess(
    db_path: Path,
) -> Callable[[Sequence[str]], subprocess.CompletedProcess[str]]:
    """Returns a callable that runs ``aimbat <args>`` as a subprocess against the test database.

    Args:
        db_path: Path to the temporary project database file.

    Returns:
        A callable that accepts a sequence of CLI arguments and returns the completed process.
    """

    def _run(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["AIMBAT_DB_URL"] = f"sqlite+pysqlite:///{db_path}"
        env["AIMBAT_LOGFILE"] = _worker_logfile()
        env["AIMBAT_LOG_LEVEL"] = _AIMBAT_LOG_LEVEL
        env["COLUMNS"] = "1000"
        return subprocess.run(
            ["uv", "run", "aimbat", *args],
            capture_output=True,
            text=True,
            env=env,
        )

    return _run
