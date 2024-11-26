from pysmo import SAC
from sqlmodel import create_engine, Session
from pathlib import Path
import sqlalchemy as sa
import shutil
import pytest
import os
import matplotlib.pyplot as plt
from uuid import uuid4

TESTDATA = dict(
    multi_event=sorted(Path(os.path.dirname(__file__)).glob("assets/event_*/*.bhz")),
    sacfile_good=Path(os.path.dirname(__file__)) / "assets/goodfile.sac",
)


@pytest.fixture(scope="session")
def test_data_dir(tmp_path_factory):  # type: ignore
    tmp_dir = tmp_path_factory.mktemp("test_data")

    yield tmp_dir

    shutil.rmtree(tmp_dir)


@pytest.fixture(scope="session")
def test_data(test_data_dir):  # type: ignore
    data_list = []
    for orgfile in TESTDATA["multi_event"]:
        testfile = test_data_dir / f"{uuid4()}.sac"
        shutil.copy(orgfile, testfile)
        data_list.append(testfile)
    return data_list


@pytest.fixture(scope="session")
def test_data_string(test_data):  # type: ignore
    return [str(data) for data in test_data]


@pytest.fixture(scope="session")
def db_engine_with_proj():  # type: ignore
    from aimbat.lib.project import create_project

    engine_ = create_engine("sqlite+pysqlite:///:memory:", echo=False)

    create_project(engine_)

    yield engine_

    engine_.dispose()


@pytest.fixture(scope="function", autouse=True)
def db_session(db_engine_with_proj):  # type: ignore
    """yield a session after 'project create' and rollback after test."""
    connection = db_engine_with_proj.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    nested = connection.begin_nested()

    @sa.event.listens_for(session, "after_transaction_end")
    def end_savepoint(session, transaction):  # type: ignore
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function", autouse=True)
def db_url(tmp_path_factory):  # type: ignore
    project = tmp_path_factory.mktemp("aimbat") / "mock.db"
    url: str = rf"sqlite+pysqlite:///{project}"
    yield url


@pytest.fixture(scope="function", autouse=True)
def db_engine(db_url):  # type: ignore
    engine = create_engine(db_url, echo=False)

    yield engine

    engine.dispose()


@pytest.fixture()
def sac_file_good(tmp_path_factory):  # type: ignore
    orgfile = TESTDATA["sacfile_good"]
    tmpdir = tmp_path_factory.mktemp("aimbat")
    testfile = os.path.join(tmpdir, "good.sac")
    shutil.copy(orgfile, testfile)
    return testfile


@pytest.fixture()
def sac_instance_good(sac_file_good):  # type: ignore
    my_sac = SAC.from_file(sac_file_good)
    yield my_sac
    del my_sac


@pytest.fixture()
def mock_show(monkeypatch):  # type: ignore
    monkeypatch.setattr(plt, "show", lambda: None)
