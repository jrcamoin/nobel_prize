"""Add prospective validation workflow.

Revision ID: 20260728_0002
Revises: 20260727_0001
"""

import sqlalchemy as sa

from alembic import op

revision = "20260728_0002"
down_revision = "20260727_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidate_pools",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("model_run_id", sa.Integer(), sa.ForeignKey("model_runs.id"), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("screening_rules", sa.JSON(), nullable=False),
        sa.Column("locked_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "pool_candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "pool_id",
            sa.Integer(),
            sa.ForeignKey("candidate_pools.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("compound_id", sa.Integer(), sa.ForeignKey("compounds.id"), nullable=False),
        sa.Column("passed_screen", sa.Boolean(), nullable=False),
        sa.Column("rejection_reasons", sa.JSON(), nullable=False),
        sa.Column("properties", sa.JSON(), nullable=False),
        sa.Column("rank", sa.Integer()),
        sa.UniqueConstraint("pool_id", "compound_id"),
    )
    op.create_table(
        "preregistrations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "pool_id",
            sa.Integer(),
            sa.ForeignKey("candidate_pools.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("report_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("signature", sa.String(64), nullable=False),
        sa.Column("signed_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_type", sa.String(80), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON()),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("finished_at", sa.DateTime()),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"])
    with op.batch_alter_table("experiments") as batch:
        batch.add_column(sa.Column("preregistration_id", sa.Integer()))
        batch.create_foreign_key(
            "fk_experiments_preregistration_id",
            "preregistrations",
            ["preregistration_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("experiments") as batch:
        batch.drop_constraint("fk_experiments_preregistration_id", type_="foreignkey")
        batch.drop_column("preregistration_id")
    op.drop_table("jobs")
    op.drop_table("preregistrations")
    op.drop_table("pool_candidates")
    op.drop_table("candidate_pools")
