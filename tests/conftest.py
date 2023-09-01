import pytest
import os
from unittest import mock


@pytest.fixture(scope="class")
def project_directory(tmp_path_factory):  # type: ignore
    """Define temporary project directory for testing."""
    tmpdir = tmp_path_factory.mktemp("aimbat")
    return tmpdir


@pytest.fixture(scope="class", autouse=True)
def mock_aimbat_project_env(project_directory):  # type: ignore
    p = project_directory / "pytest.db"
    with mock.patch.dict(os.environ, {"AIMBAT_PROJECT": f"{str(p)}"}):
        yield


@pytest.mark.depends(depends=["tests/lib/test_project.py::TestProject.test_lib_project"],
                     scope="class", autouse=True)
@pytest.fixture()
def tmp_project(mock_aimbat_project_env):  # type: ignore
    """Create an AIMBAT project for other test functions."""
    from aimbat.lib import project

    yield project.project_new()
    project.project_del()
