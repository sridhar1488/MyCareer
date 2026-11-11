"""Store per-cycle reminder settings and scheduled sends."""

import sqlalchemy as sa
from alembic import op

revision = "cyclereminders"
down_revision = "profilephotos"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "cycle_reminder_settings",
        sa.Column(
            "cycle_id",
            sa.String(36),
            sa.ForeignKey("appraisal_cycles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("manager_deadline", sa.DateTime()),
        sa.Column("hr_deadline", sa.DateTime()),
        sa.Column("hours_before", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_table(
        "scheduled_cycle_reminders",
        sa.Column(
            "cycle_id",
            sa.String(36),
            sa.ForeignKey("appraisal_cycles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("stage", sa.String(12), primary_key=True),
        sa.Column("deadline", sa.DateTime(), primary_key=True),
        sa.Column("hours_before", sa.Integer(), primary_key=True),
    )


def downgrade():
    op.drop_table("scheduled_cycle_reminders")
    op.drop_table("cycle_reminder_settings")
