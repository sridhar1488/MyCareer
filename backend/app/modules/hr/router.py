from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.api.dependencies import get_db, require_role
from app.db.base import utcnow
from app.modules.appraisals.models import Appraisal, Cycle
from app.modules.hr.schemas import FilterOption, ManagerStatus, MonitorOptions, MonitorResponse, MonitorRow
from app.modules.reviews.models import Acknowledgement, FinalEvaluation, Release
from app.modules.users.models import RoleCode, User, UserRole

router = APIRouter(
    prefix="/hr", tags=["HR monitoring"], dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN))]
)
STATUSES = [
    "NOT_STARTED",
    "DRAFT",
    "SUBMITTED",
    "UNDER_REVIEW",
    "RETURNED_FOR_REVISION",
    "HR_REVIEW",
    "HR_APPROVED",
    "FINALIZED",
    "RELEASED",
    "ACKNOWLEDGED",
]


@router.get("/monitor-options", response_model=MonitorOptions)
def options(db: Session = Depends(get_db)):
    cycles = db.scalars(select(Cycle).order_by(Cycle.created_at.desc(), Cycle.id))
    managers = db.scalars(
        select(User)
        .where(
            or_(
                User.id.in_(select(Appraisal.manager_id)),
                User.id.in_(select(UserRole.user_id).where(UserRole.role_code == RoleCode.MANAGER)),
            )
        )
        .order_by(User.full_name, User.id)
    )
    return MonitorOptions(
        cycles=[FilterOption(id=c.id, label=c.title) for c in cycles],
        managers=[FilterOption(id=u.id, label=f"{u.full_name} ({u.employee_id})") for u in managers],
    )


