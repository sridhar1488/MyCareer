from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import Identity, csrf, get_db, require_role
from app.core.errors import AppError
from app.core.security import hasher, opaque_token
from app.db.base import utcnow
from app.modules.audit.models import AuditEvent
from app.modules.auth.models import Credential
from app.modules.imports import service
from app.modules.imports.models import ImportBatch
from app.modules.notifications.service import enqueue as enqueue_email
from app.modules.users import service as users
from app.modules.users.models import RoleCode, User, UserRole

router = APIRouter(
    prefix="/admin/user-imports",
    tags=["Bulk user import"],
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN))],
)


class ImportIssue(BaseModel):
    row: int
    message: str


class ImportPreview(BaseModel):
    batch_id: str | None
    rows: list[dict]
    errors: list[ImportIssue]
    expires_at: datetime | None


class SetupLink(BaseModel):
    user_id: str
    full_name: str
    email: str
    setup_url: str
    expires_at: datetime


class ImportResult(BaseModel):
    created: int
    setup_links: list[SetupLink]


@router.get("/template")
def download_template():
    return Response(
        service.template(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="MyCareer-HRMS-user-import.xlsx"'},
    )


@router.post("/preview", response_model=ImportPreview)
async def preview(request: Request, actor: Identity = Depends(csrf), db: Session = Depends(get_db)):
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > service.MAX_BYTES:
            raise AppError(413, "IMPORT_TOO_LARGE", "The workbook must be no larger than 5 MB.")
    rows = service.read_file(bytes(data))
    normalized, errors = service.validate_rows(db, rows)
    if errors:
        return ImportPreview(batch_id=None, rows=normalized, errors=errors, expires_at=None)
    users.admin_transaction(db, actor)
    batch = ImportBatch(actor_id=actor.user.id, rows=normalized, expires_at=utcnow() + timedelta(minutes=30))
    db.add(batch)
    db.flush()
    db.add(
        AuditEvent(
            actor_id=actor.user.id,
            action="admin.import_previewed",
            resource_id=batch.id,
            details={"rows": len(normalized)},
        )
    )
    db.commit()
    return ImportPreview(batch_id=batch.id, rows=normalized, errors=[], expires_at=batch.expires_at)


@router.post("/{batch_id}/confirm", response_model=ImportResult, status_code=201)
def confirm(batch_id: str, request: Request, actor: Identity = Depends(csrf), db: Session = Depends(get_db)):
    users.admin_transaction(db, actor)
    batch = db.get(ImportBatch, batch_id, with_for_update=True, populate_existing=True)
    if not batch or batch.actor_id != actor.user.id:
        raise AppError(404, "NOT_FOUND", "Import preview not found.")
    if batch.consumed_at or batch.expires_at <= utcnow():
        raise AppError(
            409, "IMPORT_EXPIRED", "The preview has expired or was already imported. Upload again."
        )
    rows, errors = service.validate_rows(db, batch.rows)
    if errors:
        raise AppError(
            409,
            "IMPORT_CHANGED",
            "Accounts or manager assignments changed after preview. Upload again to review current validation results.",
        )
    created = {}
    links = []
    for row in rows:
        department = users.department(db, row["department"])
        user = User(
            **{
                key: row[key]
                for key in [
                    "full_name",
                    "employee_id",
                    "email",
                    "department",
                    "designation",
                    "country",
                    "location",
                ]
            },
            date_joined=date.fromisoformat(row["date_joined"]) if row["date_joined"] else None,
            department_id=department.id,
        )
        db.add(user)
        db.flush()
        db.add_all(
            UserRole(user_id=user.id, role_code=role) for role in users.assigned_roles(RoleCode(row["role"]))
        )
        db.add(
            Credential(user_id=user.id, password_hash=hasher.hash(opaque_token()), must_change_password=True)
        )
        created[row["employee_id"].casefold()] = user
        settings = request.app.state.settings
        link = service.setup_token(db, user, settings)
        links.append(link)
        if settings.mail_enabled:
            if settings.mail_test_mode:
                setup_instructions = (
                    "Mail is in test mode, so the working one-time setup link is withheld from this email. "
                    "The administrator can securely share the private setup link from the completed import."
                )
            else:
                setup_instructions = service.setup_email_instructions(link, settings)
            enqueue_email(
                db,
                settings,
                "Welcome to MyCareer — set up your account",
                f"Hello {user.full_name},\n\nYour MyCareer account has been created. "
                "Use the secure account setup instructions below to choose your password. "
                "Passwords must be 8–15 characters.\n\n"
                f"{setup_instructions}\n\nIf you need help, contact your MyCareer administrator.",
                [user.email],
            )
        db.add(
            AuditEvent(
                actor_id=actor.user.id,
                action="admin.user_created",
                resource_id=user.id,
                details={
                    "import_batch": batch.id,
                    "roles": users.assigned_roles(RoleCode(row["role"])),
                },
            )
        )
    db.flush()
    for user in created.values():
        db.expire(user, ["role_assignments"])
    for row in rows:
        manager = row["manager_employee_id"].casefold()
        if manager:
            target = created.get(manager) or db.scalar(
                select(User).where(func.lower(User.employee_id) == manager)
            )
            users.assign_manager(db, created[row["employee_id"].casefold()], target.id, actor.user.id)
    batch.consumed_at = utcnow()
    db.add(
        AuditEvent(
            actor_id=actor.user.id,
            action="admin.import_completed",
            resource_id=batch.id,
            details={"created": len(rows)},
        )
    )
    users.save(db)
    return ImportResult(created=len(rows), setup_links=links)
