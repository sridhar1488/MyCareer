"""Store personal profile photos."""

import sqlalchemy as sa
from alembic import op

revision = "profilephotos"
down_revision = "hrmsmaster"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_profile_photos",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("revision", sa.String(36), nullable=False),
        sa.Column("image", sa.LargeBinary(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("user_profile_photos")
