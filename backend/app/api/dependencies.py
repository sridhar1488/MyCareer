import hmac
from dataclasses import dataclass
from datetime import timedelta

from fastapi import Depends, Request
from fastapi.security import APIKeyCookie
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import token_hash
from app.db.base import utcnow
from app.modules.auth.models import AuthSession, Credential
from app.modules.users.models import RoleCode, User

cookie_scheme = APIKeyCookie(name="mi_session", auto_error=False)


def get_db(request: Request):
    with request.app.state.sessions() as db:
        yield db


@dataclass
class Identity:
    user: User
    session: AuthSession
    credential: Credential


def identity(request: Request, db: Session = Depends(get_db), token: str | None = Depends(cookie_scheme)):
    if not token or len(token) > 128:
        raise AppError(401, "UNAUTHENTICATED", "Please sign in to continue.")
    auth = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(token)))
    now = utcnow()
    settings = request.app.state.settings
    if (
        not auth
        or auth.revoked_at
        or auth.expires_at <= now
        or auth.last_seen_at + timedelta(minutes=settings.session_idle_minutes) <= now
    ):
        raise AppError(401, "SESSION_EXPIRED", "Your session has expired. Please sign in again.")
    user = db.get(User, auth.user_id)
    credential = db.get(Credential, auth.user_id)
    if not user or not user.active or not credential or user.credential_version != auth.credential_version:
        raise AppError(401, "SESSION_EXPIRED", "Please sign in again.")
    auth.last_seen_at = now
    db.commit()
    return Identity(user, auth, credential)


def active_identity(actor: Identity = Depends(identity)):
    if actor.credential.must_change_password:
        raise AppError(403, "PASSWORD_CHANGE_REQUIRED", "Change your temporary password to continue.")
    return actor


def csrf(request: Request, actor: Identity = Depends(identity)):
    value = request.headers.get("X-CSRF-Token", "")
    if not value or len(value) > 128 or not hmac.compare_digest(token_hash(value), actor.session.csrf_hash):
        raise AppError(403, "CSRF_REJECTED", "Refresh the page and try again.")
    return actor


def require_role(role: RoleCode):
    def check(actor: Identity = Depends(active_identity)):
        if role.value not in actor.user.roles:
            raise AppError(403, "FORBIDDEN", "You do not have access to this function.")
        return actor

    return check


def require_owner(actor: User, owner_id: str):
    # Administration privileges never imply permission to edit another employee's responses.
    if actor.id != owner_id:
        raise AppError(404, "NOT_FOUND", "Record not found.")


def require_assigned_manager(actor: User, owner_id: str, manager_id: str):
    if actor.id == owner_id or actor.id != manager_id or RoleCode.MANAGER not in actor.roles:
        raise AppError(404, "NOT_FOUND", "Record not found.")
