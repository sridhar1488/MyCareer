"""HR form drafts, import previews and configurable text responses."""

import sqlalchemy as sa
from alembic import op

revision = "hrformsimports"
down_revision = "p5scoring"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("development_plans", sa.Column("extra_answers", sa.JSON(), nullable=True))
    op.create_table(
        "form_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "published_form_id",
            sa.String(36),
            sa.ForeignKey("appraisal_form_versions.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "user_import_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("rows", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table("user_import_batches")
    op.drop_table("form_templates")
    op.drop_column("development_plans", "extra_answers")
