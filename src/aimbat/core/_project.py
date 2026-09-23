"""Create and delete AIMBAT project databases, including the SQLite quality-invalidation triggers."""

from pathlib import Path

from sqlalchemy import Connection, Engine
from sqlmodel import SQLModel, text

from aimbat.logger import logger

__all__ = ["create_project", "delete_project"]


# ---------------------------------------------------------------------------
# Quality-invalidation triggers for a seismogram parameter change (5a/5b/5c).
#
# The three differ only in what makes `iccs_cc` stale; what makes the MCCC
# stats stale is the same question in all three, so they share one body.
# Every trigger here also exists in the migration chain, and
# `tests/integration/core/test_migrations.py::test_same_triggers` compares the
# two - so changing this text, comments included, needs a migration that drops
# and recreates the triggers.
# ---------------------------------------------------------------------------

_EVENT_SEISMOGRAMS = """
            SELECT id FROM aimbatseismogram WHERE event_id = (
                SELECT event_id FROM aimbatseismogram WHERE id = NEW.seismogram_id
            )"""
"""Every seismogram of the event the updated seismogram belongs to."""

_WAS_IN_LAST_MCCC_RUN = """
            SELECT 1 FROM aimbatseismogramquality
            WHERE seismogram_id = NEW.seismogram_id
              AND mccc_cc_mean IS NOT NULL"""
"""Whether the updated seismogram was included in the last MCCC run.

Inferred from live `mccc_cc_mean` stats rather than from `select`, because
MCCC may have been run with `--all`, in which case a deselected seismogram
was included too.
"""

_NULL_ICCS_IF_SELECTED = f"""
        -- Null iccs_cc for all event seismograms if selected (stack changed),
        -- or just locally if deselected (the changed seismogram's own CC is
        -- stale even though the stack is unchanged).
        UPDATE aimbatseismogramquality
        SET iccs_cc = NULL
        WHERE (
            NEW."select" = TRUE
            AND seismogram_id IN ({_EVENT_SEISMOGRAMS}
            )
        ) OR (
            NEW."select" IS NOT TRUE
            AND seismogram_id = NEW.seismogram_id
        );"""
"""Null `iccs_cc` across the event, or only locally when deselected."""

_NULL_ICCS_FOR_EVENT = f"""
        -- Always null iccs_cc for the whole event (stack composition changed)
        UPDATE aimbatseismogramquality
        SET iccs_cc = NULL
        WHERE seismogram_id IN ({_EVENT_SEISMOGRAMS}
        );"""
"""Null `iccs_cc` across the whole event unconditionally."""

_NULL_MCCC = f"""
        -- Null event-level RMSE if this seismogram was in the last MCCC run
        UPDATE aimbateventquality
        SET mccc_rmse = NULL
        WHERE EXISTS ({_WAS_IN_LAST_MCCC_RUN}
        )
          AND event_id = (
            SELECT event_id FROM aimbatseismogram WHERE id = NEW.seismogram_id
        );

        -- Null per-seismogram MCCC stats for the whole event if this seismogram
        -- was in the last MCCC run (checked before these stats are nulled above)
        UPDATE aimbatseismogramquality
        SET mccc_cc_mean = NULL, mccc_cc_std = NULL, mccc_error = NULL
        WHERE EXISTS ({_WAS_IN_LAST_MCCC_RUN}
        )
          AND seismogram_id IN ({_EVENT_SEISMOGRAMS}
        );"""
"""Null the MCCC stats the updated seismogram took part in.

The event-level statement is ordered before the per-seismogram one so both
see the original, not-yet-nulled stats.
"""


def _null_quality_trigger(name: str, when: str, null_iccs: str) -> str:
    """Build one of the seismogram-parameter quality-invalidation triggers.

    Args:
        name: Trigger name.
        when: The trigger's `WHEN` condition.
        null_iccs: The statement nulling `iccs_cc`, the one part that differs
            between the three triggers.
    """
    return f"""
    CREATE TRIGGER IF NOT EXISTS {name}
    AFTER UPDATE ON aimbatseismogramparameters
    WHEN {when}
    BEGIN{null_iccs}
{_NULL_MCCC}
    END;
"""


