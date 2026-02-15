"""Module to define the AIMBAT project file and create the database engine."""

from sqlmodel import create_engine
from aimbat.config import settings

engine = create_engine(url=settings.db_url, echo=False)
"""AIMBAT database engine."""
