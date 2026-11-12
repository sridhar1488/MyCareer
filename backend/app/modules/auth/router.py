from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import Identity, active_identity, csrf, get_db, identity
from app.core.errors import AppError
from app.db.base import utcnow
from app.modules.audit.models import AuditEvent
from app.modules.auth import profile_photo, service
from app.modules.auth.rate_limit import throttle
from app.modules.auth.schemas import (
    LoginInput,
    PasswordChange,
    ResetComplete,
    ResetRequest,
    SessionResponse,
    UserResponse,
)
from app.modules.users.models import UserProfilePhoto

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
def me(actor: Identity = Depends(identity), db: Session = Depends(get_db)):
    return service.profile(db, actor.user, actor.credential)


@router.get("/me/photo", response_class=Response, responses={200: {"content": {"image/jpeg": {}}}})
def get_photo(actor: Identity = Depends(active_identity), db: Session = Depends(get_db)):
    photo = db.get(UserProfilePhoto, actor.user.id)
    if not photo:
        raise AppError(404, "PHOTO_NOT_FOUND", "No profile picture is set.")
    return Response(photo.image, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"})


@router.put("/me/photo", response_model=UserResponse, dependencies=[Depends(active_identity)])
async def upload_photo(request: Request, actor: Identity = Depends(csrf), db: Session = Depends(get_db)):
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > profile_photo.MAX_UPLOAD:
            raise AppError(413, "PHOTO_TOO_LARGE", "Choose an image of 2 MB or less.")
        data.extend(chunk)
    image = await run_in_threadpool(profile_photo.normalize_photo, bytes(data))
    await run_in_threadpool(profile_photo.change_photo, db, actor.user.id, image)
    return await run_in_threadpool(service.profile, db, actor.user, actor.credential)


@router.delete("/me/photo", response_model=UserResponse, dependencies=[Depends(active_identity)])
def delete_photo(actor: Identity = Depends(csrf), db: Session = Depends(get_db)):
    profile_photo.change_photo(db, actor.user.id, None)
    return service.profile(db, actor.user, actor.credential)


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
    return {"message": service.request_password_reset(db, request.app.state.settings, str(data.email))}


@router.post("/complete-password-setup", status_code=204)
def complete_password_setup(data: ResetComplete, request: Request, db: Session = Depends(get_db)):
    from app.core.security import token_hash

    limit(request, "reset_complete", token_hash(data.token))
    service.complete_reset(db, data.token, data.new_password.get_secret_value())
