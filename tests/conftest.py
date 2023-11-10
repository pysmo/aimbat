import shutil
import pytest
import os
from unittest import mock
from pysmo import SAC
from sqlmodel import create_engine


TESTDATA = dict(
    sacfile_good=os.path.join(os.path.dirname(__file__), "assets/goodfile.sac"),
)


@pytest.fixture()
def sac_good(tmp_path_factory):  # type: ignore
    orgfile = TESTDATA["sacfile_good"]
    tmpdir = tmp_path_factory.mktemp("aimbat")
    testfile = os.path.join(tmpdir, "good.sac")
    shutil.copy(orgfile, testfile)
    return SAC.from_file(testfile)


@pytest.fixture(scope="class")
def project_directory(tmp_path_factory):  # type: ignore
    """Define temporary project directory for testing."""
    tmpdir = tmp_path_factory.mktemp("aimbat")
    return tmpdir


@pytest.fixture()
def tmp_project_filename(tmp_path_factory):  # type: ignore
    tmpdir = tmp_path_factory.mktemp("aimbat")
    return tmpdir / "pytest-tmp.db"


@pytest.fixture()
def tmp_db_engine(tmp_project_filename):  # type: ignore
    return create_engine(rf"sqlite+pysqlite:///{tmp_project_filename}")


@pytest.fixture(scope="class")
def mock_project_env(project_directory):  # type: ignore
    with mock.patch.dict(
        os.environ, {"AIMBAT_PROJECT": f"{str(project_directory)}/pytest-mock-env.db"}
    ):
        yield
