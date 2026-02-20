"""Module to define the AIMBAT project file and create the database engine."""

from aimbat import settings
from sqlmodel import create_engine

__all__ = ["engine"]

engine = create_engine(url=settings.db_url, echo=False)
"""AIMBAT database engine."""
