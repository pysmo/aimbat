"""add unique constraint to datasource sourcename

Revision ID: 72c6b97febca
Revises: ffa5c8fcbe9b
Create Date: 2026-08-26 15:06:44.501155+00:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "72c6b97febca"
down_revision: str | None = "ffa5c8fcbe9b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("aimbatdatasource", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_aimbatdatasource_sourcename", ["sourcename"]
        )


def downgrade() -> None:
    with op.batch_alter_table("aimbatdatasource", schema=None) as batch_op:
        batch_op.drop_constraint("uq_aimbatdatasource_sourcename", type_="unique")
