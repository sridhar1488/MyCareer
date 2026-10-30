from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import Identity, get_db, require_role
from app.core.errors import AppError
from app.modules.appraisals.models import Appraisal, Cycle
from app.modules.audit.models import AuditEvent
from app.modules.hr import reports
from app.modules.reviews.models import FinalEvaluation
from app.modules.reviews.schemas import ReleasedResult
from app.modules.reviews.service import final_result
from app.modules.users.models import RoleCode

router = APIRouter(prefix="/hr/evaluations", tags=["HR final evaluations"])


def records(db, actor, q="", cycle_id=None, manager_id=None, department="", status=None, appraisal_id=None):
    values = db.execute(
        select(Appraisal, Cycle)
        .join(Cycle)
        .join(FinalEvaluation)
        .where(
            Appraisal.state.in_(["HR_APPROVED", "RELEASED"]),
            or_(Appraisal.employee_id != actor.user.id, Appraisal.state == "RELEASED"),
        )
        .order_by(FinalEvaluation.finalized_at.desc(), Appraisal.id)
    ).all()
    for appraisal, cycle in values:
        identity = appraisal.identity_snapshot
        if (
            appraisal_id
            and appraisal.id != appraisal_id
            or cycle_id
            and cycle.id != cycle_id
            or manager_id
            and appraisal.manager_id != manager_id
            or department
            and identity.get("department", "").casefold() != department.casefold()
            or status
            and appraisal.state != status
        ):
            continue
        if (
            q
            and q.casefold()
            not in " ".join(
                str(identity.get(k, "")) for k in ["employee_name", "employee_id", "manager_name"]
            ).casefold()
        ):
            continue
        yield appraisal, cycle


@router.get("")
def listing(
    q: str = Query("", max_length=150),
    cycle_id: str | None = None,
    manager_id: str | None = None,
    department: str = Query("", max_length=100),
    status: str | None = Query(None, pattern="^(HR_APPROVED|RELEASED)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    actor: Identity = Depends(require_role(RoleCode.SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    values = list(records(db, actor, q, cycle_id, manager_id, department, status))
    return {
        "items": [
            {
                "id": a.id,
                "cycle": c.title,
                "identity": a.identity_snapshot,
                "state": a.state,
                "finalized_at": db.get(FinalEvaluation, a.id).finalized_at,
            }
            for a, c in values[(page - 1) * page_size : page * page_size]
        ],
        "total": len(values),
        "page": page,
        "page_size": page_size,
    }


@router.get("/export/{format}")
def export(
    format: str,
    q: str = Query("", max_length=150),
    cycle_id: str | None = None,
    manager_id: str | None = None,
    department: str = Query("", max_length=100),
    status: str | None = Query(None, pattern="^(HR_APPROVED|RELEASED)$"),
    appraisal_id: str | None = None,
    actor: Identity = Depends(require_role(RoleCode.SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    if format not in ["xlsx", "pdf"]:
        raise AppError(422, "FORMAT", "Choose Excel or PDF.")
    values = list(records(db, actor, q, cycle_id, manager_id, department, status, appraisal_id))
    if appraisal_id and not values:
        raise AppError(404, "NOT_FOUND", "Final evaluation not found.")
    if len(values) > (100 if format == "pdf" else 1000):
        raise AppError(
            422,
            "EXPORT_LIMIT",
            "Narrow the filters: PDF supports 100 evaluations and Excel 1,000 per download.",
        )
    content = [(a, c, final_result(db, a.id)) for a, c in values]
    data = reports.pdf(content) if format == "pdf" else reports.excel(content)
    db.add(
        AuditEvent(
            actor_id=actor.user.id,
            action=f"hr.export_{format}",
            resource_id=appraisal_id,
            details={"count": len(values)},
        )
    )
    db.commit()
    return Response(
        data,
        media_type="application/pdf"
        if format == "pdf"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="final-evaluations.{format}"'},
    )


@router.get("/{appraisal_id}", response_model=ReleasedResult)
def detail(
    appraisal_id: str,
    actor: Identity = Depends(require_role(RoleCode.SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    values = list(records(db, actor, appraisal_id=appraisal_id))
    if not values:
        raise AppError(404, "NOT_FOUND", "Final evaluation not found.")
    result = final_result(db, appraisal_id)
    db.add(AuditEvent(actor_id=actor.user.id, action="hr.final_viewed", resource_id=appraisal_id))
    db.commit()
    return result
