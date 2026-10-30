"""Test-only accounts for browser workflows. Refuses every non-E2E database."""

import os
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.core.security import hasher, token_hash
from app.db.base import utcnow
from app.db.session import make_engine, session_factory
from app.modules.auth.models import Credential, PasswordToken
from app.modules.users.models import RoleCode, User, UserRole

settings = Settings()
database = make_url(settings.database_url.get_secret_value()).database or ""
if settings.environment != "test" or not database.endswith("_e2e_test"):
    raise RuntimeError("E2E seeding is allowed only in test mode in a database ending _e2e_test")
password = os.environ["MI_E2E_PASSWORD"]
engine = make_engine(settings)
with session_factory(engine).begin() as db:
    for name, role, temporary in [
        ("employee", RoleCode.EMPLOYEE, False),
        ("manager", RoleCode.MANAGER, False),
        ("hr", RoleCode.SUPER_ADMIN, False),
        ("admin", RoleCode.SUPER_ADMIN, False),
        ("temporary", RoleCode.EMPLOYEE, True),
        ("reset", RoleCode.EMPLOYEE, False),
    ]:
        email = f"{name}.e2e@example.org"
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            user = User(
                employee_id=f"E2E-{name}",
                email=email,
                full_name=f"Test {name.title()}",
                department="Test department",
                designation="Test role",
                country="India",
            )
            db.add(user)
            db.flush()
            db.add(UserRole(user_id=user.id, role_code=role.value))
            db.add(
                Credential(
                    user_id=user.id, password_hash=hasher.hash(password), must_change_password=temporary
                )
            )
        else:
            db.execute(delete(UserRole).where(UserRole.user_id == user.id))
            db.add(UserRole(user_id=user.id, role_code=role.value))
            credential = db.get(Credential, user.id)
            credential.password_hash = hasher.hash(password)
            credential.must_change_password = temporary
            user.credential_version += 1
        if name == "reset":
            token = os.environ["MI_E2E_RESET_TOKEN"]
            existing = db.scalar(select(PasswordToken).where(PasswordToken.token_hash == token_hash(token)))
            if not existing:
                db.add(
                    PasswordToken(
                        user_id=user.id,
                        token_hash=token_hash(token),
                        expires_at=utcnow() + timedelta(minutes=30),
                    )
                )
engine.dispose()
print("Isolated E2E accounts prepared.")
