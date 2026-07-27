"""Add candidate qualification and laboratory protocols.

Revision ID: 20260729_0003
Revises: 20260728_0002
"""

import sqlalchemy as sa

from alembic import op

revision = "20260729_0003"
down_revision = "20260728_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("pool_candidates") as batch:
        batch.add_column(sa.Column("selected", sa.Boolean(), nullable=False, server_default="0"))
        batch.add_column(
            sa.Column(
                "availability_status", sa.String(40), nullable=False, server_default="unverified"
            )
        )
        batch.add_column(sa.Column("vendor", sa.String(160)))
        batch.add_column(sa.Column("catalog_number", sa.String(120)))
        batch.add_column(sa.Column("price", sa.Float()))
        batch.add_column(sa.Column("purity", sa.Float()))
    op.create_table(
        "laboratory_protocols",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "pool_id",
            sa.Integer(),
            sa.ForeignKey("candidate_pools.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("organism", sa.String(160), nullable=False),
        sa.Column("strain", sa.String(160), nullable=False),
        sa.Column("method", sa.String(120), nullable=False),
        sa.Column("medium", sa.String(120), nullable=False),
        sa.Column("concentration_min", sa.Float(), nullable=False),
        sa.Column("concentration_max", sa.Float(), nullable=False),
        sa.Column("concentration_unit", sa.String(40), nullable=False),
        sa.Column("replicates", sa.Integer(), nullable=False),
        sa.Column("positive_control", sa.String(160), nullable=False),
        sa.Column("negative_control", sa.String(160), nullable=False),
        sa.Column("blinded", sa.Boolean(), nullable=False),
        sa.Column("success_criterion", sa.Text(), nullable=False),
        sa.Column("laboratory", sa.String(200), nullable=False),
        sa.Column("protocol_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("laboratory_protocols")
    with op.batch_alter_table("pool_candidates") as batch:
        for column in (
            "purity",
            "price",
            "catalog_number",
            "vendor",
            "availability_status",
            "selected",
        ):
            batch.drop_column(column)
