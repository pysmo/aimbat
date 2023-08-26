from .defaults import defaults_load_global_values
from . import models  # noqa: F401
from sqlmodel import SQLModel, create_engine
from os import getcwd, environ
from pathlib import Path
from typing import Any


# AIMBAT_PROJECT defines the sqlite file where the project lives. If
# there is an environment variable by the same name, the value inside
# it is used for the project. If there is no environment variable,
# set set it to aimbat.db in the current working directory.
AIMBAT_PROJECT: str = environ.get("AIMBAT_PROJECT", f"{getcwd()}/aimbat.db")


def project_db_engine(project_file: str = AIMBAT_PROJECT) -> Any:
    """Create DB engine."""

    project_db = rf"sqlite+pysqlite:///{project_file}"

    return create_engine(project_db)


def project_new(project_file: str = AIMBAT_PROJECT) -> None:
    """Create a new AIMBAT project."""

    # stop here if there is an existing aimbat.db file
    if Path(project_file).exists():
        raise RuntimeError(f"Unable to create a new project: {project_file} exists!")

    engine = project_db_engine(project_file)

    # create tables
    SQLModel.metadata.create_all(engine)

    # load defaults
    defaults_load_global_values(engine)


def project_del(project_file: str = AIMBAT_PROJECT) -> None:
    """Delete the AIMBAT project."""

    try:
        Path(project_file).unlink()

    except FileNotFoundError:
        raise RuntimeWarning(f"Unable to delete project: file {project_file} not found.")


def project_info(project_file: str = AIMBAT_PROJECT) -> Any:
    """Show AIMBAT project information."""

    if not Path(project_file).exists():
        raise RuntimeError(f"Project {project_file} not found!")

    else:
        raise NotImplementedError
