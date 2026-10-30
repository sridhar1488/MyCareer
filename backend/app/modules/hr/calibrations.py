from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import Identity, csrf, get_db, require_role
from app.core.errors import AppError
from app.db.base import utcnow
from app.modules.appraisals import service as employee_service
from app.modules.appraisals.models import Appraisal, AppraisalHistory, Cycle
from app.modules.audit.models import AuditEvent
from app.modules.reviews import scoring
from app.modules.reviews.models import CalibrationDraft, CalibrationEvent, FinalEvaluation, ManagerSubmission
from app.modules.reviews.schemas import CalibrationApprove, CalibrationSave, EvaluationInput
from app.modules.users.models import OperatorGuard, RoleCode, User

router = APIRouter(
    prefix="/hr/calibrations",
    tags=["HR calibration"],
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN))],
)


def entry(db, appraisal):
    cycle = db.get(Cycle, appraisal.cycle_id)
    return {
        "id": appraisal.id,
        "employee_name": appraisal.identity_snapshot["employee_name"],
        "employee_id": appraisal.identity_snapshot["employee_id"],
        "department": appraisal.identity_snapshot.get("department", ""),
        "manager_name": appraisal.identity_snapshot["manager_name"],
        "cycle_title": cycle.title,
        "state": appraisal.state,
        "version": appraisal.version,
        "submitted_revision": appraisal.content_revision,
        "manager_submitted_at": db.get(ManagerSubmission, appraisal.id).submitted_at,
    }


