"""Create scientific provenance schema.

Revision ID: 20260727_0001
"""

import sqlalchemy as sa

from alembic import op

revision = "20260727_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("version", sa.String(80), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("license", sa.String(120), nullable=False),
        sa.Column("query", sa.JSON(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("imported_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_datasets_name", "datasets", ["name"])
    op.create_table(
        "compounds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("source_id", sa.String(80)),
        sa.Column("smiles", sa.Text(), nullable=False),
        sa.Column("canonical_smiles", sa.Text(), nullable=False, unique=True),
        sa.Column("inchikey", sa.String(27), nullable=False, unique=True),
        sa.Column("scaffold_smiles", sa.Text(), nullable=False),
        sa.Column("molecular_weight", sa.Float(), nullable=False),
        sa.Column("target_pathogen", sa.String(160), nullable=False),
        sa.Column("activity_score", sa.Float()),
        sa.Column("confidence", sa.Float()),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("evidence_source", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    for name in ("name", "source_id", "target_pathogen"):
        op.create_index(f"ix_compounds_{name}", "compounds", [name])
    op.create_index("ix_compounds_inchikey", "compounds", ["inchikey"], unique=True)
    op.create_table(
        "assays",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "dataset_id",
            sa.Integer(),
            sa.ForeignKey("datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(80), nullable=False),
        sa.Column("organism", sa.String(160), nullable=False),
        sa.Column("assay_type", sa.String(40)),
        sa.Column("description", sa.Text()),
        sa.UniqueConstraint("dataset_id", "external_id"),
    )
    op.create_index("ix_assays_organism", "assays", ["organism"])
    op.create_table(
        "measurements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "compound_id",
            sa.Integer(),
            sa.ForeignKey("compounds.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assay_id", sa.Integer(), sa.ForeignKey("assays.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("standard_type", sa.String(40), nullable=False),
        sa.Column("relation", sa.String(8)),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("units", sa.String(40), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("assay_id", "compound_id", "standard_type", "value"),
    )
    op.create_table(
        "model_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("algorithm", sa.String(120), nullable=False),
        sa.Column("split_strategy", sa.String(80), nullable=False),
        sa.Column("random_seed", sa.Integer(), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("artifact_sha256", sa.String(64)),
        sa.Column("git_commit", sa.String(40)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "compound_id",
            sa.Integer(),
            sa.ForeignKey("compounds.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "model_run_id",
            sa.Integer(),
            sa.ForeignKey("model_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("activity_probability", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("uncertainty", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("model_run_id", "compound_id"),
    )
    op.create_table(
        "experiments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("compound_id", sa.Integer(), sa.ForeignKey("compounds.id"), nullable=False),
        sa.Column("protocol_uri", sa.Text(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("result", sa.JSON()),
        sa.Column("performed_by", sa.String(160)),
        sa.Column("performed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    for table in (
        "experiments",
        "predictions",
        "model_runs",
        "measurements",
        "assays",
        "compounds",
        "datasets",
    ):
        op.drop_table(table)
