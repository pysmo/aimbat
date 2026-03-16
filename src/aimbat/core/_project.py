from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import SQLModel, text

from aimbat.logger import logger

__all__ = ["create_project", "delete_project"]


def _project_exists(engine: Engine) -> bool:
    """Check if AIMBAT project exists by checking if aimbatevent table exists."""

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
    """Initializes a new AIMBAT project database schema and triggers.

    Args:
        engine: The SQLAlchemy/SQLModel Engine instance connected to the target database.

    Raises:
        RuntimeError: If a project schema already exists in the target database.
    """

    # Import locally to ensure SQLModel registers all table metadata before create_all()
    import aimbat.models  # noqa: F401

    logger.info(f"Creating new project in {engine.url}")

    if _project_exists(engine):
        raise RuntimeError(
            f"Unable to create a new project: project already exists at {engine.url}!"
        )

    logger.debug("Creating database tables and loading defaults.")

    SQLModel.metadata.create_all(engine)

    if engine.name == "sqlite":
        with engine.begin() as connection:
            # Trigger 1: Handle updates to existing rows
            connection.execute(
                text("""
                CREATE TRIGGER IF NOT EXISTS single_default_event_update
                BEFORE UPDATE ON aimbatevent
                FOR EACH ROW WHEN NEW.is_default = TRUE
                BEGIN
                    UPDATE aimbatevent SET is_default = NULL 
                    WHERE is_default = TRUE AND id != NEW.id;
                END;
            """)
            )

            # Trigger 2: Handle brand new default events being inserted
            connection.execute(
                text("""
                CREATE TRIGGER IF NOT EXISTS single_default_event_insert
                BEFORE INSERT ON aimbatevent
                FOR EACH ROW WHEN NEW.is_default = TRUE
                BEGIN
                    UPDATE aimbatevent SET is_default = NULL
                    WHERE is_default = TRUE;
                END;
            """)
            )

            # Trigger 3: Track last modification time when event parameters change
            connection.execute(
                text("""
                CREATE TRIGGER IF NOT EXISTS event_modified_on_params_update
                AFTER UPDATE ON aimbateventparameters
                BEGIN
                    UPDATE aimbatevent SET last_modified = datetime('now')
                    WHERE id = NEW.event_id;
                END;
            """)
            )

            # Trigger 4: Track last modification time when seismogram parameters change
            connection.execute(
                text("""
                CREATE TRIGGER IF NOT EXISTS event_modified_on_seis_params_update
                AFTER UPDATE ON aimbatseismogramparameters
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

            # Trigger 5: Null all quality when event window/bandpass/ramp parameters change.
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

            # Trigger 6: Null MCCC quality when MCCC-specific event parameters change.
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

            # Trigger 7a: Null quality when flip changes on a seismogram.
            # Flipping a trace only affects the ICCS stack if the seismogram is selected.
            # MCCC stats are invalidated if the seismogram was included in the last MCCC
            # run, which is inferred from the presence of live mccc_cc_mean stats —
            # not from select, because MCCC may have been run with --all.
            # The event-level UPDATE is ordered before the per-seismogram UPDATE so that
            # the EXISTS check sees the original (non-nulled) stats in both statements.
            connection.execute(
                text("""
                CREATE TRIGGER IF NOT EXISTS null_quality_on_seis_flip_change
                AFTER UPDATE ON aimbatseismogramparameters
                WHEN NEW.flip IS NOT OLD.flip
                BEGIN
                    -- Null iccs_cc for all event seismograms if selected (stack changed),
                    -- or just locally if deselected (the flipped seismogram's own CC is stale
                    -- even though the stack is unchanged).
                    UPDATE aimbatseismogramquality
                    SET iccs_cc = NULL
                    WHERE (
                        NEW."select" = TRUE
                        AND seismogram_id IN (
                            SELECT id FROM aimbatseismogram WHERE event_id = (
                                SELECT event_id FROM aimbatseismogram WHERE id = NEW.seismogram_id
                            )
                        )
                    ) OR (
                        NEW."select" IS NOT TRUE
                        AND seismogram_id = NEW.seismogram_id
                    );

                    -- Null event-level RMSE if this seismogram was in the last MCCC run
                    UPDATE aimbateventquality
                    SET mccc_rmse = NULL
                    WHERE EXISTS (
                        SELECT 1 FROM aimbatseismogramquality
                        WHERE seismogram_id = NEW.seismogram_id
                          AND mccc_cc_mean IS NOT NULL
                    )
                      AND event_id = (
                        SELECT event_id FROM aimbatseismogram WHERE id = NEW.seismogram_id
                    );

                    -- Null per-seismogram MCCC stats for the whole event if this seismogram
                    -- was in the last MCCC run (checked before these stats are nulled above)
                    UPDATE aimbatseismogramquality
                    SET mccc_cc_mean = NULL, mccc_cc_std = NULL, mccc_error = NULL
                    WHERE EXISTS (
                        SELECT 1 FROM aimbatseismogramquality
                        WHERE seismogram_id = NEW.seismogram_id
                          AND mccc_cc_mean IS NOT NULL
                    )
                      AND seismogram_id IN (
                        SELECT id FROM aimbatseismogram WHERE event_id = (
                            SELECT event_id FROM aimbatseismogram WHERE id = NEW.seismogram_id
                        )
                    );
                END;
            """)
            )

            # Trigger 7b: Null quality when t1 changes on a seismogram.
            # ICCS: if selected, the stack is affected so iccs_cc is stale for all;
            # if deselected, only this seismogram's own iccs_cc is stale.
            # MCCC: invalidated whenever the seismogram was in the last MCCC run,
            # inferred from live mccc_cc_mean — not select — because MCCC may have
            # been run with --all, meaning a deselected seismogram could still be included.
            connection.execute(
                text("""
                CREATE TRIGGER IF NOT EXISTS null_quality_on_seis_t1_change
                AFTER UPDATE ON aimbatseismogramparameters
                WHEN NEW.t1 IS NOT OLD.t1
                BEGIN
                    -- Null iccs_cc for all event seismograms if selected (stack changed),
                    -- otherwise only null locally.
                    UPDATE aimbatseismogramquality
                    SET iccs_cc = NULL
                    WHERE (
                        NEW."select" = TRUE
                        AND seismogram_id IN (
                            SELECT id FROM aimbatseismogram WHERE event_id = (
                                SELECT event_id FROM aimbatseismogram WHERE id = NEW.seismogram_id
                            )
                        )
                    ) OR (
                        NEW."select" IS NOT TRUE
                        AND seismogram_id = NEW.seismogram_id
                    );

                    -- Null event-level RMSE if this seismogram was in the last MCCC run
                    UPDATE aimbateventquality
                    SET mccc_rmse = NULL
                    WHERE EXISTS (
                        SELECT 1 FROM aimbatseismogramquality
                        WHERE seismogram_id = NEW.seismogram_id
                          AND mccc_cc_mean IS NOT NULL
                    )
                      AND event_id = (
                        SELECT event_id FROM aimbatseismogram WHERE id = NEW.seismogram_id
                    );

                    -- Null per-seismogram MCCC stats for the whole event if this seismogram
                    -- was in the last MCCC run
                    UPDATE aimbatseismogramquality
                    SET mccc_cc_mean = NULL, mccc_cc_std = NULL, mccc_error = NULL
                    WHERE EXISTS (
                        SELECT 1 FROM aimbatseismogramquality
                        WHERE seismogram_id = NEW.seismogram_id
                          AND mccc_cc_mean IS NOT NULL
                    )
                      AND seismogram_id IN (
                        SELECT id FROM aimbatseismogram WHERE event_id = (
                            SELECT event_id FROM aimbatseismogram WHERE id = NEW.seismogram_id
                        )
                    );
                END;
            """)
            )

            # Trigger 7c: Null quality when select changes on a seismogram.
            # ICCS stack composition changes in both directions (select → deselect and
            # vice versa), so iccs_cc is always invalidated for the whole event.
            # MCCC stats are only invalidated if the seismogram was in the last MCCC run,
            # inferred from live mccc_cc_mean — if MCCC was run with --all, changing
            # select does not change the MCCC set, so live stats remain valid.
            connection.execute(
                text("""
                CREATE TRIGGER IF NOT EXISTS null_quality_on_seis_select_change
                AFTER UPDATE ON aimbatseismogramparameters
                WHEN NEW."select" IS NOT OLD."select"
                BEGIN
                    -- Always null iccs_cc for the whole event (stack composition changed)
                    UPDATE aimbatseismogramquality
                    SET iccs_cc = NULL
                    WHERE seismogram_id IN (
                        SELECT id FROM aimbatseismogram WHERE event_id = (
                            SELECT event_id FROM aimbatseismogram WHERE id = NEW.seismogram_id
                        )
                    );

                    -- Null event-level RMSE if this seismogram was in the last MCCC run
                    UPDATE aimbateventquality
                    SET mccc_rmse = NULL
                    WHERE EXISTS (
                        SELECT 1 FROM aimbatseismogramquality
                        WHERE seismogram_id = NEW.seismogram_id
                          AND mccc_cc_mean IS NOT NULL
                    )
                      AND event_id = (
                        SELECT event_id FROM aimbatseismogram WHERE id = NEW.seismogram_id
                    );

                    -- Null per-seismogram MCCC stats for the whole event if this seismogram
                    -- was in the last MCCC run
                    UPDATE aimbatseismogramquality
                    SET mccc_cc_mean = NULL, mccc_cc_std = NULL, mccc_error = NULL
                    WHERE EXISTS (
                        SELECT 1 FROM aimbatseismogramquality
                        WHERE seismogram_id = NEW.seismogram_id
                          AND mccc_cc_mean IS NOT NULL
                    )
                      AND seismogram_id IN (
                        SELECT id FROM aimbatseismogram WHERE event_id = (
                            SELECT event_id FROM aimbatseismogram WHERE id = NEW.seismogram_id
                        )
                    );
                END;
            """)
            )


def delete_project(engine: Engine) -> None:
    """Delete the AIMBAT project.

    Raises:
        RuntimeError: If unable to delete project.
    """

    logger.info(f"Deleting project in {engine=}.")

    if _project_exists(engine):
        if engine.driver == "pysqlite":
            database = engine.url.database
            engine.dispose()
            if database == ":memory:":
                logger.info("Running database in memory, nothing to delete.")
                return
            elif database:
                project_path = Path(database)
                logger.info(f"Deleting project file: {project_path=}")
                project_path.unlink()
                return
    raise RuntimeError("Unable to find/delete project.")
