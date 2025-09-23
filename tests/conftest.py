from aimbat.lib.typing import SeismogramFileType
from pysmo.classes import SAC
from sqlmodel import Session, select
from pathlib import Path
from collections.abc import Generator, Callable
from typing import Any
from dataclasses import dataclass, field
from importlib import reload
import aimbat.lib.db as db
import aimbat.lib.defaults as defaults
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
def increase_columns(monkeypatch: pytest.MonkeyPatch) -> Generator[None, Any, Any]:
    monkeypatch.setenv("COLUMNS", "1000")
    yield


@pytest.fixture(scope="session")
def test_data_dir(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[Path, Any, Any]:
    tmp_dir = Path(tmp_path_factory.mktemp("test_data"))

    yield tmp_dir

    shutil.rmtree(tmp_dir)


@pytest.fixture(scope="session")
def test_data(test_data_dir: Path) -> Generator[list[Path], Any, Any]:
    data_list: list[Path] = []
    for orgfile in TESTDATA.multi_event:
        testfile = test_data_dir / f"{uuid.uuid4()}.sac"
        shutil.copy(orgfile, testfile)
        data_list.append(testfile)
    yield data_list


@pytest.fixture(scope="session")
def test_data_string(test_data: list[Path]) -> Generator[list[str], Any, Any]:
    yield [str(data) for data in test_data]


@pytest.fixture
def test_db(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[Path, Session], Any, Any]:
    db_file = Path(tmp_path_factory.mktemp("test_db")) / "mock.db"
    db_url: str = rf"sqlite+pysqlite:///{db_file}"
    monkeypatch.setenv("AIMBAT_PROJECT", str(db_file))
    monkeypatch.setenv("AIMBAT_DB_URL", str(db_url))
    reload(defaults)
    reload(db)

    with Session(db.engine) as session:
        yield db_file, session
    db.engine.dispose()


@pytest.fixture
def test_db_with_project(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[Path, Session], Any, Any]:
    db_file = Path(tmp_path_factory.mktemp("test_db")) / "mock.db"
    db_url: str = rf"sqlite+pysqlite:///{db_file}"
    monkeypatch.setenv("AIMBAT_PROJECT", str(db_file))
    monkeypatch.setenv("AIMBAT_DB_URL", str(db_url))
    import aimbat.lib.project as project

    reload(defaults)
    reload(db)
    reload(project)
    project.create_project()

    with Session(db.engine) as session:
        yield db_file, session
    db.engine.dispose()


@pytest.fixture
def test_db_with_data(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
    test_data: list[Path],
) -> Generator[tuple[Path, Session], Any, Any]:
    db_file = Path(tmp_path_factory.mktemp("test_db")) / "mock.db"
    db_url: str = rf"sqlite+pysqlite:///{db_file}"
    monkeypatch.setenv("AIMBAT_PROJECT", str(db_file))
    monkeypatch.setenv("AIMBAT_DB_URL", str(db_url))
    import aimbat.lib.project as project
    import aimbat.lib.data as data

    reload(defaults)
    reload(db)
    reload(project)
    reload(data)
    project.create_project()
    data.add_files_to_project(test_data, SeismogramFileType.SAC)

    with Session(db.engine) as session:
        yield db_file, session
    db.engine.dispose()


@pytest.fixture
def test_db_with_active_event(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
    test_data: list[Path],
) -> Generator[tuple[Path, Session], Any, Any]:
    db_file = Path(tmp_path_factory.mktemp("test_db")) / "mock.db"
    db_url: str = rf"sqlite+pysqlite:///{db_file}"
    monkeypatch.setenv("AIMBAT_PROJECT", str(db_file))
    monkeypatch.setenv("AIMBAT_DB_URL", str(db_url))
    import aimbat.lib.project as project
    import aimbat.lib.data as data
    import aimbat.lib.event as event

    reload(defaults)
    reload(db)
    reload(project)
    reload(data)
    project.create_project()
    data.add_files_to_project(test_data, SeismogramFileType.SAC)

    with Session(db.engine) as session:
        events = session.exec(select(event.AimbatEvent)).all()
        lengths = [len(e.seismograms) for e in events]
        event.set_active_event(session, events[lengths.index(max(lengths))])
        yield db_file, session
    db.engine.dispose()


@pytest.fixture()
def sac_file_good(tmp_path_factory: pytest.TempPathFactory) -> Path:
    orgfile = TESTDATA.sacfile_good
    tmpdir = tmp_path_factory.mktemp("aimbat")
    testfile = tmpdir / "good.sac"
    shutil.copy(orgfile, testfile)
    return testfile


@pytest.fixture()
def sac_instance_good(sac_file_good: Path) -> Generator[SAC, Any, Any]:
    my_sac = SAC.from_file(sac_file_good)
    try:
        yield my_sac
    finally:
        del my_sac


# @pytest.hookimpl(trylast=True)
# def pytest_sessionfinish(session: Session, exitstatus: pytest.ExitCode) -> None:
#     gc.collect()
