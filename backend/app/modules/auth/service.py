import uuid
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import hasher, opaque_token, private_key, token_hash, verify_password
from app.db.base import utcnow
from app.modules.audit.models import AuditEvent
from app.modules.auth.models import AuthSession, Credential, PasswordToken
from app.modules.auth.schemas import UserResponse
from app.modules.notifications.service import enqueue
from app.modules.users.models import User, UserProfilePhoto


def profile(db: Session, user: User, credential: Credential) -> UserResponse:
    manager_name = (
        db.scalar(select(User.full_name).where(User.id == user.manager_id)) if user.manager_id else None
    )
    return UserResponse(
        id=user.id,
        employee_id=user.employee_id,
        email=user.email,
        full_name=user.full_name,
        department=user.department,
        designation=user.designation,
        country=user.country,
        date_joined=user.date_joined,
        manager_name=manager_name,
        profile_photo_revision=db.scalar(
            select(UserProfilePhoto.revision).where(UserProfilePhoto.user_id == user.id)
        ),
        roles=user.roles,
        must_change_password=credential.must_change_password,
    )


def csrf_value(settings: Settings, auth: AuthSession):
    return private_key(settings.secret_key.get_secret_value(), f"csrf:{auth.id}")


def issue_session(db: Session, user: User, settings: Settings):
    raw = opaque_token()
    auth = AuthSession(
        id=str(uuid.uuid4()),
        user_id=user.id,
        token_hash=token_hash(raw),
        csrf_hash="",
        credential_version=user.credential_version,
        expires_at=utcnow() + timedelta(hours=settings.session_hours),
    )
    csrf_token = csrf_value(settings, auth)
    auth.csrf_hash = token_hash(csrf_token)
    db.add(auth)
    return raw, csrf_token


def login(db: Session, settings: Settings, email: str, password: str):
    user = db.scalar(select(User).where(User.email == email).with_for_update())
    credential = db.get(Credential, user.id) if user else None
    valid = verify_password(credential.password_hash if credential else None, password)
    if not valid or not user or not user.active:
        db.add(AuditEvent(action="auth.login_failed", details={"reason": "invalid_credentials"}))
        db.commit()
        raise AppError(401, "INVALID_CREDENTIALS", "Email or password is incorrect.")
    if hasher.check_needs_rehash(credential.password_hash):
        credential.password_hash = hasher.hash(password)
    user.last_login_at = utcnow()
    raw, csrf_token = issue_session(db, user, settings)
    db.add(AuditEvent(actor_id=user.id, action="auth.login", resource_id=user.id))
    db.commit()
    return raw, csrf_token, profile(db, user, credential)


def revoke_all(db: Session, user: User):
    user.credential_version += 1
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


