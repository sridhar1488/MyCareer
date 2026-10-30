from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.dependencies import Identity, csrf, get_db, identity
from app.db.base import utcnow
from app.modules.audit.models import AuditEvent
from app.modules.auth import service
from app.modules.auth.rate_limit import throttle
from app.modules.auth.schemas import (
    LoginInput,
    PasswordChange,
    ResetComplete,
    ResetRequest,
    SessionResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def apply_cookie(response, settings, token):
    response.set_cookie(
        "mi_session",
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api",
        max_age=settings.session_hours * 3600,
    )


def limit(request, action, principal):
    throttle(
        request.app.state.sessions,
        request.app.state.settings,
        action,
        request.client.host if request.client else "unknown",
        principal,
    )


@router.post("/login", response_model=SessionResponse)
def login(data: LoginInput, request: Request, response: Response, db: Session = Depends(get_db)):
    limit(request, "login", str(data.email))
    settings = request.app.state.settings
    raw, csrf_token, user = service.login(db, settings, str(data.email), data.password.get_secret_value())
    # Rotate any previous browser session instead of leaving an orphan active.
    previous = request.cookies.get("mi_session")
    if previous:
        from sqlalchemy import update

        from app.core.security import token_hash
        from app.modules.auth.models import AuthSession

        db.execute(
            update(AuthSession)
            .where(AuthSession.token_hash == token_hash(previous))
            .values(revoked_at=utcnow())
        )
        db.commit()
    apply_cookie(response, settings, raw)
    return SessionResponse(user=user, csrf_token=csrf_token)


@router.get("/me", response_model=UserResponse)
def me(actor: Identity = Depends(identity)):
    return service.profile(actor.user, actor.credential)


@router.get("/csrf")
def csrf_token(request: Request, actor: Identity = Depends(identity)) -> dict[str, str]:
    return {"csrf_token": service.csrf_value(request.app.state.settings, actor.session)}


@router.post("/logout", status_code=204)
def logout(
    request: Request, response: Response, actor: Identity = Depends(csrf), db: Session = Depends(get_db)
):
    actor.session.revoked_at = utcnow()
    db.add(AuditEvent(actor_id=actor.user.id, action="auth.logout", resource_id=actor.user.id))
    db.commit()
    response.delete_cookie(
        "mi_session",
        path="/api",
        secure=request.app.state.settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )


@router.post("/change-password", response_model=SessionResponse)
def change_password(
    data: PasswordChange,
    request: Request,
    response: Response,
    actor: Identity = Depends(csrf),
    db: Session = Depends(get_db),
):
    limit(request, "password_change", actor.user.id)
    raw, csrf_token, user = service.change_password(
        db,
        request.app.state.settings,
        actor,
        data.current_password.get_secret_value(),
        data.new_password.get_secret_value(),
    )
    apply_cookie(response, request.app.state.settings, raw)
    return SessionResponse(user=user, csrf_token=csrf_token)


@router.post("/forgot-password", status_code=202)
def forgot_password(data: ResetRequest, request: Request, db: Session = Depends(get_db)) -> dict[str, str]:
    limit(request, "reset_request", str(data.email).lower())
    # No public token issuance or false promise of email delivery.
    db.add(AuditEvent(action="auth.reset_requested", details={"channel": "administrator_assistance"}))
    db.commit()
    return {"message": "Contact your account administrator for a secure password reset link."}


@router.post("/complete-password-setup", status_code=204)
def complete_password_setup(data: ResetComplete, request: Request, db: Session = Depends(get_db)):
    from app.core.security import token_hash

    limit(request, "reset_complete", token_hash(data.token))
    service.complete_reset(db, data.token, data.new_password.get_secret_value())
