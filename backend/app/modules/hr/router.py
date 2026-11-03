from fractions import Fraction

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.api.dependencies import Identity, get_db, require_role
from app.db.base import utcnow
from app.modules.appraisals.models import Appraisal, Cycle
from app.modules.hr.schemas import (
    AnalyticsResponse,
    AnalyticsSummary,
    DepartmentAnalytics,
    FilterOption,
    ManagerStatus,
    MonitorOptions,
    MonitorResponse,
    MonitorRow,
    ScorePoint,
    TopPerformer,
)
from app.modules.reviews import scoring
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


@router.get("/analytics", response_model=AnalyticsResponse)
def analytics(
    cycle_id: str | None = None,
    actor: Identity = Depends(require_role(RoleCode.SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """Aggregate cycle progress and HR-approved scores for HR-only charts."""
    query = (
        select(Appraisal, FinalEvaluation)
        .outerjoin(FinalEvaluation, FinalEvaluation.appraisal_id == Appraisal.id)
        .where(or_(Appraisal.employee_id != actor.user.id, Appraisal.state == "RELEASED"))
    )
    if cycle_id:
        query = query.where(Appraisal.cycle_id == cycle_id)

    department_rows: dict[str, dict] = {}
    employee_scores: dict[str, dict] = {}
    overall_scores: list[Fraction] = []
    score_points: list[ScorePoint] = []
    appraisal_count = 0
    approved_count = 0
    for appraisal, final in db.execute(query):
        appraisal_count += 1
        identity = final.employee_snapshot.get("identity", {}) if final else appraisal.identity_snapshot
        department = identity.get("department") or "Unassigned"
        dept = department_rows.setdefault(department, {"appraisals": 0, "approved": 0, "scores": []})
        dept["appraisals"] += 1
        if not final or appraisal.state not in {"HR_APPROVED", "RELEASED"}:
            continue

        approved_count += 1
        raw_overall = final.score.get("overall", {})
        score_value = Fraction(int(raw_overall["numerator"]), int(raw_overall["denominator"]))
        overall_scores.append(score_value)
        dept["approved"] += 1
        dept["scores"].append(score_value)

        employee_id = identity.get("employee_id", "")
        employee_name = identity.get("employee_name", "Unknown employee")
        manager_name = identity.get("manager_name", "")
        score_points.append(
            ScorePoint(
                employee_id=employee_id,
                employee_name=employee_name,
                score=scoring.exact(score_value, 1).display,
            )
        )
        person = employee_scores.setdefault(
            employee_id,
            {
                "employee_name": employee_name,
                "department": department,
                "manager_name": manager_name,
                "scores": [],
            },
        )
        person["scores"].append(score_value)

    def average(values):
        return sum(values, Fraction(0)) / len(values) if values else None

    departments = [
        DepartmentAnalytics(
            department=name,
            appraisal_count=values["appraisals"],
            approved_count=values["approved"],
            approval_percent=scoring.exact(
                Fraction(values["approved"] * 100, values["appraisals"]), 1
            ).display,
            average_score=(scoring.exact(average(values["scores"]), 1).display if values["scores"] else None),
        )
        for name, values in sorted(department_rows.items())
    ]
    performers = [
        TopPerformer(
            employee_id=employee_id,
            employee_name=person["employee_name"],
            department=person["department"],
            manager_name=person["manager_name"],
            average_score=scoring.exact(average(person["scores"]), 1).display,
            approved_appraisals=len(person["scores"]),
        )
        for employee_id, person in employee_scores.items()
    ]
    performers.sort(key=lambda p: (-Fraction(p.average_score), p.employee_name.casefold()))
    return AnalyticsResponse(
        summary=AnalyticsSummary(
            appraisal_count=appraisal_count,
            approved_count=approved_count,
            approval_percent=(
                scoring.exact(Fraction(approved_count * 100, appraisal_count), 1).display
                if appraisal_count
                else "0.0"
            ),
            approved_average=(scoring.exact(average(overall_scores), 1).display if overall_scores else None),
        ),
        departments=departments,
        top_performers=performers[:5],
        score_points=score_points,
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
