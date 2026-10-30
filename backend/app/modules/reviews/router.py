from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import Identity, csrf, get_db, require_role
from app.modules.appraisals.models import Appraisal, Cycle
from app.modules.appraisals.schemas import HistoryPage, HistoryRow
from app.modules.reviews import service
from app.modules.reviews.models import ReviewEvent
from app.modules.reviews.schemas import (
    ReleaseReview,
    ReturnReview,
    ReviewCommand,
    ReviewEventPage,
    ReviewEventRow,
    ReviewResponse,
    SaveReview,
    TeamPage,
    TeamRow,
)
from app.modules.users.models import RoleCode, User

router = APIRouter(
    prefix="/manager",
    tags=["Assigned manager reviews"],
    dependencies=[Depends(require_role(RoleCode.MANAGER))],
)


@router.get("/appraisals", response_model=TeamPage)
def assigned_appraisals(
    q: str = Query("", max_length=150),
    state: str | None = Query(
        None,
        pattern="^(DRAFT|SUBMITTED|UNDER_REVIEW|RETURNED_FOR_REVISION|HR_REVIEW|HR_APPROVED|FINALIZED|RELEASED)$",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    actor: Identity = Depends(require_role(RoleCode.MANAGER)),
    db: Session = Depends(get_db),
):
    query = (
        select(Appraisal)
        .join(User, User.id == Appraisal.employee_id)
        .where(
            Appraisal.manager_id == actor.user.id,
            Appraisal.employee_id != actor.user.id,
        )
    )
    if q:
        query = query.where(
            or_(User.full_name.icontains(q, autoescape=True), User.employee_id.icontains(q, autoescape=True))
        )
    if state:
        query = query.where(Appraisal.state == state)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    appraisals = db.scalars(
        query.order_by(Appraisal.submitted_at.desc(), Appraisal.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = []
    for a in appraisals:
        cycle = db.get(Cycle, a.cycle_id)
        items.append(
            TeamRow(
                id=a.id,
                employee_name=a.identity_snapshot["employee_name"],
                employee_id=a.identity_snapshot["employee_id"],
                department=a.identity_snapshot["department"],
                cycle_title=cycle.title,
                state=a.state,
                version=a.version,
                submitted_revision=a.content_revision,
                submitted_at=a.submitted_at,
                submission_deadline=cycle.submission_deadline,
            )
        )
    return TeamPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/appraisals/{appraisal_id}", response_model=ReviewResponse)
def review_detail(
    appraisal_id: str,
    actor: Identity = Depends(require_role(RoleCode.MANAGER)),
    db: Session = Depends(get_db),
):
    return service.detail(db, service.assigned(db, appraisal_id, actor))


@router.post("/appraisals/{appraisal_id}/begin", response_model=ReviewResponse)
def begin(
    appraisal_id: str, data: ReviewCommand, actor: Identity = Depends(csrf), db: Session = Depends(get_db)
):
    return service.begin(db, service.assigned(db, appraisal_id, actor, data), actor)


@router.put("/appraisals/{appraisal_id}/review", response_model=ReviewResponse)
def save_review(
    appraisal_id: str, data: SaveReview, actor: Identity = Depends(csrf), db: Session = Depends(get_db)
):
    return service.save(db, service.assigned(db, appraisal_id, actor, data), data, actor)


@router.post("/appraisals/{appraisal_id}/return", response_model=ReviewResponse)
def return_review(
    appraisal_id: str, data: ReturnReview, actor: Identity = Depends(csrf), db: Session = Depends(get_db)
):
    return service.return_for_revision(db, service.assigned(db, appraisal_id, actor, data), data, actor)


@router.post("/appraisals/{appraisal_id}/finalize", response_model=ReviewResponse)
def finalize_review(
    appraisal_id: str, data: ReviewCommand, actor: Identity = Depends(csrf), db: Session = Depends(get_db)
):
    return service.finalize(db, service.assigned(db, appraisal_id, actor, data), data, actor)


@router.post("/appraisals/{appraisal_id}/release", response_model=ReviewResponse)
def release_review(
    appraisal_id: str, data: ReleaseReview, actor: Identity = Depends(csrf), db: Session = Depends(get_db)
):
    return service.release(db, service.assigned(db, appraisal_id, actor, data), data, actor)


@router.get("/appraisals/{appraisal_id}/review-history", response_model=ReviewEventPage)
def review_history(
    appraisal_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    actor: Identity = Depends(require_role(RoleCode.MANAGER)),
    db: Session = Depends(get_db),
):
    service.assigned(db, appraisal_id, actor)
    query = select(ReviewEvent).where(ReviewEvent.appraisal_id == appraisal_id)
    count = db.scalar(select(func.count()).select_from(query.subquery()))
    events = db.scalars(
        query.order_by(ReviewEvent.appraisal_version.desc(), ReviewEvent.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return ReviewEventPage(
        items=[ReviewEventRow.model_validate(e, from_attributes=True) for e in events],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.get("/appraisals/{appraisal_id}/history", response_model=HistoryPage)
def workflow_history(
    appraisal_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    actor: Identity = Depends(require_role(RoleCode.MANAGER)),
    db: Session = Depends(get_db),
):
    service.assigned(db, appraisal_id, actor)
    from app.modules.appraisals.models import AppraisalHistory

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
