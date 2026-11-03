"""HR calibration gate and private appraisal attachments.

Revision ID: mycareer
Revises: hrformsimports
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "mycareer"
down_revision: str | None = "hrformsimports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "manager_submissions",
        sa.Column("appraisal_id", sa.String(36), primary_key=True),
        sa.Column("submitted_revision", sa.Integer(), nullable=False),
        sa.Column("employee_snapshot", sa.JSON(), nullable=False),
        sa.Column("evaluation", sa.JSON(), nullable=False),
        sa.Column("score", sa.JSON(), nullable=False),
        sa.Column("policy", sa.JSON(), nullable=False),
        sa.Column("submitted_by", sa.String(36), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["appraisal_id"], ["appraisals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_table(
        "hr_calibration_drafts",
        sa.Column("appraisal_id", sa.String(36), primary_key=True),
        sa.Column("evaluation", sa.JSON(), nullable=False),
        sa.Column("score", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.String(36), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["appraisal_id"], ["appraisals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_table(
        "hr_calibration_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("appraisal_id", sa.String(36), nullable=False),
        sa.Column("appraisal_version", sa.Integer(), nullable=False),
        sa.Column("evaluation", sa.JSON(), nullable=False),
        sa.Column("score", sa.JSON(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(2000), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["appraisal_id"], ["appraisals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_hr_calibration_events_appraisal_id", "hr_calibration_events", ["appraisal_id"])
    op.create_table(
        "appraisal_attachments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("appraisal_id", sa.String(36), nullable=False),
        sa.Column("uploader_id", sa.String(36), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("object_key", sa.String(80), nullable=False, unique=True),
        sa.Column("media_type", sa.String(100), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.Column("submitted_revision", sa.Integer(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["appraisal_id"], ["appraisals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["uploader_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_appraisal_attachments_appraisal_id", "appraisal_attachments", ["appraisal_id"])
    # Existing signed manager evaluations are treated as previously approved so that
    # this workflow change does not revoke releases or expose a mutable old result.
    op.execute("UPDATE appraisals SET state='HR_APPROVED' WHERE state='FINALIZED'")
    for table in ["manager_submissions", "hr_calibration_events"]:
        for operation in ["UPDATE", "DELETE"]:
            if op.get_bind().dialect.name == "mysql":
                op.execute(
                    f"CREATE TRIGGER {table}_no_{operation.lower()} BEFORE {operation} ON {table} FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Historical sign-off and calibration records are immutable'"
                )
            else:
                op.execute(
                    f"CREATE TRIGGER {table}_no_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'Historical sign-off and calibration records are immutable'); END"
                )


def downgrade() -> None:
    for table in ["manager_submissions", "hr_calibration_events"]:
        for operation in ["update", "delete"]:
            op.execute(f"DROP TRIGGER IF EXISTS {table}_no_{operation}")
    # Drop whole tables directly: on MySQL these child-column indexes are required
    # by their foreign keys and cannot be removed independently.
    op.drop_table("appraisal_attachments")
    op.drop_table("hr_calibration_events")
    op.drop_table("hr_calibration_drafts")
    op.drop_table("manager_submissions")
    op.execute("UPDATE appraisals SET state='FINALIZED' WHERE state='HR_APPROVED'")
