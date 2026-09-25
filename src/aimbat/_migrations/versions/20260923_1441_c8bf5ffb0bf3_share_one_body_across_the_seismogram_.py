"""share one body across the seismogram quality triggers

Revision ID: c8bf5ffb0bf3
Revises: 1d11b0d28c31
Create Date: 2026-09-23 14:41:25.955522+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8bf5ffb0bf3"
down_revision: str | None = "1d11b0d28c31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TRIGGERS = (
    "null_quality_on_seis_flip_change",
    "null_quality_on_seis_t1_change",
    "null_quality_on_seis_select_change",
)

# The three triggers' SQL is unchanged; only their comments are, now that
# `core/_project.py::create_project()` builds all three from one template
# rather than spelling each out. The bodies are compared as text, comments
# included, by tests/integration/core/test_migrations.py::test_same_triggers,
# so the wording has to be recreated here too.

_NULL_QUALITY_ON_SEIS_FLIP_CHANGE_NEW = """
    CREATE TRIGGER IF NOT EXISTS null_quality_on_seis_flip_change
    AFTER UPDATE ON aimbatseismogramparameters
    WHEN NEW.flip IS NOT OLD.flip
    BEGIN
        -- Null iccs_cc for all event seismograms if selected (stack changed),
        -- or just locally if deselected (the changed seismogram's own CC is
        -- stale even though the stack is unchanged).
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
"""

_NULL_QUALITY_ON_SEIS_T1_CHANGE_NEW = """
    CREATE TRIGGER IF NOT EXISTS null_quality_on_seis_t1_change
    AFTER UPDATE ON aimbatseismogramparameters
    WHEN NEW.t1 IS NOT OLD.t1
    BEGIN
        -- Null iccs_cc for all event seismograms if selected (stack changed),
        -- or just locally if deselected (the changed seismogram's own CC is
        -- stale even though the stack is unchanged).
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
"""

_NULL_QUALITY_ON_SEIS_SELECT_CHANGE_NEW = """
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
"""

_NULL_QUALITY_ON_SEIS_FLIP_CHANGE_OLD = """
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
"""

_NULL_QUALITY_ON_SEIS_T1_CHANGE_OLD = """
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
"""

_NULL_QUALITY_ON_SEIS_SELECT_CHANGE_OLD = """
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
"""


def upgrade() -> None:
    for name in _TRIGGERS:
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS {name}"))
    op.execute(sa.text(_NULL_QUALITY_ON_SEIS_FLIP_CHANGE_NEW))
    op.execute(sa.text(_NULL_QUALITY_ON_SEIS_T1_CHANGE_NEW))
    op.execute(sa.text(_NULL_QUALITY_ON_SEIS_SELECT_CHANGE_NEW))


def downgrade() -> None:
    for name in _TRIGGERS:
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS {name}"))
    op.execute(sa.text(_NULL_QUALITY_ON_SEIS_FLIP_CHANGE_OLD))
    op.execute(sa.text(_NULL_QUALITY_ON_SEIS_T1_CHANGE_OLD))
    op.execute(sa.text(_NULL_QUALITY_ON_SEIS_SELECT_CHANGE_OLD))
