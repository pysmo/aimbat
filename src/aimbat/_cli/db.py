"""
Manage the AIMBAT project database schema.

Schema changes are applied via [Alembic](https://alembic.sqlalchemy.org).
Most users never need this command group — `aimbat project create` already
creates a database with the current schema. It exists for bringing an
*existing* project database up to date after an AIMBAT upgrade that changed
the schema, including databases created before this command group existed.
"""

from cyclopts import App

from .common import DebugParameter, handle_issues

app = App(name="db", help=__doc__, help_format="markdown")


@app.command(name="upgrade")
@handle_issues
def cli_db_upgrade(*, _: DebugParameter = DebugParameter()) -> None:
    """Upgrade the project database to the latest schema version.

    Safe to run on a database that is already up to date (does nothing) or
    on one that predates Alembic (verifies its schema matches before
    stamping it, then upgrades).
    """
    import warnings

    from aimbat.core import upgrade_project
    from aimbat.core._migrations import SchemaStaleWarning
    from aimbat.core._project import _project_exists
    from aimbat.db import engine

    # The staleness warning's whole message is "run `aimbat db upgrade`" -
    # showing it while that command is already running is just noise.
    # Scoped to this call only; restored automatically on exit.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SchemaStaleWarning)

        if not _project_exists(engine):
            raise RuntimeError(
                'No AIMBAT project found. Try running "aimbat project create" first.'
            )

        upgrade_project(engine)


@app.command(name="current")
@handle_issues
def cli_db_current(*, _: DebugParameter = DebugParameter()) -> None:
    """Show the schema version the project database is currently at."""
    from aimbat.core import get_current_revision
    from aimbat.core._project import _project_exists
    from aimbat.db import engine

    if not _project_exists(engine):
        raise RuntimeError(
            'No AIMBAT project found. Try running "aimbat project create" first.'
        )

    revision = get_current_revision(engine)
    if revision is None:
        print("No Alembic version history (pre-dates schema versioning).")
    else:
        print(revision)


if __name__ == "__main__":
    app()