@router.get("/monitor", response_model=MonitorResponse)
def monitor(
    view: str = Query("individuals", pattern="^(individuals|managers)$"),
    q: str = Query("", max_length=150),
    cycle_id: str | None = None,
    manager_id: str | None = None,
    department: str = Query("", max_length=100),
    status: str | None = Query(
        None,
        pattern="^(NOT_STARTED|DRAFT|SUBMITTED|UNDER_REVIEW|RETURNED_FOR_REVISION|HR_REVIEW|HR_APPROVED|FINALIZED|RELEASED|ACKNOWLEDGED)$",
    ),
    overdue_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    employee, manager = aliased(User), aliased(User)
    stage = case(
        (Appraisal.state == "DRAFT", case((Appraisal.started_at.is_(None), "NOT_STARTED"), else_="DRAFT")),
        (Acknowledgement.appraisal_id.is_not(None), "ACKNOWLEDGED"),
        else_=Appraisal.state,
    )
    now = utcnow()
    employee_pending = Appraisal.state.in_(["DRAFT", "RETURNED_FOR_REVISION"])
    overdue_condition = employee_pending & (Cycle.submission_deadline < now)
    query = (
        select(Appraisal)
        .join(Cycle, Cycle.id == Appraisal.cycle_id)
        .join(employee, employee.id == Appraisal.employee_id)
        .join(manager, manager.id == Appraisal.manager_id)
        .outerjoin(Acknowledgement, Acknowledgement.appraisal_id == Appraisal.id)
        .outerjoin(FinalEvaluation, FinalEvaluation.appraisal_id == Appraisal.id)
        .outerjoin(Release, Release.appraisal_id == Appraisal.id)
    )
    if q.strip():
        query = query.where(
            or_(
                Appraisal.identity_snapshot["employee_name"]
                .as_string()
                .icontains(q.strip(), autoescape=True),
                Appraisal.identity_snapshot["employee_id"].as_string().icontains(q.strip(), autoescape=True),
                Appraisal.identity_snapshot["manager_name"].as_string().icontains(q.strip(), autoescape=True),
                manager.full_name.icontains(q.strip(), autoescape=True),
                manager.employee_id.icontains(q.strip(), autoescape=True),
            )
        )
    if cycle_id:
        query = query.where(Appraisal.cycle_id == cycle_id)
    if manager_id:
        query = query.where(Appraisal.manager_id == manager_id)
    if department:
        query = query.where(Appraisal.identity_snapshot["department"].as_string() == department)
    if status:
        query = query.where(stage == status)
    if overdue_only:
        query = query.where(overdue_condition)
    counts = [func.coalesce(func.sum(case((stage == s, 1), else_=0)), 0).label(s) for s in STATUSES]
    totals = db.execute(
        query.with_only_columns(func.count(Appraisal.id), *counts, maintain_column_froms=True)
    ).one()
    status_counts = dict(zip(STATUSES, [int(v) for v in totals[1:]], strict=True))
    grouped = query.with_only_columns(
        manager.id,
        manager.full_name,
        manager.active,
        func.count(Appraisal.id),
        *counts,
        maintain_column_froms=True,
    ).group_by(manager.id, manager.full_name, manager.active)
    manager_total = db.scalar(select(func.count()).select_from(grouped.subquery()))
    items, managers = [], []
    if view == "managers":
        values = db.execute(
            grouped.order_by(manager.full_name, manager.id).offset((page - 1) * page_size).limit(page_size)
        )
        managers = [
            ManagerStatus(
                manager_id=row[0],
                manager_name=row[1],
                manager_active=row[2],
                total=row[3],
                status_counts=dict(zip(STATUSES, [int(v) for v in row[4:]], strict=True)),
            )
            for row in values
        ]
    else:
        rows = db.execute(
            query.with_only_columns(
                Appraisal,
                Cycle,
                employee.active,
                manager.active,
                stage,
                FinalEvaluation.finalized_at,
                Release.released_at,
                Acknowledgement.acknowledged_at,
                maintain_column_froms=True,
            )
            .order_by(Appraisal.identity_snapshot["employee_name"].as_string(), Appraisal.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        for a, c, emp_active, mgr_active, current, finalized, released, acknowledged in rows:
            identity = a.identity_snapshot
            pending, responsible = {
                "NOT_STARTED": ("Start self-assessment", identity["employee_name"]),
                "DRAFT": ("Complete and submit self-assessment", identity["employee_name"]),
                "SUBMITTED": ("Begin manager review", identity["manager_name"]),
                "UNDER_REVIEW": ("Complete manager review", identity["manager_name"]),
                "RETURNED_FOR_REVISION": ("Revise and resubmit", identity["employee_name"]),
                "HR_REVIEW": ("Calibrate and approve evaluation", "HR team"),
                "HR_APPROVED": ("Release HR-approved evaluation", identity["manager_name"]),
                "FINALIZED": ("Release finalized evaluation", identity["manager_name"]),
                "RELEASED": ("Acknowledge receipt", identity["employee_name"]),
                "ACKNOWLEDGED": ("Complete", None),
            }[current]
            items.append(
                MonitorRow(
                    id=a.id,
                    employee_id=identity["employee_id"],
                    employee_name=identity["employee_name"],
                    employee_active=emp_active,
                    department=identity["department"],
                    designation=identity["designation"],
                    manager_id=a.manager_id,
                    manager_name=identity["manager_name"],
                    manager_active=mgr_active,
                    cycle_id=c.id,
                    cycle_title=c.title,
                    cycle_state=c.state,
                    status=current,
                    pending_action=pending,
                    responsible_name=responsible,
                    submission_deadline=c.submission_deadline,
                    overdue=a.state in ["DRAFT", "RETURNED_FOR_REVISION"] and c.submission_deadline < now,
                    deadline_enforced=not c.allow_late_submission,
                    submitted_at=a.submitted_at,
                    finalized_at=finalized,
                    released_at=released,
                    acknowledged_at=acknowledged,
                )
            )
    return MonitorResponse(
        total=totals[0],
        status_counts=status_counts,
        items=items,
        managers=managers,
        manager_total=manager_total,
        page=page,
        page_size=page_size,
        view=view,
    )