def _project_exists(engine: Engine) -> bool:
    """Check whether an AIMBAT project already exists at `engine`.

    Presence is inferred from the `aimbatevent` table rather than any
    explicit marker.

    Args:
        engine: The SQLAlchemy/SQLModel Engine instance connected to the
            target database.

    Returns:
        True if the `aimbatevent` table exists, False otherwise.

    Raises:
        RuntimeError: If `engine`'s driver is not `pysqlite`.
    """

    _TABLE_TO_CHECK = "aimbatevent"

    logger.debug(
        f"Checking if project already exists with {engine=} by searching for the {_TABLE_TO_CHECK} table."
    )

    if engine.driver == "pysqlite":
        with engine.connect() as connection:
            result = connection.execute(
                text(f"PRAGMA table_info({_TABLE_TO_CHECK})")
            ).all()
            if result == []:
                logger.debug("No project found.")
                return False
            logger.debug("Project found.")
            return True
    raise RuntimeError(
        f"Unable to determine if project already exists using {engine=}."
    )


def create_project(engine: Engine) -> None:
    """Initialise a new AIMBAT project database schema and triggers.

    Creates all tables from `SQLModel.metadata`, then, for SQLite engines,
    creates the triggers that track event modification times and
    automatically null quality metrics when the parameters they depend on
    change. The new database is stamped at the latest Alembic revision.

    Tables, triggers and the stamp are written in one transaction, so a
    failure partway through leaves no half-made project behind: SQLite rolls
    schema changes back like any other statement. A database file may still
    be created on disk by the connection itself, but it will hold no AIMBAT
    tables, and `create_project` can simply be run again.

    Args:
        engine: The SQLAlchemy/SQLModel Engine instance connected to the target database.

    Raises:
        RuntimeError: If a project schema already exists in the target database.
    """

    # Import locally to ensure SQLModel registers all table metadata before create_all()
    import aimbat.models  # noqa: F401

    logger.info(f"Creating new project in {engine.url}.")

    if _project_exists(engine):
        raise RuntimeError(
            f"Unable to create a new project: project already exists at {engine.url}!"
        )

    logger.debug("Creating database tables and loading defaults.")

    # Import locally to break a circular import at module level.
    from aimbat.core._migrations import stamp_head

    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        # SQLite can roll DDL back, but the driver commits before each DDL
        # statement unless the transaction is opened by hand - which would
        # leave a failure partway through this function half-applied, as a
        # database with tables but no quality invalidation, or no stamp.
        # AUTOCOMMIT hands transaction control over, so the BEGIN below
        # covers the tables, the triggers and the stamp together.
        connection.exec_driver_sql("BEGIN")
        try:
            SQLModel.metadata.create_all(connection)

            if engine.name == "sqlite":
                _create_triggers(connection)

            # Mark the new database as being at the latest Alembic revision so
            # that `aimbat db upgrade` treats it consistently with a database
            # that was brought up to date via a real migration, rather than as
            # an unversioned legacy database.
            stamp_head(connection)
        except Exception:
            connection.exec_driver_sql("ROLLBACK")
            raise

        connection.exec_driver_sql("COMMIT")


