"""snapshot sequence: per-event counter replaces unique time

Revision ID: d52a54a8a665
Revises: d08f5f734f78
Create Date: 2026-09-02 11:51:49.489713+00:00

`AimbatSnapshot` identity moves from a globally-unique microsecond `time`
(back-to-back automatic snapshots could collide on it) to a monotonic
per-event `sequence`. `sequence` also gives `sync_from_matching_hash` and
the snapshot listings an unambiguous ordering.

The existing rows are numbered 1..N per event with a single-pass
``ROW_NUMBER()`` window, ordered by `time` (then `id` to break exact
ties). ``batch_alter_table`` is needed to make `sequence`
NOT NULL and to swap the single-column ``UNIQUE(time)`` for
``UNIQUE(event_id, sequence)``; a naming convention lets the unnamed
reflected constraint be dropped by name. `aimbatsnapshot` carries no
triggers.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d52a54a8a665"
down_revision: str | None = "d08f5f734f78"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NAMING_CONVENTION = {
    "uq": "uq_%(table_name)s_%(column_0_name)s",
}

_BACKFILL = """
    UPDATE aimbatsnapshot AS s
    SET sequence = n.seq
    FROM (
        SELECT id, ROW_NUMBER() OVER (
            PARTITION BY event_id ORDER BY time, id
        ) AS seq
        FROM aimbatsnapshot
    ) AS n
    WHERE n.id = s.id
"""


def upgrade() -> None:
    op.add_column("aimbatsnapshot", sa.Column("sequence", sa.Integer(), nullable=True))
    op.execute(_BACKFILL)

    with op.batch_alter_table(
        "aimbatsnapshot", schema=None, naming_convention=_NAMING_CONVENTION
    ) as batch_op:
        batch_op.alter_column("sequence", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_constraint("uq_aimbatsnapshot_time", type_="unique")
        batch_op.create_unique_constraint(
            "uq_aimbatsnapshot_event_id_sequence", ["event_id", "sequence"]
        )


def downgrade() -> None:
    # Restoring UNIQUE(time) fails if the project accumulated two snapshots in
    # the same microsecond - the exact case this migration exists to fix.
    # Downgrading such a project needs the colliding rows resolved by hand.
    with op.batch_alter_table(
        "aimbatsnapshot", schema=None, naming_convention=_NAMING_CONVENTION
    ) as batch_op:
        batch_op.drop_constraint("uq_aimbatsnapshot_event_id_sequence", type_="unique")
        batch_op.create_unique_constraint("uq_aimbatsnapshot_time", ["time"])
        batch_op.drop_column("sequence")
