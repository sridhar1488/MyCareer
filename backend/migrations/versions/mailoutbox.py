"""Transactional mail notification outbox.

Revision ID: mailoutbox
Revises: mycareer
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "mailoutbox"
down_revision: str | None = "mycareer"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_outbox",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("recipients", sa.JSON(), nullable=False),
        sa.Column("subject", sa.String(250), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime()),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(500)),
    )
    op.create_index("ix_notification_outbox_available_at", "notification_outbox", ["available_at"])


def downgrade() -> None:
    op.drop_index("ix_notification_outbox_available_at", table_name="notification_outbox")
    op.drop_table("notification_outbox")
