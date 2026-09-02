"""exclude completed from event modified trigger

Revision ID: 86cb8889cd87
Revises: 72c6b97febca
Create Date: 2026-08-26 16:27:06.180392+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "86cb8889cd87"
down_revision: str | None = "72c6b97febca"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# `completed` is bookkeeping with no effect on ICCS/MCCC processing (it is
# likewise excluded from the snapshot parameter hashes in
# core/_snapshot.py) - this WHEN clause lists every other event parameter.
# See core/_project.py::create_project() - this body must stay byte-for-byte
# (modulo whitespace) in sync with there, checked by
# tests/integration/core/test_migrations.py::test_same_triggers.

_EVENT_MODIFIED_ON_PARAMS_UPDATE_NEW = """
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
"""

_EVENT_MODIFIED_ON_PARAMS_UPDATE_OLD = """
    CREATE TRIGGER IF NOT EXISTS event_modified_on_params_update
    AFTER UPDATE ON aimbateventparameters
    BEGIN
        UPDATE aimbatevent SET last_modified = strftime('%Y-%m-%d %H:%M:%f', 'now')
        WHERE id = NEW.event_id;
    END;
"""


def upgrade() -> None:
    op.execute(sa.text("DROP TRIGGER IF EXISTS event_modified_on_params_update"))
    op.execute(sa.text(_EVENT_MODIFIED_ON_PARAMS_UPDATE_NEW))


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER IF EXISTS event_modified_on_params_update"))
    op.execute(sa.text(_EVENT_MODIFIED_ON_PARAMS_UPDATE_OLD))
