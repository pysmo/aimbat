import aimbat.db
import pytest
import uuid
import shutil
import matplotlib.pyplot as plt
import random
import json
import os
import subprocess
from aimbat.app import app
from aimbat.aimbat_types import DataType
from aimbat.core import add_data_to_project, set_active_event, create_project
from aimbat.models import AimbatEvent
from aimbat.logger import configure_logging
from dataclasses import dataclass, field
from typing import Any, Literal
from pathlib import Path
from collections.abc import Callable, Generator, Sequence
from sqlmodel import Session, select, create_engine
from sqlalchemy import Engine, event

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_AIMBAT_LOGFILE = "aimbat_test.log"
_AIMBAT_LOG_LEVEL: Literal["DEBUG"] = "DEBUG"


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------


@dataclass
class TestData:
    """Container for test data paths.

    Attributes:
        multi_event: A list of paths to multi-event SAC files.
        sacfile_good: Path to a known good SAC file.
    """

    multi_event: list[Path] = field(
        default_factory=lambda: sorted(
            Path(__file__).parent.glob("assets/event_*/*.bhz")
        )
    )
    sacfile_good: Path = Path(__file__).parent / "assets/goodfile.sac"


TESTDATA = TestData()


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
    monkeypatch.setattr(aimbat.settings, "logfile", _AIMBAT_LOGFILE)
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
def sac_file_good(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Provides a path to a temporary copy of a known good SAC file.

    Args:
        tmp_path_factory: The pytest tmp_path_factory fixture.

    Returns:
        Path to the temporary SAC file.
    """
    orgfile = TESTDATA.sacfile_good
    tmpdir = tmp_path_factory.mktemp("aimbat")
    testfile = tmpdir / "good.sac"
    shutil.copy(orgfile, testfile)
    return testfile


@pytest.fixture
def multi_event_data(tmp_path_factory: pytest.TempPathFactory) -> list[Path]:
    """Provides a list of paths to temporary copies of multi-event SAC files.

    Args:
        tmp_path_factory: The pytest tmp_path_factory fixture.

    Returns:
        A list of paths to the temporary SAC files.
    """
    orgfiles = TESTDATA.multi_event
    tmpdir = tmp_path_factory.mktemp("aimbat")
    for orgfile in orgfiles:
        testfile = tmpdir / orgfile.name
        shutil.copy(orgfile, testfile)
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
    """A patched engine pre-populated with multi-event data and an active event.

    Args:
        patched_engine: The monkeypatched SQLAlchemy Engine.
        multi_event_data: Paths to temporary copies of multi-event SAC files.

    Returns:
        The monkeypatched SQLAlchemy Engine with data loaded.
    """

    datasources = multi_event_data
    with Session(patched_engine) as session:
        add_data_to_project(session, datasources, DataType.SAC)
        events = session.exec(select(AimbatEvent)).all()
        lengths = [len(e.seismograms) for e in events]
    set_active_event(session, events[lengths.index(max(lengths))])
    return patched_engine


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
    """A session pre-populated with multi-event data and an active event.

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
def cli() -> Callable[[str], None]:
    """Returns a callable that invokes ``app()`` in-process with command tokens.

    Returns:
        A callable that accepts a command string and runs it via the app.
    """

    def _run(command: str) -> None:
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
        env["AIMBAT_LOGFILE"] = _AIMBAT_LOGFILE
        env["AIMBAT_LOG_LEVEL"] = _AIMBAT_LOG_LEVEL
        env["COLUMNS"] = "1000"
        return subprocess.run(
            ["uv", "run", "aimbat", *args],
            capture_output=True,
            text=True,
            env=env,
        )

    return _run
