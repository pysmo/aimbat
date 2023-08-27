from sqlmodel import create_engine
from os import environ, getcwd


# AIMBAT_PROJECT defines the sqlite file where the project lives. If
# there is an environment variable by the same name, the value inside
# it is used for the project. If there is no environment variable,
# set set it to aimbat.db in the current working directory.
AIMBAT_PROJECT: str = environ.get("AIMBAT_PROJECT", f"{getcwd()}/aimbat.db")


def db_engine(project_file: str = AIMBAT_PROJECT):  # type: ignore
    """Create DB engine."""

    project_db = rf"sqlite+pysqlite:///{project_file}"

    return create_engine(project_db)
