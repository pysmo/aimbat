from pysmo.classes import SAC
from sqlmodel import create_engine, Session, select
from pathlib import Path
from sqlalchemy.engine import Engine
from collections.abc import Generator, Callable
from typing import Any
from dataclasses import dataclass, field
import random
import shutil
import pytest
import matplotlib.pyplot as plt
import gc
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
) -> Generator[tuple[Path, str, Engine, Session], Any, Any]:
    db_file = Path(tmp_path_factory.mktemp("test_db")) / "mock.db"
    url: str = rf"sqlite+pysqlite:///{db_file}"
    engine = create_engine(url, echo=False)
    with Session(engine) as session:
        yield db_file, url, engine, session
    engine.dispose()


@pytest.fixture
def test_db_with_project(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[tuple[Path, str, Engine, Session], Any, Any]:
    from aimbat.lib.project import create_project

    db_file = Path(tmp_path_factory.mktemp("test_db")) / "mock.db"
    url: str = rf"sqlite+pysqlite:///{db_file}"
    engine = create_engine(url, echo=False)
    create_project(engine)
    with Session(engine) as session:
        yield db_file, url, engine, session
    engine.dispose()


@pytest.fixture
def test_db_with_data(
    tmp_path_factory: pytest.TempPathFactory,
    test_data: list[Path],
) -> Generator[tuple[Path, str, Engine, Session], Any, Any]:
    from aimbat.lib.project import create_project
    from aimbat.lib.data import add_files_to_project, SeismogramFileType

    db_file = Path(tmp_path_factory.mktemp("test_db")) / "mock.db"
    url: str = rf"sqlite+pysqlite:///{db_file}"
    engine = create_engine(url, echo=False)
    create_project(engine)

    with Session(engine) as session:
        add_files_to_project(session, test_data, SeismogramFileType.SAC)
        session.flush()
        yield db_file, url, engine, session
    engine.dispose()


@pytest.fixture
def test_db_with_active_event(
    tmp_path_factory: pytest.TempPathFactory,
    test_data: list[Path],
) -> Generator[tuple[Path, str, Engine, Session], Any, Any]:
    from aimbat.lib.project import create_project
    from aimbat.lib.data import add_files_to_project, SeismogramFileType
    from aimbat.lib.event import set_active_event, AimbatEvent

    db_file = Path(tmp_path_factory.mktemp("test_db")) / "mock.db"
    url: str = rf"sqlite+pysqlite:///{db_file}"
    engine = create_engine(url, echo=False)
    create_project(engine)

    with Session(engine) as session:
        add_files_to_project(session, test_data, SeismogramFileType.SAC)
        events = session.exec(select(AimbatEvent)).all()
        lengths = [len(e.seismograms) for e in events]
        set_active_event(session, events[lengths.index(max(lengths))])
        session.flush()
        yield db_file, url, engine, session
    engine.dispose()


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


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session: Session, exitstatus: pytest.ExitCode) -> None:
    gc.collect()
