"""Module to define the AIMBAT project file and create the database engine."""

import sqlite3
from aimbat import settings
from sqlmodel import create_engine
from sqlalchemy import event
from sqlalchemy.pool import ConnectionPoolEntry

__all__ = ["engine"]

engine = create_engine(url=settings.db_url, echo=False)
"""AIMBAT database engine."""


# Automatically enforce foreign keys for every new connection if using SQLite
if engine.name == "sqlite":

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(
        dbapi_connection: sqlite3.Connection, connection_record: ConnectionPoolEntry
    ) -> None:
        """Enables foreign key support for SQLite connections."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
