"""add stack_modified and its triggers

Revision ID: 2baa7d628f32
Revises: 4386151d11e2
Create Date: 2026-09-02 18:52:22.846693+00:00

`aimbatevent.stack_modified` is bumped only by the parameter changes that
alter the ICCS stack (event window / ramp / bandpass / corners, and
per-seismogram t1 / flip / select), so an MCCC-only parameter change no
longer forces an ICCS-instance rebuild. `last_modified` keeps tracking
every parameter change and stays the general "repaint" signal.

Triggers 1b and 2b below must stay byte-for-byte (modulo whitespace) in
sync with core/_project.py::create_project() - checked by
tests/integration/core/test_migrations.py::test_same_triggers. Plain
``ALTER TABLE ADD COLUMN`` / ``CREATE TRIGGER`` are used, not
``batch_alter_table``: neither needs a table rebuild.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import aimbat.types

# revision identifiers, used by Alembic.
revision: str = "2baa7d628f32"
down_revision: str | None = "4386151d11e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STACK_MODIFIED_ON_PARAMS_UPDATE = """
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
"""

_STACK_MODIFIED_ON_SEIS_PARAMS_UPDATE = """
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
"""


def upgrade() -> None:
    op.add_column(
        "aimbatevent",
        sa.Column(
            "stack_modified",
            aimbat.types.SAPandasTimestamp(timezone=True),
            nullable=True,
        ),
    )
    # Seed from last_modified: existing instances treat the last parameter
    # change as a possible stack change (conservative - at worst one extra
    # rebuild on next open).
    op.execute("UPDATE aimbatevent SET stack_modified = last_modified")
    op.execute(sa.text(_STACK_MODIFIED_ON_PARAMS_UPDATE))
    op.execute(sa.text(_STACK_MODIFIED_ON_SEIS_PARAMS_UPDATE))


def downgrade() -> None:
    op.execute(
        sa.text("DROP TRIGGER IF EXISTS event_stack_modified_on_seis_params_update")
    )
    op.execute(sa.text("DROP TRIGGER IF EXISTS event_stack_modified_on_params_update"))
    op.drop_column("aimbatevent", "stack_modified")
