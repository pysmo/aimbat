"""split snapshot parameters_hash into mccc_hash and iccs_hash

Revision ID: 490f0a998ee3
Revises: c7ba9d07fa0a
Create Date: 2026-09-02 10:05:49.642991+00:00

`AimbatSnapshot` now carries two hashes instead of one: `mccc_hash`
identifies the MCCC inversion the frozen diagnostics belong to, `iccs_hash`
identifies the ICCS stack the frozen `iccs_cc` values were measured against.

The old `parameters_hash` is renamed to `mccc_hash`. Its stored values are
*not* recomputed: the old hash also folded in `min_cc`, which `mccc_hash`
excludes, so a pre-existing snapshot will no longer match the live MCCC hash
and its MCCC quality simply will not be reused (the quality-invalidation
triggers still clear it safely). `iccs_hash` is left NULL on pre-existing
snapshots for the same reason - they never repopulate `iccs_cc` after a
revert, which matches the previous, frequently-broken behaviour.

Native `ALTER TABLE ... RENAME COLUMN` / `ADD COLUMN` / `DROP COLUMN` are
used rather than ``batch_alter_table``: no column needs retyping and the
batch rebuild would needlessly recreate a table that four FK tables point at.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "490f0a998ee3"
down_revision: str | None = "c7ba9d07fa0a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE aimbatsnapshot RENAME COLUMN parameters_hash TO mccc_hash")
    op.add_column("aimbatsnapshot", sa.Column("iccs_hash", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("aimbatsnapshot", "iccs_hash")
    op.execute("ALTER TABLE aimbatsnapshot RENAME COLUMN mccc_hash TO parameters_hash")