def _create_triggers(connection: Connection) -> None:
    """Create the modification-tracking and quality-invalidation triggers.

    Args:
        connection: Open connection to the project database.
    """
    # Trigger 1: Track last modification time when event parameters change.
    # Lists every event parameter except `completed`, which is bookkeeping
    # with no effect on ICCS/MCCC processing (it is likewise excluded from
    # the snapshot parameter hashes in core/_snapshot.py). `last_modified`
    # is the general "something changed, repaint" signal for the TUI; the
    # narrower `stack_modified` (triggers 1b/2b) is what drives ICCS
    # staleness.
    connection.execute(
        text("""
        CREATE TRIGGER IF NOT EXISTS event_modified_on_params_update
        AFTER UPDATE ON aimbateventparameters
        WHEN (NEW.ramp_width IS NOT OLD.ramp_width)
          OR (NEW.window_pre IS NOT OLD.window_pre)
          OR (NEW.window_post IS NOT OLD.window_post)
          OR (NEW.bandpass_apply IS NOT OLD.bandpass_apply)
          OR (NEW.bandpass_fmin IS NOT OLD.bandpass_fmin)
          OR (NEW.bandpass_fmax IS NOT OLD.bandpass_fmax)
          OR (NEW.corners IS NOT OLD.corners)
          OR (NEW.min_cc IS NOT OLD.min_cc)
          OR (NEW.mccc_damp IS NOT OLD.mccc_damp)
          OR (NEW.mccc_min_cc IS NOT OLD.mccc_min_cc)
        BEGIN
            UPDATE aimbatevent SET last_modified = strftime('%Y-%m-%d %H:%M:%f', 'now')
            WHERE id = NEW.event_id;
        END;
    """)
    )

    # Trigger 2: Track last modification time when seismogram parameters
    # change. Lists every AimbatSeismogramParametersBase field (flip,
    # select, t1) so a no-op UPDATE (value unchanged) doesn't bump
    # last_modified and cause a spurious TUI repaint.
    connection.execute(
        text("""
        CREATE TRIGGER IF NOT EXISTS event_modified_on_seis_params_update
        AFTER UPDATE ON aimbatseismogramparameters
        WHEN (NEW.flip IS NOT OLD.flip)
          OR (NEW."select" IS NOT OLD."select")
          OR (NEW.t1 IS NOT OLD.t1)
        BEGIN
            UPDATE aimbatevent
            SET last_modified = strftime('%Y-%m-%d %H:%M:%f', 'now')
            WHERE id = (
                SELECT event_id FROM aimbatseismogram
                WHERE id = NEW.seismogram_id
            );
        END;
    """)
    )

    # Trigger 1b: Track when an event parameter that changes the ICCS
    # stack is modified. This is the subset of trigger 1's columns that
    # actually alter the aligned signal - matching trigger 3's WHEN
    # clause - so `stack_modified` (and therefore ICCS-instance
    # staleness) is not bumped by an MCCC-only or `min_cc` change.
    # `min_cc` only feeds the autoselect threshold, which `run_iccs`
    # refreshes on the instance per run.
    connection.execute(
        text("""
        CREATE TRIGGER IF NOT EXISTS event_stack_modified_on_params_update
        AFTER UPDATE ON aimbateventparameters
        WHEN (NEW.window_pre IS NOT OLD.window_pre)
          OR (NEW.window_post IS NOT OLD.window_post)
          OR (NEW.ramp_width IS NOT OLD.ramp_width)
          OR (NEW.bandpass_apply IS NOT OLD.bandpass_apply)
          OR (NEW.bandpass_fmin IS NOT OLD.bandpass_fmin)
          OR (NEW.bandpass_fmax IS NOT OLD.bandpass_fmax)
          OR (NEW.corners IS NOT OLD.corners)
        BEGIN
            UPDATE aimbatevent SET stack_modified = strftime('%Y-%m-%d %H:%M:%f', 'now')
            WHERE id = NEW.event_id;
        END;
    """)
    )

    # Trigger 2b: Track when a per-seismogram parameter that changes the
    # ICCS stack (t1, flip, select) is modified.
    connection.execute(
        text("""
        CREATE TRIGGER IF NOT EXISTS event_stack_modified_on_seis_params_update
        AFTER UPDATE ON aimbatseismogramparameters
        WHEN (NEW.t1 IS NOT OLD.t1)
          OR (NEW.flip IS NOT OLD.flip)
          OR (NEW."select" IS NOT OLD."select")
        BEGIN
            UPDATE aimbatevent
            SET stack_modified = strftime('%Y-%m-%d %H:%M:%f', 'now')
            WHERE id = (
                SELECT event_id FROM aimbatseismogram
                WHERE id = NEW.seismogram_id
            );
        END;
    """)
    )

    # Trigger 3: Null all quality when event window/bandpass/ramp parameters change.
    # These parameters change the signal data used by both ICCS and MCCC.
    connection.execute(
        text("""
        CREATE TRIGGER IF NOT EXISTS null_all_quality_on_window_bandpass_change
        AFTER UPDATE ON aimbateventparameters
        WHEN (NEW.window_pre IS NOT OLD.window_pre)
          OR (NEW.window_post IS NOT OLD.window_post)
          OR (NEW.ramp_width IS NOT OLD.ramp_width)
          OR (NEW.bandpass_apply IS NOT OLD.bandpass_apply)
          OR (NEW.bandpass_fmin IS NOT OLD.bandpass_fmin)
          OR (NEW.bandpass_fmax IS NOT OLD.bandpass_fmax)
          OR (NEW.corners IS NOT OLD.corners)
        BEGIN
            UPDATE aimbateventquality
            SET mccc_rmse = NULL
            WHERE event_id = NEW.event_id;
            UPDATE aimbatseismogramquality
            SET iccs_cc = NULL, mccc_cc_mean = NULL, mccc_cc_std = NULL, mccc_error = NULL
            WHERE seismogram_id IN (
                SELECT id FROM aimbatseismogram WHERE event_id = NEW.event_id
            );
        END;
    """)
    )

    # Trigger 4: Null MCCC quality when MCCC-specific event parameters change.
    # These parameters affect only the MCCC inversion, not the underlying signal,
    # so iccs_cc remains valid.
    connection.execute(
        text("""
        CREATE TRIGGER IF NOT EXISTS null_mccc_quality_on_mccc_params_change
        AFTER UPDATE ON aimbateventparameters
        WHEN (NEW.mccc_damp IS NOT OLD.mccc_damp)
          OR (NEW.mccc_min_cc IS NOT OLD.mccc_min_cc)
        BEGIN
            UPDATE aimbateventquality
            SET mccc_rmse = NULL
            WHERE event_id = NEW.event_id;
            UPDATE aimbatseismogramquality
            SET mccc_cc_mean = NULL, mccc_cc_std = NULL, mccc_error = NULL
            WHERE seismogram_id IN (
                SELECT id FROM aimbatseismogram WHERE event_id = NEW.event_id
            );
        END;
    """)
    )

    # Triggers 5a/5b/5c: Null quality when flip, t1 or select changes on
    # a seismogram. Flipping or repicking a trace only affects the ICCS
    # stack if the seismogram is selected; changing select itself always
    # does, in both directions.
    for name, when, null_iccs in (
        (
            "null_quality_on_seis_flip_change",
            "NEW.flip IS NOT OLD.flip",
            _NULL_ICCS_IF_SELECTED,
        ),
        (
            "null_quality_on_seis_t1_change",
            "NEW.t1 IS NOT OLD.t1",
            _NULL_ICCS_IF_SELECTED,
        ),
        (
            "null_quality_on_seis_select_change",
            'NEW."select" IS NOT OLD."select"',
            _NULL_ICCS_FOR_EVENT,
        ),
    ):
        connection.execute(text(_null_quality_trigger(name, when, null_iccs)))


