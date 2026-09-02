"""add per-parent unique index to aimbatnote

Revision ID: c7ba9d07fa0a
Revises: ca35a8b78a91
Create Date: 2026-09-02 02:29:35.785525+00:00

`AimbatNote` carries one note per parent record, but only the "exactly one
FK set" check constraint was enforced - nothing stopped a second row for the
same parent, in which case `save_note`/`get_note_content` would silently act
on an arbitrary one. Add a partial unique index per FK column so a duplicate
fails loudly at write time.

Plain ``CREATE INDEX ... WHERE`` is used rather than ``batch_alter_table``:
adding an index needs no table rebuild, and the batch rebuild would both
rename the table (which SQLite rejects while triggers elsewhere reference it)
and drop any triggers defined on ``aimbatnote``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7ba9d07fa0a"
down_revision: str | None = "ca35a8b78a91"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FK_COLUMNS = ("event_id", "station_id", "seismogram_id", "snapshot_id")


def upgrade() -> None:
    for column in _FK_COLUMNS:
        op.create_index(
            f"ix_aimbatnote_{column}",
            "aimbatnote",
            [column],
            unique=True,
            sqlite_where=sa.text(f"{column} IS NOT NULL"),
        )


def downgrade() -> None:
    for column in _FK_COLUMNS:
        op.drop_index(f"ix_aimbatnote_{column}", table_name="aimbatnote")
