from pysmo.classes import SAC
from sqlmodel import create_engine, Session
from pathlib import Path
from sqlalchemy.engine import Engine
from collections.abc import Generator
from typing import Any
from dataclasses import dataclass, field
import shutil
import pytest
import matplotlib.pyplot as plt
import gc
from uuid import uuid4


@dataclass
class TestData:
    multi_event: list[Path] = field(
        default_factory=lambda: sorted(
            Path(__file__).parent.glob("assets/event_*/*.bhz")
        )
    )
    sacfile_good = Path(__file__).parent / "assets/goodfile.sac"


TESTDATA = TestData()


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
        testfile = test_data_dir / f"{uuid4()}.sac"
        shutil.copy(orgfile, testfile)
        data_list.append(testfile)
    yield data_list


@pytest.fixture(scope="session")
def test_data_string(test_data: list[Path]) -> Generator[list[str], Any, Any]:
    yield [str(data) for data in test_data]


@pytest.fixture(scope="class")
def db_url(tmp_path_factory: pytest.TempPathFactory) -> Generator[str, Any, Any]:
    tmp_dir = Path(tmp_path_factory.mktemp("test_db"))
    project = tmp_dir / "mock.db"
    url: str = rf"sqlite+pysqlite:///{project}"
    yield url


@pytest.fixture(scope="class")
def db_url_with_data(
    tmp_path_factory: pytest.TempPathFactory, test_data_string: list[str]
) -> Generator[str, Any, Any]:
    from aimbat.cli.project import app as project
    from aimbat.cli.data import app as data

    tmp_dir = Path(tmp_path_factory.mktemp("test_db"))
    project_path = tmp_dir / "mock.db"
    url: str = rf"sqlite+pysqlite:///{project_path}"
    project(["create", "--db-url", url])
    args = ["add", "--db-url", url]
    args.extend(test_data_string)
    data(args)
    yield url


@pytest.fixture(scope="class")
def db_engine(db_url: str) -> Generator[Engine, Any, Any]:
    engine = create_engine(db_url, echo=False)

    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="class")
def db_session_with_project() -> Generator[Session, Any, Any]:
    from aimbat.lib.project import create_project

    url: str = r"sqlite+pysqlite:///:memory:"

    engine = create_engine(url, echo=False)

    with Session(engine) as session:
        try:
            create_project(engine)
            yield session
        finally:
            session.close()
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


@pytest.fixture()
def mock_show(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plt, "show", lambda: None)


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session: Session, exitstatus: pytest.ExitCode) -> None:
    gc.collect()
