from copy import deepcopy
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import Identity, csrf, get_db, require_role
from app.core.errors import AppError
from app.db.base import utcnow
from app.modules.appraisals.models import FormVersion
from app.modules.audit.models import AuditEvent
from app.modules.forms.config import config_for
from app.modules.forms.models import FormTemplate
from app.modules.forms.schemas import FormCommand, FormConfig, SaveForm
from app.modules.users.models import RoleCode
from app.modules.users.service import admin_transaction

router = APIRouter(
    prefix="/hr/forms", tags=["HR form builder"], dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN))]
)


class TemplateResponse(BaseModel):
    id: str
    config: FormConfig
    version: int
    published_form_id: str | None
    updated_at: datetime


class TemplatePage(BaseModel):
    items: list[TemplateResponse]
    total: int
    page: int
    page_size: int


class PublishedForm(BaseModel):
    id: str
    name: str


def response(item):
    return TemplateResponse(
        id=item.id,
        config=item.config,
        version=item.version,
        published_form_id=item.published_form_id,
        updated_at=item.updated_at,
    )


@router.get("/published", response_model=list[PublishedForm])
def published(db: Session = Depends(get_db)):
    return [
        PublishedForm(id=f.id, name=f.definition.get("form_name", "Workbook annual appraisal"))
        for f in db.scalars(select(FormVersion).order_by(FormVersion.id))
    ]


@router.get("/default", response_model=FormConfig)
def default(db: Session = Depends(get_db)):
    return config_for(db.get(FormVersion, "workbook-ye2025-v1").definition)


@router.get("", response_model=TemplatePage)
def templates(
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), db: Session = Depends(get_db)
):
    values = db.scalars(
        select(FormTemplate)
        .order_by(FormTemplate.updated_at.desc(), FormTemplate.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return TemplatePage(
        items=[response(v) for v in values],
        total=db.scalar(select(func.count()).select_from(FormTemplate)),
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=TemplateResponse, status_code=201)
def create(config: FormConfig, actor: Identity = Depends(csrf), db: Session = Depends(get_db)):
    admin_transaction(db, actor)
    item = FormTemplate(name=config.name, config=config.model_dump(), created_by=actor.user.id)
    db.add(item)
    db.flush()
    db.add(AuditEvent(actor_id=actor.user.id, action="form.draft_created", resource_id=item.id))
    db.commit()
    return response(item)


def locked(db, identifier, version):
    item = db.get(FormTemplate, identifier, with_for_update=True, populate_existing=True)
    if not item:
        raise AppError(404, "NOT_FOUND", "Form template not found.")
    if item.version != version:
        raise AppError(409, "VERSION_CONFLICT", "The form changed. Reload before continuing.")
    return item


@router.put("/{identifier}", response_model=TemplateResponse)
def save(identifier: str, data: SaveForm, actor: Identity = Depends(csrf), db: Session = Depends(get_db)):
    admin_transaction(db, actor)
    item = locked(db, identifier, data.expected_version)
    item.config = data.config.model_dump()
    item.name = data.config.name
    item.version += 1
    item.updated_at = utcnow()
    db.add(AuditEvent(actor_id=actor.user.id, action="form.draft_saved", resource_id=item.id))
    db.commit()
    return response(item)


@router.post("/{identifier}/publish", response_model=TemplateResponse)
def publish(
    identifier: str, data: FormCommand, actor: Identity = Depends(csrf), db: Session = Depends(get_db)
):
    admin_transaction(db, actor)
    item = locked(db, identifier, data.expected_version)
    config = FormConfig.model_validate(item.config)
    source = db.get(FormVersion, "workbook-ye2025-v1")
    definition = deepcopy(source.definition)
    definition.update(
        form_name=f"{config.name} - version {item.version}",
        form_config=config.model_dump(),
        competencies=[c.label for c in config.competencies] if config.competencies_enabled else [],
        published_at=utcnow().isoformat(),
        template_id=item.id,
        template_version=item.version,
    )
    form = FormVersion(source_sha256=source.source_sha256, definition=definition)
    from app.modules.appraisals.models import identifier as new_id

    form.id = new_id()
    definition["form_version_id"] = form.id
    db.add(form)
    db.flush()
    item.published_form_id = form.id
    item.version += 1
    item.updated_at = utcnow()
    db.add(
        AuditEvent(
            actor_id=actor.user.id,
            action="form.published",
            resource_id=form.id,
            details={"template_id": item.id},
        )
    )
    db.commit()
    return response(item)