def delete_project(engine: Engine) -> None:
    """Delete the AIMBAT project.

    For a file-based SQLite database, deletes the database file itself. For
    an in-memory database, this is a no-op beyond disposing the engine.

    Args:
        engine: The SQLAlchemy/SQLModel Engine instance connected to the
            target database.

    Raises:
        RuntimeError: If no project exists at `engine`, or if `engine`'s
            driver is not `pysqlite`.
    """

    logger.info(f"Deleting project at {engine.url}.")

    if not _project_exists(engine):
        raise RuntimeError("No project found to delete.")

    if engine.driver == "pysqlite":
        database = engine.url.database
        engine.dispose()
        if database == ":memory:":
            logger.info("Running database in memory, nothing to delete.")
            return
        elif database:
            project_path = Path(database)
            resolved = project_path.resolve()
            if resolved == Path(resolved.anchor) or resolved == Path.home():
                raise RuntimeError(
                    f"Refusing to delete suspicious project path: {resolved}."
                )
            logger.info(f"Deleting project file: {project_path}.")
            project_path.unlink()
            for suffix in ("-wal", "-shm"):
                project_path.with_name(project_path.name + suffix).unlink(
                    missing_ok=True
                )
            return

    raise RuntimeError(
        f"Unable to delete project: unsupported engine driver '{engine.driver}'."
    )
