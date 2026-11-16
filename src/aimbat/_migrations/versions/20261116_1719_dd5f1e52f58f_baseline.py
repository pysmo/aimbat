"""baseline

Revision ID: dd5f1e52f58f
Revises:
Create Date: 2026-11-16 17:19:53.164145+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

import aimbat.types

# revision identifiers, used by Alembic.
revision: str = "dd5f1e52f58f"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "aimbatevent",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "time", aimbat.types.SAPandasTimestamp(timezone=True), nullable=False
        ),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("depth", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("time"),
    )
    op.create_table(
        "aimbatstation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("network", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("location", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("channel", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("elevation", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "aimbateventparameters",
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("ramp_width", sa.Float(), nullable=False),
        sa.Column("window_pre", aimbat.types.SAPandasTimedelta(), nullable=False),
        sa.Column("window_post", aimbat.types.SAPandasTimedelta(), nullable=False),
        sa.Column("bandpass_apply", sa.Boolean(), nullable=False),
        sa.Column("bandpass_fmin", sa.Float(), nullable=False),
        sa.Column("bandpass_fmax", sa.Float(), nullable=False),
        sa.Column("corners", sa.Integer(), server_default="2", nullable=False),
        sa.Column("min_cc", sa.Float(), nullable=False),
        sa.Column("mccc_damp", sa.Float(), nullable=False),
        sa.Column("mccc_min_cc", sa.Float(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["aimbatevent.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("aimbateventparameters", schema=None) as batch_op:
        batch_op.create_index(
            "ix_aimbateventparameters_event_id", ["event_id"], unique=True
        )

    op.create_table(
        "aimbateventquality",
        sa.Column("mccc_rmse", aimbat.types.SAPandasTimedelta(), nullable=True),
        sa.Column("mccc_members", sa.JSON(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column(
            "mccc_fingerprint", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.ForeignKeyConstraint(["event_id"], ["aimbatevent.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("aimbateventquality", schema=None) as batch_op:
        batch_op.create_index(
            "ix_aimbateventquality_event_id", ["event_id"], unique=True
        )

    op.create_table(
        "aimbatseismogram",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "begin_time", aimbat.types.SAPandasTimestamp(timezone=True), nullable=False
        ),
        sa.Column("delta", aimbat.types.SAPandasTimedelta(), nullable=False),
        sa.Column("t0", aimbat.types.SAPandasTimestamp(timezone=True), nullable=False),
        sa.Column("station_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["aimbatevent.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["station_id"], ["aimbatstation.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("aimbatseismogram", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_aimbatseismogram_event_id"), ["event_id"], unique=False
        )

    op.create_table(
        "aimbatsnapshot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "time", aimbat.types.SAPandasTimestamp(timezone=True), nullable=False
        ),
        sa.Column("comment", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("automatic", sa.Boolean(), nullable=False),
        sa.Column("mccc_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("iccs_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["aimbatevent.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_id", "sequence", name="uq_aimbatsnapshot_event_id_sequence"
        ),
    )
    op.create_table(
        "aimbatdatasource",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sourcename", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "datatype",
            sa.Enum("SAC", "JSON_EVENT", "JSON_STATION", "MSEED", name="datatype"),
            nullable=False,
        ),
        sa.Column("seismogram_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["seismogram_id"], ["aimbatseismogram.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sourcename", name="uq_aimbatdatasource_sourcename"),
    )
    op.create_table(
        "aimbateventparameterssnapshot",
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("ramp_width", sa.Float(), nullable=False),
        sa.Column("window_pre", aimbat.types.SAPandasTimedelta(), nullable=False),
        sa.Column("window_post", aimbat.types.SAPandasTimedelta(), nullable=False),
        sa.Column("bandpass_apply", sa.Boolean(), nullable=False),
        sa.Column("bandpass_fmin", sa.Float(), nullable=False),
        sa.Column("bandpass_fmax", sa.Float(), nullable=False),
        sa.Column("corners", sa.Integer(), server_default="2", nullable=False),
        sa.Column("min_cc", sa.Float(), nullable=False),
        sa.Column("mccc_damp", sa.Float(), nullable=False),
        sa.Column("mccc_min_cc", sa.Float(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("parameters_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["parameters_id"], ["aimbateventparameters.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["aimbatsnapshot.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "aimbateventqualitysnapshot",
        sa.Column("mccc_rmse", aimbat.types.SAPandasTimedelta(), nullable=True),
        sa.Column("mccc_members", sa.JSON(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_quality_id", sa.Uuid(), nullable=True),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_quality_id"], ["aimbateventquality.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["aimbatsnapshot.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "aimbatnote",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=True),
        sa.Column("station_id", sa.Uuid(), nullable=True),
        sa.Column("seismogram_id", sa.Uuid(), nullable=True),
        sa.Column("snapshot_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "(CASE WHEN event_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN station_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN seismogram_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN snapshot_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="aimbat_note_exactly_one_parent",
        ),
        sa.ForeignKeyConstraint(["event_id"], ["aimbatevent.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["seismogram_id"], ["aimbatseismogram.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["aimbatsnapshot.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["station_id"], ["aimbatstation.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("aimbatnote", schema=None) as batch_op:
        batch_op.create_index(
            "ix_aimbatnote_event_id",
            ["event_id"],
            unique=True,
            sqlite_where=sa.text("event_id IS NOT NULL"),
        )
        batch_op.create_index(
            "ix_aimbatnote_seismogram_id",
            ["seismogram_id"],
            unique=True,
            sqlite_where=sa.text("seismogram_id IS NOT NULL"),
        )
        batch_op.create_index(
            "ix_aimbatnote_snapshot_id",
            ["snapshot_id"],
            unique=True,
            sqlite_where=sa.text("snapshot_id IS NOT NULL"),
        )
        batch_op.create_index(
            "ix_aimbatnote_station_id",
            ["station_id"],
            unique=True,
            sqlite_where=sa.text("station_id IS NOT NULL"),
        )

    op.create_table(
        "aimbatseismogramparameters",
        sa.Column("flip", sa.Boolean(), nullable=False),
        sa.Column("select", sa.Boolean(), nullable=False),
        sa.Column("t1", aimbat.types.SAPandasTimestamp(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("seismogram_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["seismogram_id"], ["aimbatseismogram.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("aimbatseismogramparameters", schema=None) as batch_op:
        batch_op.create_index(
            "ix_aimbatseismogramparameters_seismogram_id",
            ["seismogram_id"],
            unique=True,
        )

    op.create_table(
        "aimbatseismogramquality",
        sa.Column("iccs_cc", sa.Float(), nullable=True),
        sa.Column("mccc_cc_mean", sa.Float(), nullable=True),
        sa.Column("mccc_cc_std", sa.Float(), nullable=True),
        sa.Column("mccc_error", aimbat.types.SAPandasTimedelta(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("seismogram_id", sa.Uuid(), nullable=False),
        sa.Column(
            "iccs_fingerprint", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["seismogram_id"], ["aimbatseismogram.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("aimbatseismogramquality", schema=None) as batch_op:
        batch_op.create_index(
            "ix_aimbatseismogramquality_seismogram_id", ["seismogram_id"], unique=True
        )

    op.create_table(
        "aimbatseismogramparameterssnapshot",
        sa.Column("flip", sa.Boolean(), nullable=False),
        sa.Column("select", sa.Boolean(), nullable=False),
        sa.Column("t1", aimbat.types.SAPandasTimestamp(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("seismogram_id", sa.Uuid(), nullable=True),
        sa.Column("seismogram_parameters_id", sa.Uuid(), nullable=True),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["seismogram_parameters_id"],
            ["aimbatseismogramparameters.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["aimbatsnapshot.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "aimbatseismogramqualitysnapshot",
        sa.Column("iccs_cc", sa.Float(), nullable=True),
        sa.Column("mccc_cc_mean", sa.Float(), nullable=True),
        sa.Column("mccc_cc_std", sa.Float(), nullable=True),
        sa.Column("mccc_error", aimbat.types.SAPandasTimedelta(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("seismogram_id", sa.Uuid(), nullable=True),
        sa.Column("seismogram_quality_id", sa.Uuid(), nullable=True),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["seismogram_quality_id"],
            ["aimbatseismogramquality.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["aimbatsnapshot.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("aimbatseismogramqualitysnapshot")
    op.drop_table("aimbatseismogramparameterssnapshot")
    with op.batch_alter_table("aimbatseismogramquality", schema=None) as batch_op:
        batch_op.drop_index("ix_aimbatseismogramquality_seismogram_id")

    op.drop_table("aimbatseismogramquality")
    with op.batch_alter_table("aimbatseismogramparameters", schema=None) as batch_op:
        batch_op.drop_index("ix_aimbatseismogramparameters_seismogram_id")

    op.drop_table("aimbatseismogramparameters")
    with op.batch_alter_table("aimbatnote", schema=None) as batch_op:
        batch_op.drop_index(
            "ix_aimbatnote_station_id", sqlite_where=sa.text("station_id IS NOT NULL")
        )
        batch_op.drop_index(
            "ix_aimbatnote_snapshot_id", sqlite_where=sa.text("snapshot_id IS NOT NULL")
        )
        batch_op.drop_index(
            "ix_aimbatnote_seismogram_id",
            sqlite_where=sa.text("seismogram_id IS NOT NULL"),
        )
        batch_op.drop_index(
            "ix_aimbatnote_event_id", sqlite_where=sa.text("event_id IS NOT NULL")
        )

    op.drop_table("aimbatnote")
    op.drop_table("aimbateventqualitysnapshot")
    op.drop_table("aimbateventparameterssnapshot")
    op.drop_table("aimbatdatasource")
    op.drop_table("aimbatsnapshot")
    with op.batch_alter_table("aimbatseismogram", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_aimbatseismogram_event_id"))

    op.drop_table("aimbatseismogram")
    with op.batch_alter_table("aimbateventquality", schema=None) as batch_op:
        batch_op.drop_index("ix_aimbateventquality_event_id")

    op.drop_table("aimbateventquality")
    with op.batch_alter_table("aimbateventparameters", schema=None) as batch_op:
        batch_op.drop_index("ix_aimbateventparameters_event_id")

    op.drop_table("aimbateventparameters")
    op.drop_table("aimbatstation")
    op.drop_table("aimbatevent")
