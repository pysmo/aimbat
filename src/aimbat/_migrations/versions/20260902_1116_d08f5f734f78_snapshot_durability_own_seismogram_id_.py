"""snapshot durability: own seismogram_id, SET NULL on live FKs

Revision ID: d08f5f734f78
Revises: 490f0a998ee3
Create Date: 2026-09-02 11:16:40.466105+00:00

Snapshots are frozen history and must survive deletion of the live rows they
were taken from.

- The two seismogram snapshot tables gain their own ``seismogram_id`` column,
  backfilled from the live parameter/quality row they point at, so a snapshot
  still resolves to a seismogram after that live row is gone.
- All four snapshot -> live foreign keys switch from ``ON DELETE CASCADE`` to
  ``ON DELETE SET NULL`` and become nullable. Deleting a seismogram (or its
  parameter/quality rows) now nulls the reference instead of destroying the
  frozen record. The event stays reachable via ``aimbatsnapshot.event_id``.

The snapshot -> parent ``aimbatsnapshot`` FKs keep ``ON DELETE CASCADE`` -
deleting a whole snapshot still removes its frozen rows.

``batch_alter_table`` is required (SQLite cannot alter a constraint in place).
None of these four tables carry triggers, and the quality-invalidation
triggers reference only the live tables, so the rebuilds are safe. A local
naming convention is used so the unnamed reflected FKs can be dropped by name.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d08f5f734f78"
down_revision: str | None = "490f0a998ee3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}

# (snapshot table, FK column, referred table)
_LIVE_FKS = [
    (
        "aimbateventparameterssnapshot",
        "parameters_id",
        "aimbateventparameters",
    ),
    (
        "aimbateventqualitysnapshot",
        "event_quality_id",
        "aimbateventquality",
    ),
    (
        "aimbatseismogramparameterssnapshot",
        "seismogram_parameters_id",
        "aimbatseismogramparameters",
    ),
    (
        "aimbatseismogramqualitysnapshot",
        "seismogram_quality_id",
        "aimbatseismogramquality",
    ),
]


def _rewrite_fk(
    table: str, column: str, referred: str, *, ondelete: str, nullable: bool
) -> None:
    fk_name = f"fk_{table}_{column}_{referred}"
    with op.batch_alter_table(
        table, schema=None, naming_convention=_NAMING_CONVENTION
    ) as batch_op:
        batch_op.alter_column(column, existing_type=sa.Uuid(), nullable=nullable)
        batch_op.drop_constraint(fk_name, type_="foreignkey")
        batch_op.create_foreign_key(
            fk_name, referred, [column], ["id"], ondelete=ondelete
        )


def upgrade() -> None:
    for table in (
        "aimbatseismogramparameterssnapshot",
        "aimbatseismogramqualitysnapshot",
    ):
        op.add_column(table, sa.Column("seismogram_id", sa.Uuid(), nullable=True))

    for table, column, referred in _LIVE_FKS:
        _rewrite_fk(table, column, referred, ondelete="SET NULL", nullable=True)

    op.execute(
        "UPDATE aimbatseismogramparameterssnapshot SET seismogram_id = ("
        "  SELECT p.seismogram_id FROM aimbatseismogramparameters p"
        "  WHERE p.id = aimbatseismogramparameterssnapshot.seismogram_parameters_id"
        ") WHERE seismogram_parameters_id IS NOT NULL"
    )
    op.execute(
        "UPDATE aimbatseismogramqualitysnapshot SET seismogram_id = ("
        "  SELECT q.seismogram_id FROM aimbatseismogramquality q"
        "  WHERE q.id = aimbatseismogramqualitysnapshot.seismogram_quality_id"
        ") WHERE seismogram_quality_id IS NOT NULL"
    )


def downgrade() -> None:
    # The old schema had these FKs NOT NULL with ON DELETE CASCADE, so a
    # snapshot row whose live counterpart is gone could not exist - drop any
    # that SET NULL has since orphaned before restoring the constraint.
    for table, column, _referred in _LIVE_FKS:
        op.execute(f"DELETE FROM {table} WHERE {column} IS NULL")

    for table, column, referred in _LIVE_FKS:
        _rewrite_fk(table, column, referred, ondelete="CASCADE", nullable=False)

    for table in (
        "aimbatseismogramparameterssnapshot",
        "aimbatseismogramqualitysnapshot",
    ):
        op.drop_column(table, "seismogram_id")
