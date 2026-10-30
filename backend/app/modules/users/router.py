from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.api.dependencies import Identity, csrf, get_db, require_role
from app.core.errors import AppError
from app.core.security import hasher
from app.db.base import utcnow
from app.modules.audit.models import AuditEvent
from app.modules.auth.models import Credential, PasswordToken
from app.modules.auth.service import revoke_all
from app.modules.users import service
from app.modules.users.models import RoleCode, User, UserRole
from app.modules.users.schemas import (
    AuditPage,
    AuditRow,
    ChangeManager,
    ChangeRole,
    CreateUser,
    DirectoryPage,
    DirectoryUser,
    EditUser,
    ResetPassword,
    VersionInput,
)

router = APIRouter(prefix="/admin", tags=["Account administration"])


@router.post("/users/{user_id}/setup-link", dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN))])
def setup_link(
    user_id: str,
    data: VersionInput,
    request: Request,
    actor: Identity = Depends(csrf),
    db: Session = Depends(get_db),
):
    from app.modules.imports.service import setup_token

    with service.admin_write(db, actor):
        user = service.versioned_user(db, user_id, data.expected_version)
        if user.id == actor.user.id or not user.active:
            raise AppError(
                409, "SETUP_NOT_ALLOWED", "Use Account security for yourself. Other accounts must be active."
            )
        revoke_all(db, user)
        db.execute(
            update(PasswordToken)
            .where(PasswordToken.user_id == user.id, PasswordToken.consumed_at.is_(None))
            .values(consumed_at=utcnow())
        )
        user.version += 1
        result = setup_token(db, user, request.app.state.settings)
        db.add(AuditEvent(actor_id=actor.user.id, action="admin.setup_link_created", resource_id=user.id))
    return result


class AccountSummary(BaseModel):
    total_accounts: int
    active_accounts: int
    role_counts: dict[str, int]


@router.get(
    "/summary", response_model=AccountSummary, dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN))]
)
def summary(db: Session = Depends(get_db)):
    return AccountSummary(
        total_accounts=db.scalar(select(func.count()).select_from(User)),
        active_accounts=db.scalar(select(func.count()).select_from(User).where(User.active.is_(True))),
        role_counts={
            role.value: db.scalar(
                select(func.count()).select_from(UserRole).where(UserRole.role_code == role.value)
            )
            for role in RoleCode
        },
    )


@router.get(
    "/users", response_model=DirectoryPage, dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN))]
)
def directory(
    q: str = Query("", max_length=150),
    role: RoleCode | None = None,
    active: bool | None = None,
    department: str | None = None,
    manager_id: str | None = None,
    sort: str = Query("full_name", pattern="^(full_name|employee_id|email|department|created_at)$"),
    descending: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    statement = select(User)
    if q:
        term = q.strip()
        statement = statement.where(
            or_(
                User.full_name.icontains(term, autoescape=True),
                User.email.icontains(term, autoescape=True),
                User.employee_id.icontains(term, autoescape=True),
            )
        )
    if role:
        statement = statement.where(
            User.id.in_(select(UserRole.user_id).where(UserRole.role_code == role.value))
        )
    if active is not None:
        statement = statement.where(User.active == active)
    if department:
        statement = statement.where(User.department == department)
    if manager_id:
        statement = statement.where(User.manager_id == manager_id)
    total = db.scalar(select(func.count()).select_from(statement.subquery()))
    column = getattr(User, sort)
    users = db.scalars(
        statement.order_by(column.desc() if descending else column.asc(), User.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return DirectoryPage(
        items=[service.directory_user(db, u) for u in users], total=total, page=page, page_size=page_size
    )


@router.get(
    "/users/{user_id}",
    response_model=DirectoryUser,
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN))],
)
def user_detail(user_id: str, db: Session = Depends(get_db)):
    return service.directory_user(db, service.get_user(db, user_id))


@router.post(
    "/users",
    status_code=201,
    response_model=DirectoryUser,
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN))],
)
def create_user(data: CreateUser, actor: Identity = Depends(csrf), db: Session = Depends(get_db)):
    with service.admin_write(db, actor):
        dept = service.department(db, data.department)
        user = User(
            **data.model_dump(exclude={"temporary_password", "role", "manager_id", "super_admin"}),
            department_id=dept.id,
        )
        db.add(user)
        db.flush()
        roles = service.assigned_roles(data.role, data.super_admin)
        db.add_all(UserRole(user_id=user.id, role_code=role) for role in roles)
        db.add(
            Credential(
                user_id=user.id,
                password_hash=hasher.hash(data.temporary_password.get_secret_value()),
                must_change_password=True,
            )
        )
        service.assign_manager(db, user, data.manager_id, actor.user.id)
        db.add(
            AuditEvent(
                actor_id=actor.user.id,
                action="admin.user_created",
                resource_id=user.id,
                details={"role": data.role.value, "roles": roles},
            )
        )
    db.expire(user, ["role_assignments"])
    return service.directory_user(db, user)


