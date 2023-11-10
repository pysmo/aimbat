from pysmo import SAC
from sqlmodel import create_engine
import shutil
import pytest
import os
import aimbat.lib.db
import aimbat.lib.project
import aimbat.lib.defaults
import aimbat.lib.data
import aimbat.lib.io


TESTDATA = dict(
    sacfile_good=os.path.join(os.path.dirname(__file__), "assets/goodfile.sac"),
)


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
def project_directory(tmp_path_factory):  # type: ignore
    """Define temporary project directory for testing."""
    tmpdir = tmp_path_factory.mktemp("aimbat")
    yield tmpdir


@pytest.fixture(autouse=True)
def mock_aimbat_project(monkeypatch, tmp_path_factory):  # type: ignore

    project = tmp_path_factory.mktemp("aimbat") / "mock.db"
    engine = create_engine(rf"sqlite+pysqlite:///{project}")

    monkeypatch.setattr(aimbat.lib.db, "AIMBAT_PROJECT", project)
    monkeypatch.setattr(aimbat.lib.project, "AIMBAT_PROJECT", project)

    monkeypatch.setattr(aimbat.lib.db, "engine", engine)
    monkeypatch.setattr(aimbat.lib.project, "engine", engine)
    monkeypatch.setattr(aimbat.lib.defaults, "engine", engine)
    monkeypatch.setattr(aimbat.lib.data, "engine", engine)
    monkeypatch.setattr(aimbat.lib.io, "engine", engine)
