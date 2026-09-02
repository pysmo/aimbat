"""drop unused extra column from aimbatseismogram

Revision ID: ca35a8b78a91
Revises: 86cb8889cd87
Create Date: 2026-09-01 22:52:18.015917+00:00

The `extra` column was a never-used, `PickleType`-backed metadata bag on
`aimbatseismogram`. Nothing in AIMBAT ever wrote to or read from it, so any
value it holds (only reachable by poking the ORM directly) is dropped here
rather than converted - a pickle blob cannot be safely deserialised in a
migration, which is the whole reason for removing it.

A plain ``ALTER TABLE ... DROP COLUMN`` is used rather than
``batch_alter_table``: `extra` is not part of any index, constraint, or
trigger body, so SQLite (>= 3.35) can drop it in place. The batch rebuild
would instead rename the table, which SQLite rejects here because six of the
quality-invalidation triggers reference `aimbatseismogram` in their bodies
and are transiently dangling mid-rebuild.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ca35a8b78a91"
down_revision: str | None = "86cb8889cd87"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("aimbatseismogram", "extra")


def downgrade() -> None:
    op.add_column(
        "aimbatseismogram",
        sa.Column("extra", sa.PickleType(), nullable=True),
    )