def change_password(db: Session, settings: Settings, actor, current_password: str, new_password: str):
    user = db.scalar(
        select(User)
        .where(User.id == actor.user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    credential = db.get(Credential, user.id, populate_existing=True)
    if user.credential_version != actor.session.credential_version or not user.active:
        raise AppError(401, "SESSION_EXPIRED", "Please sign in again.")
    if not verify_password(credential.password_hash, current_password):
        raise AppError(400, "CURRENT_PASSWORD_INCORRECT", "Your current password is incorrect.")
    if verify_password(credential.password_hash, new_password):
        raise AppError(422, "PASSWORD_REUSED", "Choose a different password.")
    credential.password_hash = hasher.hash(new_password)
    credential.must_change_password = False
    credential.changed_at = utcnow()
    revoke_all(db, user)
    db.execute(
        update(PasswordToken)
        .where(PasswordToken.user_id == user.id, PasswordToken.consumed_at.is_(None))
        .values(consumed_at=utcnow())
    )
    raw, csrf_token = issue_session(db, user, settings)
    db.add(AuditEvent(actor_id=user.id, action="auth.password_changed", resource_id=user.id))
    db.commit()
    return raw, csrf_token, profile(db, user, credential)


def request_password_reset(db: Session, settings: Settings, email: str) -> str:
    user = db.scalar(select(User).where(User.email == email.lower()).with_for_update())
    if user is None:
        raise AppError(
            404, "USER_NOT_REGISTERED", "User is not registered. Please contact your administrator."
        )
    if not user.active:
        raise AppError(
            403, "ACCOUNT_INACTIVE", "Your account is inactive. Please contact your administrator."
        )
    if not settings.mail_enabled:
        raise AppError(
            503, "MAIL_UNAVAILABLE", "Password reset email is unavailable. Please contact your administrator."
        )

    expires = utcnow() + timedelta(minutes=settings.reset_minutes)
    preview_only = (
        settings.mail_test_mode and user.email.casefold() != (settings.mail_test_recipient or "").casefold()
    )
    instructions = f"Hi {user.full_name},\n\nWe received a request to reset your MyCareer password.\n\n"
    if preview_only:
        instructions += "Password reset email preview. Reset links are omitted in test mode.\n\n"
    else:
        raw = opaque_token()
        db.add(PasswordToken(user_id=user.id, token_hash=token_hash(raw), expires_at=expires))
        instructions += f"Reset your password: {settings.public_base_url.rstrip('/')}/#reset={raw}\n"
        if settings.alternate_public_base_url:
            instructions += (
                f"Alternate reset link: {settings.alternate_public_base_url.rstrip('/')}/#reset={raw}\n"
            )
        instructions += f"\nThis link expires at {expires:%d %b %Y, %H:%M} UTC and can only be used once.\n\n"
    instructions += "If you did not request this, you can ignore this email."
    enqueue(db, settings, "Reset your MyCareer password", instructions, [user.email])
    db.add(AuditEvent(action="auth.reset_requested", resource_id=user.id, details={"channel": "email"}))
    db.commit()
    if preview_only:
        return "Password reset email is in test mode. Please contact your administrator for a reset link."
    return "A password reset link has been queued for your registered email. Please check your inbox."


def issue_reset(db: Session, settings: Settings, user: User):
    """Issue a password reset through the local administrator command."""
    user = db.scalar(
        select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True)
    )
    if not user.active:
        raise AppError(409, "ACCOUNT_INACTIVE", "An inactive account cannot receive a reset.")
    raw = opaque_token()
    revoke_all(db, user)
    db.execute(
        update(PasswordToken)
        .where(PasswordToken.user_id == user.id, PasswordToken.consumed_at.is_(None))
        .values(consumed_at=utcnow())
    )
    db.add(
        PasswordToken(
            user_id=user.id,
            token_hash=token_hash(raw),
            expires_at=utcnow() + timedelta(minutes=settings.reset_minutes),
        )
    )
    db.add(
        AuditEvent(
            action="auth.operator_reset_issued", resource_id=user.id, details={"channel": "local_operator"}
        )
    )
    db.commit()
    return raw


def complete_reset(db: Session, raw: str, new_password: str):
    found = db.scalar(select(PasswordToken).where(PasswordToken.token_hash == token_hash(raw)))
    if not found:
        raise AppError(400, "INVALID_RESET_TOKEN", "This reset link is invalid or expired.")
    user = db.scalar(select(User).where(User.id == found.user_id).with_for_update())
    reset = db.scalar(
        select(PasswordToken)
        .where(PasswordToken.id == found.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not user.active or reset.consumed_at or reset.expires_at <= utcnow():
        raise AppError(400, "INVALID_RESET_TOKEN", "This reset link is invalid or expired.")
    credential = db.get(Credential, user.id)
    if verify_password(credential.password_hash, new_password):
        raise AppError(422, "PASSWORD_REUSED", "Choose a different password.")
    credential.password_hash = hasher.hash(new_password)
    credential.changed_at = utcnow()
    credential.must_change_password = False
    revoke_all(db, user)
    db.execute(
        update(PasswordToken)
        .where(PasswordToken.user_id == user.id, PasswordToken.consumed_at.is_(None))
        .values(consumed_at=utcnow())
    )
    db.add(AuditEvent(actor_id=user.id, action="auth.password_reset_completed", resource_id=user.id))
    db.commit()