@router.patch(
    "/users/{user_id}",
    response_model=DirectoryUser,
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN))],
)
def edit_user(user_id: str, data: EditUser, actor: Identity = Depends(csrf), db: Session = Depends(get_db)):
    with service.admin_write(db, actor):
        user = service.versioned_user(db, user_id, data.expected_version)
        changes = data.model_dump(exclude={"expected_version"})
        fields = [key for key, value in changes.items() if getattr(user, key) != value]
        for key, value in changes.items():
            setattr(user, key, value)
        user.department_id = service.department(db, data.department).id
        user.version += 1
        db.add(
            AuditEvent(
                actor_id=actor.user.id,
                action="admin.profile_changed",
                resource_id=user.id,
                details={"fields": fields},
            )
        )
    return service.directory_user(db, user)


@router.put(
    "/users/{user_id}/role",
    response_model=DirectoryUser,
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN))],
)
def change_role(
    user_id: str, data: ChangeRole, actor: Identity = Depends(csrf), db: Session = Depends(get_db)
):
    with service.admin_write(db, actor):
        user = service.versioned_user(db, user_id, data.expected_version)
        if user.id == actor.user.id:
            raise AppError(403, "SELF_ROLE_CHANGE", "You cannot change your own role.")
        roles = service.assigned_roles(data.role, data.super_admin)
        service.protect_admin(db, user, RoleCode.SUPER_ADMIN not in roles)
        if RoleCode.MANAGER in user.roles and RoleCode.MANAGER not in roles:
            service.protect_manager(db, user)
        previous = user.roles
        db.execute(delete(UserRole).where(UserRole.user_id == user.id))
        db.add_all(UserRole(user_id=user.id, role_code=role) for role in roles)
        user.version += 1
        revoke_all(db, user)
        db.add(
            AuditEvent(
                actor_id=actor.user.id,
                action="admin.role_changed",
                resource_id=user.id,
                details={"previous_roles": previous, "roles": roles},
            )
        )
    db.expire(user, ["role_assignments"])
    return service.directory_user(db, user)


@router.put(
    "/users/{user_id}/manager",
    response_model=DirectoryUser,
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN))],
)
def change_manager(
    user_id: str, data: ChangeManager, actor: Identity = Depends(csrf), db: Session = Depends(get_db)
):
    with service.admin_write(db, actor):
        user = service.versioned_user(db, user_id, data.expected_version)
        service.assign_manager(db, user, data.manager_id, actor.user.id)
        user.version += 1
    return service.directory_user(db, user)


@router.post(
    "/users/{user_id}/{action}",
    response_model=DirectoryUser,
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN))],
)
def account_action(
    user_id: str,
    action: str,
    data: VersionInput,
    actor: Identity = Depends(csrf),
    db: Session = Depends(get_db),
):
    if action not in {"activate", "deactivate"}:
        raise AppError(404, "NOT_FOUND", "Account action not found.")
    with service.admin_write(db, actor):
        user = service.versioned_user(db, user_id, data.expected_version)
        if action == "deactivate":
            service.protect_admin(db, user, True)
            if user.id == actor.user.id:
                raise AppError(
                    409, "SELF_DEACTIVATION", "Use another administrator to deactivate your account."
                )
            service.protect_manager(db, user)
            revoke_all(db, user)
        user.active = action == "activate"
        user.version += 1
        db.add(AuditEvent(actor_id=actor.user.id, action=f"admin.user_{action}d", resource_id=user.id))
    return service.directory_user(db, user)


@router.put(
    "/users/{user_id}/temporary-password",
    status_code=204,
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN))],
)
def reset_password(
    user_id: str, data: ResetPassword, actor: Identity = Depends(csrf), db: Session = Depends(get_db)
):
    with service.admin_write(db, actor):
        user = service.versioned_user(db, user_id, data.expected_version)
        if user.id == actor.user.id:
            raise AppError(409, "USE_PASSWORD_CHANGE", "Change your own password from Account security.")
        if not user.active:
            raise AppError(409, "ACCOUNT_INACTIVE", "Reactivate this account before resetting its password.")
        credential = db.get(Credential, user.id)
        credential.password_hash = hasher.hash(data.temporary_password.get_secret_value())
        credential.must_change_password = True
        credential.changed_at = utcnow()
        user.version += 1
        revoke_all(db, user)
        db.execute(
            update(PasswordToken)
            .where(PasswordToken.user_id == user.id, PasswordToken.consumed_at.is_(None))
            .values(consumed_at=utcnow())
        )
        db.add(AuditEvent(actor_id=actor.user.id, action="admin.password_reset", resource_id=user.id))


@router.get(
    "/audit-events", response_model=AuditPage, dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN))]
)
def audit_events(
    q: str = Query("", max_length=80),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    statement = select(AuditEvent).where(
        or_(AuditEvent.action.startswith("admin."), AuditEvent.action.startswith("auth."))
    )
    if q:
        statement = statement.where(AuditEvent.action.icontains(q, autoescape=True))
    total = db.scalar(select(func.count()).select_from(statement.subquery()))
    events = db.scalars(
        statement.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return AuditPage(
        items=[AuditRow.model_validate(e, from_attributes=True) for e in events],
        total=total,
        page=page,
        page_size=page_size,
    )
