from aimbat.aimbat_types import DataType
from pysmo.classes import SAC
from sqlmodel import Session, select
from sqlalchemy import Engine
from pathlib import Path
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from importlib import reload
from aimbat import settings
from aimbat._config import Settings
from aimbat.logger import configure_logging
import aimbat.db as db
import aimbat.core._project as project
import aimbat.core._data as data
import aimbat.core._event as event
import random
import shutil
import pytest
import matplotlib.pyplot as plt
import uuid


@dataclass
class TestData:
    multi_event: list[Path] = field(
        default_factory=lambda: sorted(
            Path(__file__).parent.glob("assets/event_*/*.bhz")
        )
    )
    sacfile_good = Path(__file__).parent / "assets/goodfile.sac"


TESTDATA = TestData()


# https://rednafi.com/python/patch-pydantic-settings-in-pytest/
@pytest.fixture
def patch_settings(request: pytest.FixtureRequest) -> Iterator[Settings]:
    # Make a copy of the original settings
    original_settings = settings.model_copy()

    # Collect the env vars to patch
    env_vars_to_patch = getattr(request, "param", {})

    # Patch the settings to use the default values
    for k, v in Settings.model_fields.items():
        setattr(settings, k, v.default)

    # Patch the settings with the parametrized env vars
    for key, val in env_vars_to_patch.items():
        # Raise an error if the env var is not defined in the settings
        if not hasattr(settings, key):
            raise ValueError(f"Unknown setting: {key}")

        # Raise an error if the env var has an invalid type
        expected_type = getattr(settings, key).__class__
        if not isinstance(val, expected_type):
            raise ValueError(
                f"Invalid type for {key}: {val.__class__} instead of {{expected_type}}"
            )
        setattr(settings, key, val)

    yield settings

    # Restore the original settings
    settings.__dict__.update(original_settings.__dict__)


@pytest.fixture(autouse=True)
def patch_debug_setting(patch_settings: Settings) -> Iterator[None]:
    patch_settings.log_level = "DEBUG"
    patch_settings.logfile = Path("aimbat_test.log")
    configure_logging()

    yield


@pytest.fixture(autouse=True)
def mock_uuid4(monkeypatch: pytest.MonkeyPatch) -> None:
    def make_generator() -> Callable[[], uuid.UUID]:
        rand = random.Random(42)
        return lambda: uuid.UUID(int=rand.getrandbits(128), version=4)

    monkeypatch.setattr(uuid, "uuid4", make_generator())


@pytest.fixture(autouse=True)
def mock_show(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plt, "show", lambda: None)


@pytest.fixture(autouse=True)
def increase_columns(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("COLUMNS", "1000")
    yield


@pytest.fixture(scope="session")
def test_data_dir(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[Path]:
    tmp_dir = Path(tmp_path_factory.mktemp("test_data"))

    yield tmp_dir

    shutil.rmtree(tmp_dir)


@pytest.fixture(scope="session")
def test_data(test_data_dir: Path) -> Iterator[list[Path]]:
    data_list: list[Path] = []
    for orgfile in TESTDATA.multi_event:
        testfile = test_data_dir / f"{uuid.uuid4()}.sac"
        shutil.copy(orgfile, testfile)
        data_list.append(testfile)
    yield data_list


@pytest.fixture(scope="session")
def test_data_string(test_data: list[Path]) -> Iterator[list[str]]:
    yield [str(data) for data in test_data]


@pytest.fixture
def fixture_empty_db(
    patch_settings: Settings,
) -> Iterator[tuple[Engine, Session]]:
    db_url: str = r"sqlite+pysqlite:///:memory:"
    patch_settings.db_url = db_url
    db.engine.dispose()
    reload(db)

    with Session(db.engine) as session:
        yield db.engine, session
    db.engine.dispose()


@pytest.fixture
def fixture_session_with_project_file(
    tmp_path_factory: pytest.TempPathFactory,
    patch_settings: Settings,
) -> Iterator[tuple[Engine, Session, Path]]:
    db_file = Path(tmp_path_factory.mktemp("test_db")) / "mock.db"
    db_url: str = rf"sqlite+pysqlite:///{db_file}"

    patch_settings.db_url = db_url
    patch_settings.project = db_file

    db.engine.dispose()
    reload(db)
    project.create_project(db.engine)

    with Session(db.engine) as session:
        yield db.engine, session, db_file
    db.engine.dispose()


@pytest.fixture
def fixture_engine_session_with_project(
    patch_settings: Settings,
) -> Iterator[tuple[Engine, Session]]:
    """Yield a session with a new project."""

    db_url: str = r"sqlite+pysqlite:///:memory:"
    patch_settings.db_url = db_url

    db.engine.dispose()
    reload(db)
    project.create_project(db.engine)

    with Session(db.engine) as session:
        yield db.engine, session
    db.engine.dispose()


@pytest.fixture
def fixture_session_with_data(
    test_data: list[Path], patch_settings: Settings
) -> Iterator[Session]:
    """Yield a session with a test data added."""

    db_url: str = r"sqlite+pysqlite:///:memory:"
    patch_settings.db_url = db_url

    db.engine.dispose()
    reload(db)
    project.create_project(db.engine)

    with Session(db.engine) as session:
        data.add_files_to_project(session, test_data, DataType.SAC)
        yield session
    db.engine.dispose()


@pytest.fixture
def fixture_engine_session_with_active_event(
    patch_settings: Settings, test_data: list[Path]
) -> Iterator[tuple[Engine, Session]]:
    """Yield a session with an active event."""

    db_url: str = r"sqlite+pysqlite:///:memory:"
    patch_settings.db_url = db_url

    db.engine.dispose()
    reload(db)
    project.create_project(db.engine)

    with Session(db.engine) as session:
        data.add_files_to_project(session, test_data, DataType.SAC)
        events = session.exec(select(event.AimbatEvent)).all()
        lengths = [len(e.seismograms) for e in events]
        event.set_active_event(session, events[lengths.index(max(lengths))])
        yield db.engine, session
    db.engine.dispose()


@pytest.fixture()
def sac_file_good(tmp_path_factory: pytest.TempPathFactory) -> Path:
    orgfile = TESTDATA.sacfile_good
    tmpdir = tmp_path_factory.mktemp("aimbat")
    testfile = tmpdir / "good.sac"
    shutil.copy(orgfile, testfile)
    return testfile


@pytest.fixture()
def sac_instance_good(sac_file_good: Path) -> Iterator[SAC]:
    my_sac = SAC.from_file(sac_file_good)
    try:
        yield my_sac
    finally:
        del my_sac
