"""Local operator commands. Never invoked automatically during API startup."""

import argparse
import getpass
from urllib.parse import quote

from pydantic import EmailStr, TypeAdapter
from sqlalchemy import select, text

from app.core.config import Settings
from app.core.security import hasher
from app.db.session import make_engine, session_factory
from app.modules.audit.models import AuditEvent
from app.modules.auth.models import Credential
from app.modules.auth.service import issue_reset
from app.modules.users.models import Role, RoleCode, User, UserRole


def main():
    parser = argparse.ArgumentParser(description="MyCareer local account operator")
    commands = parser.add_subparsers(dest="command", required=True)
    bootstrap = commands.add_parser(
        "bootstrap-admin", help="Create the first admin only; password prompted securely"
    )
    bootstrap.add_argument("--email", required=True)
    bootstrap.add_argument("--employee-id", required=True)
    bootstrap.add_argument("--name", required=True)
    reset = commands.add_parser("issue-reset", help="Issue a one-use reset link for secure manual handoff")
    reset.add_argument("--email", required=True)
    args = parser.parse_args()
    settings = Settings()
    engine = make_engine(settings)
    email = str(TypeAdapter(EmailStr).validate_python(args.email)).lower()
    with session_factory(engine)() as db:
        if args.command == "bootstrap-admin":
            if (
                not args.name.strip()
                or len(args.name) > 150
                or not args.employee_id.strip()
                or len(args.employee_id) > 40
            ):
                parser.error("Name and employee ID must be non-empty and within documented length limits")
            password = getpass.getpass("Initial temporary password (8–15 characters): ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm or not 8 <= len(password) <= 15:
                parser.error("Passwords must match and contain 8–15 characters")
            # Serialize the one-time bootstrap across operators. Guard row is seeded by migration.
            db.execute(
                text(
                    "SELECT id FROM operator_guard WHERE id=1"
                    + (" FOR UPDATE" if engine.dialect.name == "mysql" else "")
                )
            )
            if db.scalar(select(User.id).limit(1)):
                parser.error("Bootstrap is disabled once any account exists")
            for role in RoleCode:
                if not db.get(Role, role.value):
                    db.add(Role(code=role.value))
            db.flush()
            user = User(employee_id=args.employee_id.strip(), email=email, full_name=args.name.strip())
            db.add(user)
            db.flush()
            db.add(UserRole(user_id=user.id, role_code=RoleCode.SUPER_ADMIN.value))
            db.add(
                Credential(user_id=user.id, password_hash=hasher.hash(password), must_change_password=True)
            )
            db.add(
                AuditEvent(
                    action="admin.bootstrapped", resource_id=user.id, details={"channel": "local_operator"}
                )
            )
            db.commit()
            print("Initial administrator created. Password change is required on first sign-in.")
        else:
            user = db.scalar(select(User).where(User.email == email))
            if not user:
                parser.error("Account not found")
            token = issue_reset(db, settings, user)
            print(
                "One-use reset link. Hand it directly to the account owner through your approved secure channel."
            )
            print(f"{settings.allowed_origins[0]}/#reset={quote(token)}")
            print(f"Expires in {settings.reset_minutes} minutes. Existing sessions have been revoked.")
    engine.dispose()


if __name__ == "__main__":
    main()
