import pytest
import os
import tempfile


@pytest.fixture(scope="class")
def project_directory(tmp_path_factory):  # type: ignore
    """Define temporary project directory for testing."""
    tmpdir = tmp_path_factory.mktemp("aimbat")
    return tmpdir


@pytest.fixture(scope="class")
def tmp_project_engine(project_directory):  # type: ignore
    from aimbat.lib.project import project_new, project_db_engine
    project_file = f"{project_directory}/pytest-aimbat.db"
    project_new(project_file=project_file)
    return project_db_engine(project_file=project_file)


# Set AIMBAT_PROJECT to a temporary file for the whole test
# I don't know how to do this with pytest fixtures...
def my_mock_env() -> None:
    with tempfile.TemporaryDirectory() as tmpfile:
        os.environ["AIMBAT_PROJECT"] = f"{tmpfile}"


my_mock_env()
