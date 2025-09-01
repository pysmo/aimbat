"""Module to define the AIMBAT project file and create the database engine."""

from sqlmodel import create_engine
from os import environ, getcwd


AIMBAT_PROJECT: str = environ.get("AIMBAT_PROJECT", f"{getcwd()}/aimbat.db")
"""AIMBAT project file location.

AIMBAT_PROJECT defines the sqlite file where the project lives. If
there is an environment variable by the same name, the value inside
it is used for the project. If there is no environment variable,
set it to `aimbat.db` in the current working directory.
"""
AIMBAT_DB_URL: str = rf"sqlite+pysqlite:///{AIMBAT_PROJECT}"
"""AIMBAT database url.

AIMBAT_DB_URL defines the database url to use for the project. It
is set to `sqlite+pysqlite:///{AIMBAT_PROJECT}` by default.
"""

engine = create_engine(url=AIMBAT_DB_URL, echo=False)
"""AIMBAT database engine."""
