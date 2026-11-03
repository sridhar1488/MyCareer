from sqlalchemy import select

from app.api.dependencies import require_assigned_manager
from app.core.errors import AppError
from app.db.base import utcnow
from app.modules.appraisals import service as employee_service
from app.modules.appraisals.models import Appraisal, AppraisalHistory, AppraisalRevision, Cycle
from app.modules.appraisals.schemas import AppraisalResponse
from app.modules.audit.models import AuditEvent
from app.modules.forms.config import config_for, text_errors
from app.modules.notifications.service import enqueue as enqueue_email
from app.modules.reviews import scoring
from app.modules.reviews.models import (
    Acknowledgement,
    FinalEvaluation,
    ManagerSubmission,
    Release,
    ReviewDraft,
    ReviewEvent,
)
from app.modules.reviews.schemas import EvaluationInput, ReleasedResult, ReviewResponse
from app.modules.users.models import RoleCode, User

REVIEWABLE = {"SUBMITTED", "UNDER_REVIEW"}


def assigned(db, appraisal_id, actor, command=None):
    query = select(Appraisal).where(
        Appraisal.id == appraisal_id,
        Appraisal.manager_id == actor.user.id,
        Appraisal.employee_id != actor.user.id,
    )
    appraisal = db.scalar(query)
    if not appraisal:
        raise AppError(404, "NOT_FOUND", "Assigned appraisal not found.")
    require_assigned_manager(actor.user, appraisal.employee_id, appraisal.manager_id)
    if command:
        db.scalar(
            select(Cycle)
            .where(Cycle.id == appraisal.cycle_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        employee_service.fresh_actor(db, actor, RoleCode.MANAGER)
        appraisal = db.scalar(query.with_for_update().execution_options(populate_existing=True))
        if not appraisal:
            raise AppError(404, "NOT_FOUND", "Assigned appraisal not found.")
        require_assigned_manager(actor.user, appraisal.employee_id, appraisal.manager_id)
        if appraisal.version != command.expected_version:
            raise AppError(409, "VERSION_CONFLICT", "The appraisal changed. Reload before continuing.")
        if appraisal.content_revision != command.submitted_revision:
            raise AppError(
                409,
                "REVISION_CONFLICT",
                "The employee has submitted a different revision. Reload the review.",
            )
        if db.get(Cycle, appraisal.cycle_id).state != "ACTIVE":
            raise AppError(409, "CYCLE_NOT_ACTIVE", "This cycle is not open for review actions.")
    return appraisal


def submitted(db, appraisal, lock=False):
    query = select(AppraisalRevision).where(
        AppraisalRevision.appraisal_id == appraisal.id,
        AppraisalRevision.revision == appraisal.content_revision,
    )
    if lock:
        query = query.with_for_update()
    revision = db.scalar(query)
    if not revision:
        raise AppError(404, "NOT_SUBMITTED", "This employee has not submitted an appraisal.")
    return revision.response_snapshot


def empty_evaluation(content, competency_count):
    return EvaluationInput(
        goals=[{} for _ in content["goals"]],
        contributions=[{} for _ in content["contributions"]],
        competencies=[{} for _ in range(competency_count)],
    )


def final_result(db, appraisal_id, lock=False):
    final = db.get(FinalEvaluation, appraisal_id, with_for_update=lock, populate_existing=lock)
    if not final:
        return None
    release = db.get(Release, appraisal_id, with_for_update=lock, populate_existing=lock)
    acknowledgement = db.get(Acknowledgement, appraisal_id, with_for_update=lock, populate_existing=lock)
    return ReleasedResult(
        appraisal_version=db.get(Appraisal, appraisal_id).version,
        submitted_revision=final.submitted_revision,
        identity_snapshot=final.employee_snapshot["identity"],
        form_definition=final.employee_snapshot["form_definition"],
        employee_responses=final.employee_snapshot["responses"],
        evaluation=final.evaluation,
        score=final.score,
        policy=final.policy,
        finalized_at=final.finalized_at,
        released_at=release.released_at if release else None,
        acknowledged_at=acknowledgement.acknowledged_at if acknowledgement else None,
    )


def detail(db, appraisal):
    content = submitted(db, appraisal)
    # Managers receive the submitted snapshot, never an employee's returned draft.
    personal = employee_service.detail(db, appraisal)
    personal = AppraisalResponse.model_validate({**personal.model_dump(), **content, "editable": False})
    draft = db.get(ReviewDraft, appraisal.id)
    current = bool(draft and draft.submitted_revision == appraisal.content_revision)
    final = final_result(db, appraisal.id)
    manager_submission = db.get(ManagerSubmission, appraisal.id)
    evaluation = (
        EvaluationInput.model_validate(manager_submission.evaluation)
        if manager_submission and not final
        else EvaluationInput.model_validate(draft.evaluation)
        if current
        else empty_evaluation(content, len(personal.form_definition["competencies"]))
    )
    version = db.get(Cycle, appraisal.cycle_id).scoring_policy_version
    rules = final.policy if final else scoring.policy(version, personal.form_definition)
    errors = (
        []
        if final
        else scoring.validation_errors(
            evaluation, content, len(personal.form_definition["competencies"]), personal.form_definition
        )
    )
    preview = (
        final.score
        if final
        else manager_submission.score
        if manager_submission
        else None
        if errors
        else scoring.calculate(
            evaluation,
            content,
            version,
            len(personal.form_definition["competencies"]),
            personal.form_definition,
        )
    )
    if final:
        evaluation = final.evaluation
    return ReviewResponse(
        appraisal=personal,
        submitted_revision=appraisal.content_revision,
        employee_responses=content,
        evaluation=evaluation,
        draft_is_current=current,
        final_result=final,
        policy=rules,
        validation_errors=errors,
        score_preview=preview,
    )


def transition(db, appraisal, actor, state, reason=None):
    previous = appraisal.state
    appraisal.state = state
    appraisal.version += 1
    db.add(
        AppraisalHistory(
            appraisal_id=appraisal.id,
            actor_id=actor.user.id,
            from_state=previous,
            to_state=state,
            reason=reason,
            appraisal_version=appraisal.version,
        )
    )
    db.add(AuditEvent(actor_id=actor.user.id, action=f"review.{state.lower()}", resource_id=appraisal.id))


def ensure_reviewable(appraisal):
    if appraisal.state not in REVIEWABLE:
        raise AppError(409, "INVALID_TRANSITION", "Only a submitted appraisal can be reviewed or returned.")


def begin(db, appraisal, actor):
    if appraisal.state != "SUBMITTED":
        raise AppError(409, "INVALID_TRANSITION", "Only a new submission can begin review.")
    submitted(db, appraisal, True)
    transition(db, appraisal, actor, "UNDER_REVIEW")
    db.commit()
    return detail(db, appraisal)


def save(db, appraisal, data, actor):
    ensure_reviewable(appraisal)
    content = submitted(db, appraisal, True)
    definition = employee_service.detail(db, appraisal).form_definition
    evaluation = data.evaluation
    config = config_for(definition)
    errors = text_errors(config, evaluation.extra_answers, "MANAGER")
    if errors:
        raise AppError(422, "INVALID_FORM_RESPONSES", " ".join(errors))
    allowed_na = {i for i, c in enumerate(config.competencies) if c.leadership}
    for section in ["goals", "contributions", "competencies"]:
        for index, entry in enumerate(getattr(evaluation, section)):
            if entry.not_applicable and (
                section != "competencies" or index not in allowed_na or entry.rating is not None
            ):
                raise AppError(
                    422,
                    "INVALID_APPLICABILITY",
                    "Only leadership can be N/A, and it cannot also have a rating.",
                )
    if (
        len(evaluation.goals) != len(content["goals"])
        or len(evaluation.contributions) != len(content["contributions"])
        or len(evaluation.competencies) != len(definition["competencies"])
    ):
        raise AppError(
            422, "ITEM_MISMATCH", "Rate exactly the submitted goals, contributions and workbook competencies."
        )
    if appraisal.state == "SUBMITTED":
        transition(db, appraisal, actor, "UNDER_REVIEW")
    else:
        appraisal.version += 1
    draft = db.get(ReviewDraft, appraisal.id, with_for_update=True, populate_existing=True)
    if not draft:
        draft = ReviewDraft(appraisal_id=appraisal.id)
        db.add(draft)
    draft.submitted_revision = appraisal.content_revision
    draft.evaluation = evaluation.model_dump()
    draft.updated_by = actor.user.id
    draft.updated_at = utcnow()
    db.add(
        ReviewEvent(
            appraisal_id=appraisal.id,
            appraisal_version=appraisal.version,
            submitted_revision=appraisal.content_revision,
            action="DRAFT_SAVED",
            evaluation=draft.evaluation,
            actor_id=actor.user.id,
        )
    )
    db.add(
        AuditEvent(
            actor_id=actor.user.id,
            action="review.draft_saved",
            resource_id=appraisal.id,
            details={"submitted_revision": appraisal.content_revision},
        )
    )
    db.commit()
    return detail(db, appraisal)


def return_for_revision(db, appraisal, data, actor):
    ensure_reviewable(appraisal)
    reason = data.reason.strip()
    if not reason:
        raise AppError(422, "REASON_REQUIRED", "Explain what the employee needs to revise.")
    if appraisal.state == "SUBMITTED":
        transition(db, appraisal, actor, "UNDER_REVIEW")
    transition(db, appraisal, actor, "RETURNED_FOR_REVISION", reason)
    employee = db.get(User, appraisal.employee_id)
    cycle = db.get(Cycle, appraisal.cycle_id)
    settings = db.info.get("settings")
    base_url = settings.public_base_url if settings and settings.public_base_url else "MyCareer"
    deadline = f"{cycle.submission_deadline:%d %b %Y, %H:%M} UTC"
    late_policy = (
        "Late submissions are allowed."
        if cycle.allow_late_submission
        else "Late submissions are not allowed."
    )
    enqueue_email(
        db,
        settings,
        f"Action needed: Revise your self-assessment — {cycle.title}",
        f"Hello {employee.full_name},\n\n{actor.user.full_name} returned your self-assessment for {cycle.title} for revision.\n\nManager feedback:\n{reason}\n\nPlease update your self-assessment and resubmit it in MyCareer: {base_url}\n\nCycle deadline: {deadline}. {late_policy}",
        [employee.email],
    )
    db.commit()
    return detail(db, appraisal)


def finalize(db, appraisal, data, actor):
    if appraisal.state != "UNDER_REVIEW":
        raise AppError(
            409,
            "INVALID_TRANSITION",
            "Save the manager review before finalization. Finalized reviews cannot be changed.",
        )
    content = submitted(db, appraisal, True)
    draft = db.get(ReviewDraft, appraisal.id, with_for_update=True, populate_existing=True)
    if not draft or draft.submitted_revision != appraisal.content_revision:
        raise AppError(409, "REVISION_CONFLICT", "Save a review for the current submitted revision first.")
    evaluation = EvaluationInput.model_validate(draft.evaluation)
    personal = employee_service.detail(db, appraisal)
    version = db.get(Cycle, appraisal.cycle_id).scoring_policy_version
    score = scoring.calculate(
        evaluation, content, version, len(personal.form_definition["competencies"]), personal.form_definition
    )
    db.add(
        ManagerSubmission(
            appraisal_id=appraisal.id,
            submitted_revision=appraisal.content_revision,
            employee_snapshot={
                "responses": content,
                "identity": appraisal.identity_snapshot,
                "form_definition": personal.form_definition,
            },
            evaluation=evaluation.model_dump(),
            score=score.model_dump(),
            policy=scoring.policy(version, personal.form_definition),
            submitted_by=actor.user.id,
        )
    )
    transition(
        db,
        appraisal,
        actor,
        "HR_REVIEW",
        "Manager submitted the evaluation to HR for calibration and approval",
    )
    db.add(
        ReviewEvent(
            appraisal_id=appraisal.id,
            appraisal_version=appraisal.version,
            submitted_revision=appraisal.content_revision,
            action="SUBMITTED_FOR_HR",
            evaluation=evaluation.model_dump(),
            actor_id=actor.user.id,
        )
    )
    admins = db.scalars(select(User).where(User.active.is_(True))).all()
    admins = [user for user in admins if RoleCode.SUPER_ADMIN in user.roles]
    employee = db.get(User, appraisal.employee_id)
    cycle = db.get(Cycle, appraisal.cycle_id)
    settings = db.info.get("settings")
    base_url = settings.public_base_url if settings and settings.public_base_url else "MyCareer"
    enqueue_email(
        db,
        settings,
        f"HR approval needed: {cycle.title}",
        f"Manager {actor.user.full_name} submitted the evaluation for {employee.full_name} ({employee.employee_id}) in {cycle.title}. Review and approve it in MyCareer: {base_url}",
        [user.email for user in admins],
    )
    db.commit()
    return detail(db, appraisal)


def release(db, appraisal, data, actor):
    if appraisal.state != "HR_APPROVED" or not db.get(FinalEvaluation, appraisal.id):
        raise AppError(
            409, "INVALID_TRANSITION", "HR approval is required before the manager can release an evaluation."
        )
    if not data.review_meeting_confirmed:
        raise AppError(
            422,
            "MEETING_REQUIRED",
            "Confirm that you discussed the HR-approved evaluation with the employee before releasing it.",
        )
    db.add(Release(appraisal_id=appraisal.id, released_by=actor.user.id))
    transition(
        db,
        appraisal,
        actor,
        "RELEASED",
        "Manager confirmed the post-approval review meeting with the employee before release",
    )
    db.add(
        AuditEvent(
            actor_id=actor.user.id,
            action="manager.release_meeting_confirmed",
            resource_id=appraisal.id,
            details={"review_meeting_confirmed": True},
        )
    )
    employee = db.get(User, appraisal.employee_id)
    cycle = db.get(Cycle, appraisal.cycle_id)
    settings = db.info.get("settings")
    base_url = settings.public_base_url if settings and settings.public_base_url else "MyCareer"
    enqueue_email(
        db,
        settings,
        f"Your evaluation is available: {cycle.title}",
        f"Hello {employee.full_name},\n\nYour manager has released your HR-approved evaluation for {cycle.title}. Sign in to MyCareer to view it: {base_url}",
        [employee.email],
    )
    db.commit()
    return detail(db, appraisal)


def released_to_owner(db, appraisal, lock=False):
    if appraisal.state != "RELEASED" or not db.get(
        Release, appraisal.id, with_for_update=lock, populate_existing=lock
    ):
        raise AppError(404, "NOT_RELEASED", "The evaluation has not been released to you.")
    result = final_result(db, appraisal.id, lock=lock)
    if not result:
        raise AppError(404, "NOT_RELEASED", "The evaluation has not been released to you.")
    return result


def acknowledge(db, appraisal_id, data, actor):
    appraisal = employee_service.owned(db, appraisal_id, actor)
    db.scalar(select(Cycle).where(Cycle.id == appraisal.cycle_id).with_for_update())
    employee_service.fresh_actor(db, actor)
    appraisal = db.scalar(
        select(Appraisal)
        .where(Appraisal.id == appraisal_id, Appraisal.employee_id == actor.user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not appraisal:
        raise AppError(404, "NOT_FOUND", "Appraisal not found.")
    released_to_owner(db, appraisal, lock=True)
    existing = db.get(Acknowledgement, appraisal_id, with_for_update=True, populate_existing=True)
    if existing:
        return released_to_owner(db, appraisal, lock=True)
    if appraisal.version != data.expected_version:
        raise AppError(409, "VERSION_CONFLICT", "The appraisal changed. Reload the released result.")
    db.add(Acknowledgement(appraisal_id=appraisal.id, employee_id=actor.user.id))
    appraisal.version += 1
    db.add(AuditEvent(actor_id=actor.user.id, action="appraisal.acknowledged", resource_id=appraisal.id))
    db.commit()
    return released_to_owner(db, appraisal, lock=True)
