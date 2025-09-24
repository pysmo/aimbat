"""Module to define the AIMBAT project file and create the database engine."""

from sqlmodel import create_engine
import aimbat.lib.defaults as defaults


engine = create_engine(url=defaults.AIMBAT_DB_URL, echo=False)
"""AIMBAT database engine."""
