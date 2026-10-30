from pathlib import Path
from urllib.parse import unquote
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import Identity, active_identity, csrf, get_db, require_role
from app.core.errors import AppError
from app.db.base import utcnow
from app.modules.appraisals import service
from app.modules.appraisals.models import (
    Appraisal,
    AppraisalAttachment,
    AppraisalHistory,
    AppraisalRevision,
    Cycle,
    FormVersion,
    Participant,
)
from app.modules.appraisals.schemas import (
    AppraisalPage,
    AppraisalResponse,
    CycleEdit,
    CycleInput,
    CyclePage,
    CycleResponse,
    HistoryPage,
    HistoryRow,
    ParticipantOption,
    ParticipantPage,
    RevisionResponse,
    SelfAssessmentInput,
    TransitionInput,
)
from app.modules.audit.models import AuditEvent
from app.modules.reviews import service as review_service
from app.modules.reviews.schemas import AcknowledgeInput, ReleasedResult
from app.modules.users.models import OperatorGuard, RoleCode, User

router = APIRouter(tags=["Employee appraisals"])
hr = [Depends(require_role(RoleCode.SUPER_ADMIN))]

ATTACHMENT_LIMIT = 10 * 1024 * 1024
ATTACHMENT_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def attachment_access(db, appraisal_id, actor, write=False):
    appraisal = db.get(Appraisal, appraisal_id)
    if not appraisal:
        raise AppError(404, "NOT_FOUND", "Appraisal not found.")
    if write:
        db.scalar(select(Cycle).where(Cycle.id == appraisal.cycle_id).with_for_update())
        service.fresh_actor(db, actor)
        appraisal = db.scalar(
            select(Appraisal)
            .where(Appraisal.id == appraisal_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not appraisal:
            raise AppError(404, "NOT_FOUND", "Appraisal not found.")
    owner = appraisal.employee_id == actor.user.id
    reviewer = appraisal.manager_id == actor.user.id and RoleCode.MANAGER in actor.user.roles
    hr_reader = RoleCode.SUPER_ADMIN in actor.user.roles
    if not owner and (write or not reviewer and not hr_reader):
        raise AppError(404, "NOT_FOUND", "Appraisal not found.")
    if not owner and (
        appraisal.content_revision < 1 or appraisal.state in {"DRAFT", "RETURNED_FOR_REVISION"}
    ):
        raise AppError(404, "NOT_FOUND", "Submitted attachments are not available.")
    if write and (not owner or appraisal.state not in service.EDITABLE_STATES):
        raise AppError(
            409, "APPRAISAL_READ_ONLY", "Attachments can only be changed while your appraisal is editable."
        )
    return appraisal


def attachment_row(item):
    return {
        "id": item.id,
        "name": item.original_name,
        "media_type": item.media_type,
        "size": item.byte_size,
        "uploaded_at": item.uploaded_at,
        "submitted_revision": item.submitted_revision,
    }


@router.get("/appraisals/{appraisal_id}/attachments")
def list_attachments(
    appraisal_id: str, actor: Identity = Depends(active_identity), db: Session = Depends(get_db)
):
    appraisal = attachment_access(db, appraisal_id, actor)
    query = select(AppraisalAttachment).where(
        AppraisalAttachment.appraisal_id == appraisal_id, AppraisalAttachment.deleted_at.is_(None)
    )
    if appraisal.employee_id != actor.user.id:
        query = query.where(AppraisalAttachment.submitted_revision.is_not(None))
    return {
        "items": [
            attachment_row(item)
            for item in db.scalars(query.order_by(AppraisalAttachment.uploaded_at, AppraisalAttachment.id))
        ]
    }


@router.post("/appraisals/{appraisal_id}/attachments", status_code=201)
async def upload_attachment(
    appraisal_id: str, request: Request, actor: Identity = Depends(csrf), db: Session = Depends(get_db)
):
    appraisal = attachment_access(db, appraisal_id, actor, write=True)
    filename = (
        unquote(request.headers.get("x-file-name", "attachment")).replace("\\", "/").split("/")[-1].strip()
    )
    filename = "".join(ch for ch in filename if ch.isprintable() and ch not in '<>:"|?*')[:255]
    ext = Path(filename).suffix.lower()
    media = ATTACHMENT_TYPES.get(ext)
    if not media:
        raise AppError(
            422, "FILE_TYPE", "Attach a PDF, PNG/JPG image, Word document, Excel workbook or PowerPoint file."
        )
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > ATTACHMENT_LIMIT:
            raise AppError(413, "FILE_TOO_LARGE", "Each attachment must be 10 MB or smaller.")
    valid = (
        (ext == ".pdf" and data.startswith(b"%PDF-"))
        or (ext == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n"))
        or (ext in {".jpg", ".jpeg"} and data.startswith(b"\xff\xd8\xff"))
    )
    if ext in {".docx", ".xlsx", ".pptx"}:
        import io
        import zipfile

        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                members = archive.namelist()
                entries = archive.infolist()
                with archive.open("[Content_Types].xml") as content_types:
                    types = content_types.read(65537).decode("utf-8", "ignore")
                wanted = {".docx": "wordprocessingml", ".xlsx": "spreadsheetml", ".pptx": "presentationml"}[
                    ext
                ]
                valid = len(members) <= 2000 and sum(part.file_size for part in entries) <= 50 * 1024 * 1024
                valid = valid and "[Content_Types].xml" in members and len(types) <= 65536 and wanted in types
                valid = valid and not any(part.casefold().endswith("vbaproject.bin") for part in members)
        except (ValueError, OSError, RuntimeError, zipfile.BadZipFile, KeyError):
            valid = False
    if not valid or not data:
        raise AppError(422, "FILE_CONTENT", "The file content does not match the selected file type.")
    count = (
        db.scalar(
            select(func.count())
            .select_from(AppraisalAttachment)
            .where(AppraisalAttachment.appraisal_id == appraisal_id, AppraisalAttachment.deleted_at.is_(None))
        )
        or 0
    )
    if count >= 25:
        raise AppError(422, "FILE_LIMIT", "An appraisal can have up to 25 attachments.")
    settings = request.app.state.settings
    directory = Path(settings.attachment_directory)
    if not directory.is_absolute():
        directory = Path(__file__).resolve().parents[4] / directory
    directory.mkdir(parents=True, exist_ok=True)
    object_key = f"{uuid4().hex}{ext}"
    path = directory / object_key
    path.write_bytes(data)
    item = AppraisalAttachment(
        appraisal_id=appraisal.id,
        uploader_id=actor.user.id,
        original_name=filename or f"attachment{ext}",
        object_key=object_key,
        media_type=media,
        byte_size=len(data),
    )
    db.add(item)
    db.add(
        AuditEvent(actor_id=actor.user.id, action="appraisal.attachment_uploaded", resource_id=appraisal.id)
    )
    db.commit()
    return attachment_row(item)


@router.get("/appraisals/{appraisal_id}/attachments/{attachment_id}")
def download_attachment(
    appraisal_id: str,
    attachment_id: str,
    request: Request,
    actor: Identity = Depends(active_identity),
    db: Session = Depends(get_db),
):
    appraisal = attachment_access(db, appraisal_id, actor)
    query = select(AppraisalAttachment).where(
        AppraisalAttachment.id == attachment_id,
        AppraisalAttachment.appraisal_id == appraisal_id,
        AppraisalAttachment.deleted_at.is_(None),
    )
    if appraisal.employee_id != actor.user.id:
        query = query.where(AppraisalAttachment.submitted_revision.is_not(None))
    item = db.scalar(query)
    if not item:
        raise AppError(404, "NOT_FOUND", "Attachment not found.")
    directory = Path(request.app.state.settings.attachment_directory)
    if not directory.is_absolute():
        directory = Path(__file__).resolve().parents[4] / directory
    path = directory / item.object_key
    if not path.is_file():
        raise AppError(404, "NOT_FOUND", "Attachment not found.")
    return FileResponse(
        path,
        media_type=item.media_type,
        filename=item.original_name,
        headers={"Content-Security-Policy": "default-src 'none'; sandbox"},
    )


@router.delete("/appraisals/{appraisal_id}/attachments/{attachment_id}", status_code=204)
def delete_attachment(
    appraisal_id: str, attachment_id: str, actor: Identity = Depends(csrf), db: Session = Depends(get_db)
):
    appraisal = attachment_access(db, appraisal_id, actor, write=True)
    item = db.scalar(
        select(AppraisalAttachment)
        .where(
            AppraisalAttachment.id == attachment_id,
            AppraisalAttachment.appraisal_id == appraisal_id,
            AppraisalAttachment.submitted_revision.is_(None),
            AppraisalAttachment.deleted_at.is_(None),
        )
        .with_for_update()
    )
    if not item:
        raise AppError(404, "NOT_FOUND", "Draft attachment not found.")
    item.deleted_at = utcnow()
    db.add(
        AuditEvent(actor_id=actor.user.id, action="appraisal.attachment_removed", resource_id=appraisal.id)
    )
    db.commit()
    return Response(status_code=204)


@router.get("/appraisals/{appraisal_id}/released-result", response_model=ReleasedResult)
def released_result(
    appraisal_id: str, actor: Identity = Depends(active_identity), db: Session = Depends(get_db)
):
    return review_service.released_to_owner(db, service.owned(db, appraisal_id, actor))


@router.post(
    "/appraisals/{appraisal_id}/acknowledge",
    response_model=ReleasedResult,
    dependencies=[Depends(active_identity)],
)
def acknowledge_result(
    appraisal_id: str, data: AcknowledgeInput, actor: Identity = Depends(csrf), db: Session = Depends(get_db)
):
    return review_service.acknowledge(db, appraisal_id, data, actor)


def cycle_lock(db, cycle_id, version):
    cycle = db.scalar(
        select(Cycle).where(Cycle.id == cycle_id).with_for_update().execution_options(populate_existing=True)
    )
    if not cycle:
        raise AppError(404, "NOT_FOUND", "Appraisal cycle not found.")
    if cycle.version != version:
        raise AppError(409, "VERSION_CONFLICT", "This cycle changed. Reload before continuing.")
    return cycle


def hr_write(db, actor):
    db.scalar(select(OperatorGuard).where(OperatorGuard.id == 1).with_for_update())
    service.fresh_actor(db, actor, RoleCode.SUPER_ADMIN)


@router.get("/cycles/participant-options", response_model=ParticipantPage, dependencies=hr)
def participant_options(
    q: str = Query("", max_length=150),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = select(User).where(User.active.is_(True))
    if q:
        query = query.where(
            or_(User.full_name.icontains(q, autoescape=True), User.employee_id.icontains(q, autoescape=True))
        )
    count = db.scalar(select(func.count()).select_from(query.subquery()))
    users = db.scalars(
        query.order_by(User.full_name, User.id).offset((page - 1) * page_size).limit(page_size)
    )
    return ParticipantPage(
        items=[
            ParticipantOption(
                id=u.id,
                full_name=u.full_name,
                employee_id=u.employee_id,
                department=u.department,
                manager_id=u.manager_id,
                role=", ".join(u.roles),
            )
            for u in users
        ],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.get("/cycles", response_model=CyclePage, dependencies=hr)
def cycles(
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), db: Session = Depends(get_db)
):
    count = db.scalar(select(func.count()).select_from(Cycle))
    values = db.scalars(
        select(Cycle)
        .order_by(Cycle.created_at.desc(), Cycle.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return CyclePage(
        items=[service.cycle_response(db, c) for c in values], total=count, page=page, page_size=page_size
    )


def participants(db, cycle, ids):
    active_ids = set(db.scalars(select(User.id).where(User.id.in_(ids), User.active.is_(True))))
    if active_ids != set(ids):
        raise AppError(422, "INVALID_PARTICIPANT", "Select only existing active accounts.")
    db.execute(delete(Participant).where(Participant.cycle_id == cycle.id))
    db.add_all(Participant(cycle_id=cycle.id, employee_id=employee_id) for employee_id in ids)


@router.post("/cycles", response_model=CycleResponse, status_code=201, dependencies=hr)
def create_cycle(data: CycleInput, actor: Identity = Depends(csrf), db: Session = Depends(get_db)):
    hr_write(db, actor)
    if not db.get(FormVersion, data.form_version_id):
        raise AppError(422, "INVALID_FORM", "Choose a published appraisal form.")
    cycle = Cycle(
        **data.model_dump(exclude={"participant_ids"}),
        created_by=actor.user.id,
    )
    db.add(cycle)
    db.flush()
    participants(db, cycle, data.participant_ids)
    db.add(AuditEvent(actor_id=actor.user.id, action="cycle.created", resource_id=cycle.id))
    db.commit()
    return service.cycle_response(db, cycle)


@router.patch("/cycles/{cycle_id}", response_model=CycleResponse, dependencies=hr)
def edit_cycle(
    cycle_id: str, data: CycleEdit, actor: Identity = Depends(csrf), db: Session = Depends(get_db)
):
    hr_write(db, actor)
    cycle = cycle_lock(db, cycle_id, data.expected_version)
    if cycle.state != "DRAFT":
        raise AppError(
            409, "CYCLE_IMMUTABLE", "Active cycle settings are frozen. Create a new cycle for new settings."
        )
    if not db.get(FormVersion, data.form_version_id):
        raise AppError(422, "INVALID_FORM", "Choose a published appraisal form.")
    for key, value in data.model_dump(exclude={"participant_ids", "expected_version"}).items():
        setattr(cycle, key, value)
    participants(db, cycle, data.participant_ids)
    cycle.version += 1
    db.add(AuditEvent(actor_id=actor.user.id, action="cycle.draft_changed", resource_id=cycle.id))
    db.commit()
    return service.cycle_response(db, cycle)


@router.post("/cycles/{cycle_id}/activate", response_model=CycleResponse, dependencies=hr)
def activate_cycle(
    cycle_id: str, data: TransitionInput, actor: Identity = Depends(csrf), db: Session = Depends(get_db)
):
    hr_write(db, actor)
    cycle = cycle_lock(db, cycle_id, data.expected_version)
    service.activate(db, cycle, actor)
    db.commit()
    return service.cycle_response(db, cycle)


@router.get("/me/appraisals", response_model=AppraisalPage)
def own_appraisals(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    actor: Identity = Depends(active_identity),
    db: Session = Depends(get_db),
):
    query = select(Appraisal).where(Appraisal.employee_id == actor.user.id)
    count = db.scalar(select(func.count()).select_from(query.subquery()))
    values = db.scalars(query.order_by(Appraisal.id).offset((page - 1) * page_size).limit(page_size))
    return AppraisalPage(
        items=[service.summary(db, a) for a in values], total=count, page=page, page_size=page_size
    )


@router.get("/appraisals/{appraisal_id}", response_model=AppraisalResponse)
def appraisal_detail(
    appraisal_id: str, actor: Identity = Depends(active_identity), db: Session = Depends(get_db)
):
    return service.detail(db, service.owned(db, appraisal_id, actor))


@router.put(
    "/appraisals/{appraisal_id}/self-assessment",
    response_model=AppraisalResponse,
    dependencies=[Depends(active_identity)],
)
def save_appraisal(
    appraisal_id: str,
    data: SelfAssessmentInput,
    actor: Identity = Depends(csrf),
    db: Session = Depends(get_db),
):
    appraisal = service.owned(db, appraisal_id, actor, True, data.expected_version)
    return service.save_draft(db, appraisal, data, actor)


@router.post(
    "/appraisals/{appraisal_id}/submit",
    response_model=AppraisalResponse,
    dependencies=[Depends(active_identity)],
)
def submit_appraisal(
    appraisal_id: str, data: TransitionInput, actor: Identity = Depends(csrf), db: Session = Depends(get_db)
):
    appraisal = service.owned(db, appraisal_id, actor, True, data.expected_version)
    return service.submit(db, appraisal, actor)


@router.get("/appraisals/{appraisal_id}/history", response_model=HistoryPage)
def appraisal_history(
    appraisal_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    actor: Identity = Depends(active_identity),
    db: Session = Depends(get_db),
):
    service.owned(db, appraisal_id, actor)
    query = select(AppraisalHistory).where(AppraisalHistory.appraisal_id == appraisal_id)
    count = db.scalar(select(func.count()).select_from(query.subquery()))
    events = db.scalars(
        query.order_by(AppraisalHistory.appraisal_version, AppraisalHistory.occurred_at, AppraisalHistory.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return HistoryPage(
        items=[
            HistoryRow(
                id=e.id,
                actor_name=db.get(User, e.actor_id).full_name,
                from_state=e.from_state,
                to_state=e.to_state,
                reason=e.reason,
                occurred_at=e.occurred_at,
            )
            for e in events
        ],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.get("/appraisals/{appraisal_id}/revisions/{revision}", response_model=RevisionResponse)
def appraisal_revision(
    appraisal_id: str,
    revision: int,
    actor: Identity = Depends(active_identity),
    db: Session = Depends(get_db),
):
    service.owned(db, appraisal_id, actor)
    snapshot = db.scalar(
        select(AppraisalRevision).where(
            AppraisalRevision.appraisal_id == appraisal_id, AppraisalRevision.revision == revision
        )
    )
    if not snapshot:
        raise AppError(404, "NOT_FOUND", "Submission revision not found.")
    return RevisionResponse(
        revision=snapshot.revision, submitted_at=snapshot.submitted_at, responses=snapshot.response_snapshot
    )
