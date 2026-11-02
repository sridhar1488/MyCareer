from contextlib import contextmanager

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.core.errors import AppError
from app.db.base import utcnow
from app.modules.audit.models import AuditEvent
from app.modules.users.models import Department, OperatorGuard, ReportingRelationship, RoleCode, User
from app.modules.users.schemas import DirectoryUser


def assigned_roles(role, super_admin=False):
    if role == RoleCode.SUPER_ADMIN:
        return [RoleCode.SUPER_ADMIN.value]
    if role == RoleCode.EMPLOYEE and super_admin:
        raise AppError(
            422,
            "EMPLOYEE_SUPER_ADMIN_FORBIDDEN",
            "Employee accounts cannot be assigned Super Admin access. Choose HR / Super Admin or Manager.",
        )
    values = [role.value]
    if super_admin:
        values.append(RoleCode.SUPER_ADMIN.value)
    return values


@contextmanager
def admin_write(db, actor):
    try:
        admin_transaction(db, actor)
        yield
        save(db)
    except IntegrityError:
        db.rollback()
        raise AppError(
            409, "DUPLICATE_ACCOUNT", "The email address or employee ID is already in use."
        ) from None


def admin_transaction(db, actor):
    actor_id, credential_version = actor.user.id, actor.session.credential_version
    db.scalar(select(OperatorGuard).where(OperatorGuard.id == 1).with_for_update())
    current = db.scalar(
        select(User).where(User.id == actor_id).with_for_update().execution_options(populate_existing=True)
    )
    db.expire(current, ["role_assignments"])
    if (
        not current.active
        or current.credential_version != credential_version
        or RoleCode.SUPER_ADMIN not in current.roles
    ):
        raise AppError(403, "FORBIDDEN", "Your administrator access has changed. Please sign in again.")


def get_user(db, user_id):
    user = db.scalar(
        select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True)
    )
    if not user:
        raise AppError(404, "NOT_FOUND", "Account not found.")
    return user


def versioned_user(db, user_id, expected_version):
    user = get_user(db, user_id)
    if user.version != expected_version:
        raise AppError(409, "VERSION_CONFLICT", "This account changed. Refresh the directory before editing.")
    return user


def directory_user(db, user):
    manager = db.get(User, user.manager_id) if user.manager_id else None
    return DirectoryUser(
        id=user.id,
        full_name=user.full_name,
        employee_id=user.employee_id,
        email=user.email,
        department=user.department,
        designation=user.designation,
        country=user.country,
        roles=user.roles,
        manager_id=user.manager_id,
        manager_name=manager.full_name if manager else None,
        active=user.active,
        version=user.version,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


def department(db, name):
    found = db.scalar(select(Department).where(func.lower(Department.name) == name.lower()))
    if not found:
        found = Department(name=name)
        db.add(found)
        db.flush()
    return found


def validate_manager(db, employee_id, manager_id):
    if not manager_id:
        return
    if employee_id == manager_id:
        raise AppError(422, "SELF_MANAGER", "An employee cannot report to themselves.")
    manager = db.get(User, manager_id)
    if not manager or not manager.active or RoleCode.MANAGER not in manager.roles:
        raise AppError(422, "INVALID_MANAGER", "Choose an active account with the Manager role.")
    visited = {employee_id}
    while manager:
        if manager.id in visited:
            raise AppError(422, "REPORTING_CYCLE", "This assignment would create a reporting cycle.")
        visited.add(manager.id)
        manager = db.get(User, manager.manager_id) if manager.manager_id else None


def assign_manager(db, user, manager_id, actor_id):
    validate_manager(db, user.id, manager_id)
    if user.manager_id == manager_id:
        return
    now = utcnow()
    db.execute(
        update(ReportingRelationship)
        .where(ReportingRelationship.employee_id == user.id, ReportingRelationship.valid_to.is_(None))
        .values(valid_to=now)
    )
    previous = user.manager_id
    user.manager_id = manager_id
    if manager_id:
        db.add(
            ReportingRelationship(
                employee_id=user.id, manager_id=manager_id, changed_by=actor_id, valid_from=now
            )
        )
    db.add(
        AuditEvent(
            actor_id=actor_id,
            action="admin.manager_changed",
            resource_id=user.id,
            details={"previous_manager_id": previous, "manager_id": manager_id},
        )
    )


def save(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(
            409, "DUPLICATE_ACCOUNT", "The email address or employee ID is already in use."
        ) from None


def protect_admin(db, user, remove=False):
    if remove and user.active and RoleCode.SUPER_ADMIN in user.roles:
        from app.modules.users.models import UserRole

        count = db.scalar(
            select(func.count())
            .select_from(User)
            .join(UserRole)
            .where(User.active.is_(True), UserRole.role_code == RoleCode.SUPER_ADMIN)
        )
        if count <= 1:
            raise AppError(409, "LAST_ADMIN", "The last active Super Admin cannot be removed or deactivated.")


def protect_manager(db, user):
    if db.scalar(select(User.id).where(User.manager_id == user.id, User.active.is_(True)).limit(1)):
        raise AppError(
            409,
            "MANAGER_HAS_REPORTS",
            "Reassign active direct reports before changing this manager’s access.",
        )
    from app.modules.appraisals.models import Appraisal

    if db.scalar(
        select(Appraisal.id).where(Appraisal.manager_id == user.id, Appraisal.state != "RELEASED").limit(1)
    ):
        raise AppError(
            409,
            "MANAGER_HAS_APPRAISALS",
            "This manager owns an unfinished appraisal. Historical reviewer ownership cannot be reassigned here.",
        )