@router.get("")
def queue(
    q: str = Query("", max_length=150),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = select(Appraisal).where(Appraisal.state == "HR_REVIEW")
    if q.strip():
        query = query.where(
            Appraisal.identity_snapshot["employee_name"].as_string().icontains(q.strip(), autoescape=True)
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    values = db.scalars(
        query.order_by(Appraisal.submitted_at, Appraisal.id).offset((page - 1) * page_size).limit(page_size)
    )
    return {"items": [entry(db, a) for a in values], "total": total, "page": page, "page_size": page_size}


@router.get("/{appraisal_id}")
def detail(
    appraisal_id: str,
    actor: Identity = Depends(require_role(RoleCode.SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    appraisal = db.get(Appraisal, appraisal_id)
    submission = db.get(ManagerSubmission, appraisal_id) if appraisal else None
    if not appraisal or appraisal.state != "HR_REVIEW" or not submission:
        raise AppError(404, "NOT_FOUND", "An evaluation awaiting HR calibration was not found.")
    draft = db.get(CalibrationDraft, appraisal_id)
    events = db.scalars(
        select(CalibrationEvent)
        .where(CalibrationEvent.appraisal_id == appraisal_id)
        .order_by(CalibrationEvent.appraisal_version, CalibrationEvent.occurred_at)
    )
    db.add(AuditEvent(actor_id=actor.user.id, action="hr.calibration_viewed", resource_id=appraisal_id))
    db.commit()
    return {
        **entry(db, appraisal),
        "manager_evaluation": submission.evaluation,
        "manager_score": submission.score,
        "evaluation": draft.evaluation if draft else submission.evaluation,
        "score_preview": draft.score if draft else submission.score,
        "employee_snapshot": submission.employee_snapshot,
        "events": [
            {
                "action": e.action,
                "reason": e.reason,
                "actor_name": db.get(User, e.actor_id).full_name,
                "occurred_at": e.occurred_at,
                "score": e.score,
            }
            for e in events
        ],
    }


def locked(db, appraisal_id, data, actor):
    initial = db.get(Appraisal, appraisal_id)
    if not initial:
        raise AppError(404, "NOT_FOUND", "Appraisal not found.")
    db.scalar(select(Cycle).where(Cycle.id == initial.cycle_id).with_for_update())
    db.scalar(select(OperatorGuard).where(OperatorGuard.id == 1).with_for_update())
    employee_service.fresh_actor(db, actor, RoleCode.SUPER_ADMIN)
    appraisal = db.scalar(
        select(Appraisal)
        .where(Appraisal.id == appraisal_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if appraisal.state != "HR_REVIEW" or not db.get(ManagerSubmission, appraisal_id):
        raise AppError(409, "INVALID_TRANSITION", "This evaluation is no longer awaiting HR approval.")
    if appraisal.version != data.expected_version or appraisal.content_revision != data.submitted_revision:
        raise AppError(409, "VERSION_CONFLICT", "The evaluation changed. Reload before continuing.")
    return appraisal


def validate_calibration(db, appraisal, evaluation):
    manager = EvaluationInput.model_validate(db.get(ManagerSubmission, appraisal.id).evaluation)
    raw, original = evaluation.model_dump(), manager.model_dump()
    # Calibration adjusts ratings only; comments, employee text and manager narratives remain intact.
    for key in ("goals", "contributions", "competencies"):
        if len(raw[key]) != len(original[key]):
            raise AppError(422, "ITEM_MISMATCH", "Calibration must cover the manager's original items.")
        for index, item in enumerate(raw[key]):
            for text_key in ("comment",):
                if item.get(text_key, "") != original[key][index].get(text_key, ""):
                    raise AppError(
                        422,
                        "COMMENT_LOCKED",
                        "Calibration may adjust ratings; manager comments remain preserved.",
                    )
    if (
        raw["strengths"] != original["strengths"]
        or raw["improvements"] != original["improvements"]
        or raw["extra_answers"] != original["extra_answers"]
    ):
        raise AppError(
            422,
            "MANAGER_CONTENT_LOCKED",
            "Manager narrative responses remain preserved during score calibration.",
        )
    content = db.get(ManagerSubmission, appraisal.id).employee_snapshot["responses"]
    definition = db.get(ManagerSubmission, appraisal.id).employee_snapshot["form_definition"]
    errors = scoring.validation_errors(evaluation, content, len(definition["competencies"]), definition)
    if errors:
        raise AppError(
            422,
            "INVALID_CALIBRATION",
            "Complete all required ratings and comments before saving calibration.",
        )
    return scoring.calculate(
        evaluation,
        content,
        db.get(Cycle, appraisal.cycle_id).scoring_policy_version,
        len(definition["competencies"]),
        definition,
    )


def event(db, appraisal, actor, action, evaluation, score, reason):
    appraisal.version += 1
    db.add(
        CalibrationEvent(
            appraisal_id=appraisal.id,
            appraisal_version=appraisal.version,
            evaluation=evaluation.model_dump(),
            score=score.model_dump(),
            action=action,
            reason=reason.strip(),
            actor_id=actor.user.id,
        )
    )


@router.put("/{appraisal_id}")
def save(
    appraisal_id: str, data: CalibrationSave, actor: Identity = Depends(csrf), db: Session = Depends(get_db)
):
    appraisal = locked(db, appraisal_id, data, actor)
    submission = db.get(ManagerSubmission, appraisal_id)
    evaluation = data.evaluation
    score = validate_calibration(db, appraisal, evaluation)
    original = EvaluationInput.model_validate(submission.evaluation)
    changed = [
        (section, i)
        for section in ("goals", "contributions", "competencies")
        for i, (current, prior) in enumerate(
            zip(getattr(evaluation, section), getattr(original, section), strict=True)
        )
        if (current.rating, current.not_applicable, current.applicability_reason)
        != (prior.rating, prior.not_applicable, prior.applicability_reason)
    ]
    if changed and not data.reason.strip():
        raise AppError(422, "REASON_REQUIRED", "Add a reason for the rating calibration.")
    draft = db.get(CalibrationDraft, appraisal_id, with_for_update=True, populate_existing=True)
    if not draft:
        draft = CalibrationDraft(appraisal_id=appraisal_id)
        db.add(draft)
    draft.evaluation, draft.score = evaluation.model_dump(), score.model_dump()
    draft.updated_by, draft.updated_at = actor.user.id, utcnow()
    event(db, appraisal, actor, "CALIBRATED", evaluation, score, data.reason)
    db.add(AuditEvent(actor_id=actor.user.id, action="hr.calibration_saved", resource_id=appraisal_id))
    db.commit()
    return detail(appraisal_id, actor, db)


@router.post("/{appraisal_id}/approve")
def approve(
    appraisal_id: str,
    data: CalibrationApprove,
    actor: Identity = Depends(csrf),
    db: Session = Depends(get_db),
):
    appraisal = locked(db, appraisal_id, data, actor)
    submission = db.get(ManagerSubmission, appraisal_id)
    draft = db.get(CalibrationDraft, appraisal_id)
    evaluation = EvaluationInput.model_validate(draft.evaluation if draft else submission.evaluation)
    score = validate_calibration(db, appraisal, evaluation)
    event(db, appraisal, actor, "APPROVED", evaluation, score, data.reason)
    db.add(
        FinalEvaluation(
            appraisal_id=appraisal.id,
            submitted_revision=appraisal.content_revision,
            employee_snapshot=submission.employee_snapshot,
            evaluation=evaluation.model_dump(),
            score=score.model_dump(),
            policy=submission.policy,
            finalized_by=actor.user.id,
        )
    )
    previous = appraisal.state
    appraisal.state = "HR_APPROVED"
    db.add(
        AppraisalHistory(
            appraisal_id=appraisal.id,
            actor_id=actor.user.id,
            from_state=previous,
            to_state="HR_APPROVED",
            reason=data.reason.strip() or "HR approved the calibrated evaluation",
            appraisal_version=appraisal.version,
        )
    )
    db.add(AuditEvent(actor_id=actor.user.id, action="hr.calibration_approved", resource_id=appraisal_id))
    db.commit()
    return {
        "id": appraisal.id,
        "state": appraisal.state,
        "score": score.model_dump(),
        "approved_at": db.get(FinalEvaluation, appraisal.id).finalized_at,
    }
