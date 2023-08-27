import pytest
import os
from unittest import mock


@pytest.fixture(scope="function", autouse=True)
def mock_aimbat_project_env(tmp_path):  # type: ignore
    d = tmp_path / "aimbat"
    d.mkdir()
    p = d / "pytest.db"
    with mock.patch.dict(os.environ, {"AIMBAT_PROJECT": f"{str(p)}"}):
        yield


@pytest.fixture(scope="class")
def project_directory(tmp_path_factory):  # type: ignore
    """Define temporary project directory for testing."""
    tmpdir = tmp_path_factory.mktemp("aimbat")
    return tmpdir


@pytest.fixture(scope="class")
def tmp_project_engine(project_directory):  # type: ignore
    from aimbat.lib.db import db_engine
    from aimbat.lib.project import project_new
    project_file = f"{project_directory}/pytest-aimbat.db"
    project_new(project_file=project_file)
    return db_engine(project_file=project_file)


@pytest.mark.depends(depends=["tests/lib/test_project.py::TestProject.test_lib_project"],
                     scope="session")
@pytest.fixture()
def cli_project():  # type: ignore
    """Create an AIMBAT project for other test functions."""
    from aimbat.lib import project

    yield project.project_new()
    project.project_del()
