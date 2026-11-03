"""Persist HRMS location and date joined on user profiles."""

import sqlalchemy as sa
from alembic import op

revision = "hrmsmaster"
down_revision = "rolepolicy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("location", sa.String(length=120), server_default="", nullable=False),
    )
    op.add_column("users", sa.Column("date_joined", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "date_joined")
    op.drop_column("users", "location")
