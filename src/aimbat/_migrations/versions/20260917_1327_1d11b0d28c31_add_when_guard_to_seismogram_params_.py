"""add WHEN guard to seismogram params modified trigger

Revision ID: 1d11b0d28c31
Revises: 2baa7d628f32
Create Date: 2026-09-17 13:27:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1d11b0d28c31"
down_revision: str | None = "2baa7d628f32"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Lists every AimbatSeismogramParametersBase field (flip, select, t1) so a
# no-op UPDATE (value unchanged) doesn't bump last_modified and cause a
# spurious TUI repaint. See core/_project.py::create_project() - this body
# must stay byte-for-byte (modulo whitespace) in sync with there, checked by
# tests/integration/core/test_migrations.py::test_same_triggers.

_EVENT_MODIFIED_ON_SEIS_PARAMS_UPDATE_NEW = """
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
"""

_EVENT_MODIFIED_ON_SEIS_PARAMS_UPDATE_OLD = """
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
"""


def upgrade() -> None:
    op.execute(sa.text("DROP TRIGGER IF EXISTS event_modified_on_seis_params_update"))
    op.execute(sa.text(_EVENT_MODIFIED_ON_SEIS_PARAMS_UPDATE_NEW))


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER IF EXISTS event_modified_on_seis_params_update"))
    op.execute(sa.text(_EVENT_MODIFIED_ON_SEIS_PARAMS_UPDATE_OLD))
