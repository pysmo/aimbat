"""unique index on 1:1 parameters and quality links

Revision ID: 4386151d11e2
Revises: d52a54a8a665
Create Date: 2026-09-02 17:51:51.909907+00:00

`AimbatSeismogramParameters` / `AimbatSeismogramQuality` are one row per
seismogram, and `AimbatEventParameters` / `AimbatEventQuality` are one row
per event - the ORM relationships are scalar - but nothing enforced it.
A stray second row would be picked arbitrarily by helpers that build a
`{parent_id: row}` map (e.g. `_snapshot._live_seismogram_quality_map`),
silently yielding inconsistent reads. Add a unique index on each link
column so a duplicate fails loudly at write time.

Plain ``CREATE UNIQUE INDEX`` is used rather than ``batch_alter_table``:
adding an index needs no table rebuild, and the batch rebuild would drop
every trigger defined on these tables (triggers 1/3/4 on
``aimbateventparameters``, 2/5a-c on ``aimbatseismogramparameters``).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4386151d11e2"
down_revision: str | None = "d52a54a8a665"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, link column) - the index is named ix_<table>_<column>.
_UNIQUE_LINKS = (
    ("aimbatseismogramparameters", "seismogram_id"),
    ("aimbatseismogramquality", "seismogram_id"),
    ("aimbateventparameters", "event_id"),
    ("aimbateventquality", "event_id"),
)


def _reject_existing_duplicates() -> None:
    """Fail with a clear message if a link column already has duplicate rows.

    `CREATE UNIQUE INDEX` on a table that already violates the constraint
    raises an opaque "UNIQUE constraint failed" with no indication of which
    rows are at fault - surface the offending parents instead.
    """
    bind = op.get_bind()
    for table, column in _UNIQUE_LINKS:
        rows = bind.execute(
            sa.text(
                f"SELECT {column} FROM {table} GROUP BY {column} HAVING COUNT(*) > 1"
            )
        ).fetchall()
        if rows:
            offenders = ", ".join(str(row[0]) for row in rows)
            raise RuntimeError(
                f"{table} has more than one row for the same {column} "
                f"({offenders}). Delete the duplicate rows, keeping one per "
                f"parent, then re-run `aimbat db upgrade`."
            )


def upgrade() -> None:
    _reject_existing_duplicates()
    for table, column in _UNIQUE_LINKS:
        op.create_index(f"ix_{table}_{column}", table, [column], unique=True)


def downgrade() -> None:
    for table, column in _UNIQUE_LINKS:
        op.drop_index(f"ix_{table}_{column}", table_name=table)
