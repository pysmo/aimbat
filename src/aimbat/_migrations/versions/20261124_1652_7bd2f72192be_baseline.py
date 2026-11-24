"""baseline

Revision ID: 7bd2f72192be
Revises:
Create Date: 2026-11-24 16:52:37.693892+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

import aimbat.types

# revision identifiers, used by Alembic.
revision: str = "7bd2f72192be"
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
        sa.UniqueConstraint(
            "network",
            "name",
            "location",
            "channel",
            name="uq_aimbatstation_network_name_location_channel",
        ),
    )
    op.create_table(
        "aimbatphase",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["aimbatevent.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "name", name="uq_aimbatphase_event_id_name"),
    )
    op.create_table(
        "aimbatseismogram",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "begin_time", aimbat.types.SAPandasTimestamp(timezone=True), nullable=False
        ),
        sa.Column("delta", aimbat.types.SAPandasTimedelta(), nullable=False),
        sa.Column("station_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["aimbatevent.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["station_id"], ["aimbatstation.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_id", "station_id", name="uq_aimbatseismogram_event_id_station_id"
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
    with op.batch_alter_table("aimbatdatasource", schema=None) as batch_op:
        batch_op.create_index(
            "ix_aimbatdatasource_seismogram_id", ["seismogram_id"], unique=True
        )

    op.create_table(
        "aimbatphaseparameters",
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
        sa.Column("phase_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["phase_id"], ["aimbatphase.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("aimbatphaseparameters", schema=None) as batch_op:
        batch_op.create_index(
            "ix_aimbatphaseparameters_phase_id", ["phase_id"], unique=True
        )

    op.create_table(
        "aimbatphasequality",
        sa.Column("mccc_rmse", aimbat.types.SAPandasTimedelta(), nullable=True),
        sa.Column("mccc_members", sa.JSON(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("phase_id", sa.Uuid(), nullable=False),
        sa.Column(
            "mccc_fingerprint", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.ForeignKeyConstraint(["phase_id"], ["aimbatphase.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("aimbatphasequality", schema=None) as batch_op:
        batch_op.create_index(
            "ix_aimbatphasequality_phase_id", ["phase_id"], unique=True
        )

    op.create_table(
        "aimbatpick",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "time", aimbat.types.SAPandasTimestamp(timezone=True), nullable=False
        ),
        sa.Column("label", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("phase_name", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("dismissed", sa.Boolean(), nullable=False),
        sa.Column(
            "origin", sa.Enum("SOURCE", "MANUAL", name="pickorigin"), nullable=False
        ),
        sa.Column("source_name", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "source_type",
            sa.Enum("SAC", "JSON_EVENT", "JSON_STATION", "MSEED", name="datatype"),
            nullable=True,
        ),
        sa.Column("source_key", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("target_network", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("target_station", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("target_location", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("target_channel", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "target_event_time",
            aimbat.types.SAPandasTimestamp(timezone=True),
            nullable=True,
        ),
        sa.Column("target_seismogram_id", sa.Uuid(), nullable=True),
        sa.Column("seismogram_id", sa.Uuid(), nullable=True),
        sa.Column("event_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "(origin = 'SOURCE') = (source_name IS NOT NULL AND source_key IS NOT NULL)",
            name="aimbat_pick_source_provenance",
        ),
        sa.CheckConstraint(
            "seismogram_id IS NULL OR event_id IS NULL",
            name="aimbat_pick_event_only_while_unmatched",
        ),
        sa.CheckConstraint(
            "target_seismogram_id IS NULL OR (target_network IS NULL AND target_station IS NULL AND target_location IS NULL AND target_channel IS NULL AND target_event_time IS NULL)",
            name="aimbat_pick_one_target_form",
        ),
        sa.ForeignKeyConstraint(["event_id"], ["aimbatevent.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["seismogram_id"], ["aimbatseismogram.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("aimbatpick", schema=None) as batch_op:
        batch_op.create_index(
            "ix_aimbatpick_event_id",
            ["event_id"],
            unique=False,
            sqlite_where=sa.text("event_id IS NOT NULL"),
        )
        batch_op.create_index(
            "ix_aimbatpick_seismogram_id", ["seismogram_id"], unique=False
        )
        batch_op.create_index(
            "ix_aimbatpick_source_name_source_key",
            ["source_name", "source_key"],
            unique=True,
            sqlite_where=sa.text("source_name IS NOT NULL"),
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
        sa.Column("phase_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["phase_id"], ["aimbatphase.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "phase_id", "sequence", name="uq_aimbatsnapshot_phase_id_sequence"
        ),
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
        "aimbatphaseparameterssnapshot",
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
            ["parameters_id"], ["aimbatphaseparameters.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["aimbatsnapshot.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "aimbatphasequalitysnapshot",
        sa.Column("mccc_rmse", aimbat.types.SAPandasTimedelta(), nullable=True),
        sa.Column("mccc_members", sa.JSON(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("phase_quality_id", sa.Uuid(), nullable=True),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["phase_quality_id"], ["aimbatphasequality.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["aimbatsnapshot.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "aimbatseismogramparameters",
        sa.Column("flip", sa.Boolean(), nullable=False),
        sa.Column("select", sa.Boolean(), nullable=False),
        sa.Column(
            "refined_pick", aimbat.types.SAPandasTimestamp(timezone=True), nullable=True
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("seismogram_id", sa.Uuid(), nullable=False),
        sa.Column("phase_id", sa.Uuid(), nullable=False),
        sa.Column("pick_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["phase_id"], ["aimbatphase.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pick_id"], ["aimbatpick.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["seismogram_id"], ["aimbatseismogram.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "seismogram_id",
            "phase_id",
            name="uq_aimbatseismogramparameters_seismogram_id_phase_id",
        ),
    )
    with op.batch_alter_table("aimbatseismogramparameters", schema=None) as batch_op:
        batch_op.create_index(
            "ix_aimbatseismogramparameters_phase_id", ["phase_id"], unique=False
        )
        batch_op.create_index(
            "ix_aimbatseismogramparameters_pick_id", ["pick_id"], unique=True
        )

    op.create_table(
        "aimbatseismogramparameterssnapshot",
        sa.Column("flip", sa.Boolean(), nullable=False),
        sa.Column("select", sa.Boolean(), nullable=False),
        sa.Column(
            "refined_pick", aimbat.types.SAPandasTimestamp(timezone=True), nullable=True
        ),
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
        "aimbatseismogramquality",
        sa.Column("iccs_cc", sa.Float(), nullable=True),
        sa.Column("mccc_cc_mean", sa.Float(), nullable=True),
        sa.Column("mccc_cc_std", sa.Float(), nullable=True),
        sa.Column("mccc_error", aimbat.types.SAPandasTimedelta(), nullable=True),
        sa.Column("mccc_refused", sa.Boolean(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("seismogram_parameters_id", sa.Uuid(), nullable=False),
        sa.Column(
            "iccs_fingerprint", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["seismogram_parameters_id"],
            ["aimbatseismogramparameters.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("aimbatseismogramquality", schema=None) as batch_op:
        batch_op.create_index(
            "ix_aimbatseismogramquality_seismogram_parameters_id",
            ["seismogram_parameters_id"],
            unique=True,
        )

    op.create_table(
        "aimbatseismogramqualitysnapshot",
        sa.Column("iccs_cc", sa.Float(), nullable=True),
        sa.Column("mccc_cc_mean", sa.Float(), nullable=True),
        sa.Column("mccc_cc_std", sa.Float(), nullable=True),
        sa.Column("mccc_error", aimbat.types.SAPandasTimedelta(), nullable=True),
        sa.Column("mccc_refused", sa.Boolean(), nullable=True),
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


def downgrade() -> None:
    op.drop_table("aimbatseismogramqualitysnapshot")
    with op.batch_alter_table("aimbatseismogramquality", schema=None) as batch_op:
        batch_op.drop_index("ix_aimbatseismogramquality_seismogram_parameters_id")

    op.drop_table("aimbatseismogramquality")
    op.drop_table("aimbatseismogramparameterssnapshot")
    with op.batch_alter_table("aimbatseismogramparameters", schema=None) as batch_op:
        batch_op.drop_index("ix_aimbatseismogramparameters_pick_id")
        batch_op.drop_index("ix_aimbatseismogramparameters_phase_id")

    op.drop_table("aimbatseismogramparameters")
    op.drop_table("aimbatphasequalitysnapshot")
    op.drop_table("aimbatphaseparameterssnapshot")
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
    op.drop_table("aimbatsnapshot")
    with op.batch_alter_table("aimbatpick", schema=None) as batch_op:
        batch_op.drop_index(
            "ix_aimbatpick_source_name_source_key",
            sqlite_where=sa.text("source_name IS NOT NULL"),
        )
        batch_op.drop_index("ix_aimbatpick_seismogram_id")
        batch_op.drop_index(
            "ix_aimbatpick_event_id", sqlite_where=sa.text("event_id IS NOT NULL")
        )

    op.drop_table("aimbatpick")
    with op.batch_alter_table("aimbatphasequality", schema=None) as batch_op:
        batch_op.drop_index("ix_aimbatphasequality_phase_id")

    op.drop_table("aimbatphasequality")
    with op.batch_alter_table("aimbatphaseparameters", schema=None) as batch_op:
        batch_op.drop_index("ix_aimbatphaseparameters_phase_id")

    op.drop_table("aimbatphaseparameters")
    with op.batch_alter_table("aimbatdatasource", schema=None) as batch_op:
        batch_op.drop_index("ix_aimbatdatasource_seismogram_id")

    op.drop_table("aimbatdatasource")
    op.drop_table("aimbatseismogram")
    op.drop_table("aimbatphase")
    op.drop_table("aimbatstation")
    op.drop_table("aimbatevent")
