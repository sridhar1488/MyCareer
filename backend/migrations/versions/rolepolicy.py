"""Keep employee and Super Admin roles separate.

Revision ID: rolepolicy
Revises: mailoutbox
"""

from collections.abc import Sequence

from alembic import op

revision: str = "rolepolicy"
down_revision: str | None = "mailoutbox"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The employee role is not required to complete an employee's own appraisal.
    # Preserve Super Admin access while removing the invalid combined assignment.
    op.execute(
        "DELETE FROM user_roles WHERE role_code='EMPLOYEE' AND user_id IN "
        "(SELECT user_id FROM (SELECT user_id FROM user_roles WHERE role_code='SUPER_ADMIN') AS admins)"
    )


def downgrade() -> None:
    # Restore the former combination for Super Admin users when rolling back.
    op.execute(
        "INSERT INTO user_roles (user_id, role_code) "
        "SELECT admins.user_id, 'EMPLOYEE' FROM user_roles AS admins "
        "WHERE admins.role_code='SUPER_ADMIN' AND NOT EXISTS "
        "(SELECT 1 FROM user_roles AS employees WHERE employees.user_id=admins.user_id "
        "AND employees.role_code='EMPLOYEE')"
    )
