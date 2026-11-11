from collections import Counter
from datetime import UTC

from sqlalchemy import delete, func, select

from app.api.dependencies import require_owner
from app.core.errors import AppError
from app.db.base import utcnow
from app.modules.appraisals.models import (
    Appraisal,
    AppraisalAttachment,
    AppraisalHistory,
    AppraisalItem,
    AppraisalRevision,
    Cycle,
    DevelopmentPlan,
    FormVersion,
    Participant,
)
from app.modules.appraisals.schemas import (
    AppraisalResponse,
    AppraisalSummary,
    CycleResponse,
    DevelopmentInput,
    SelfAssessmentInput,
)
from app.modules.audit.models import AuditEvent
from app.modules.forms.config import config_for, validate_employee
from app.modules.forms.text_limits import (
    HEADER_LIMIT,
    RESPONSE_LIMIT,
    TEXT_MINIMUM,
    exceeds_limit,
    is_single_character,
    validate_answer_lengths,
    validate_text_change,
)
from app.modules.notifications.service import enqueue as enqueue_email
from app.modules.users.models import RoleCode, User

FORM_VERSION = "workbook-ye2025-v1"
EDITABLE_STATES = {"DRAFT", "RETURNED_FOR_REVISION"}


def fresh_actor(db, actor, role=None):
    actor_id, credential_version = actor.user.id, actor.session.credential_version
    current = db.scalar(
        select(User).where(User.id == actor_id).with_for_update().execution_options(populate_existing=True)
    )
    db.expire(current, ["role_assignments"])
    if not current.active or current.credential_version != credential_version:
        raise AppError(401, "SESSION_EXPIRED", "Please sign in again.")
    if role and role not in current.roles:
        raise AppError(403, "FORBIDDEN", "You do not have access to this function.")
    return current


def cycle_response(db, cycle):
    ids = list(
        db.scalars(
            select(Participant.employee_id)
            .where(Participant.cycle_id == cycle.id)
            .order_by(Participant.employee_id)
        )
    )
    return CycleResponse(
        id=cycle.id,
        title=cycle.title,
        period_start=cycle.period_start,
        period_end=cycle.period_end,
        submission_deadline=cycle.submission_deadline,
        min_goals=cycle.min_goals,
        allow_late_submission=cycle.allow_late_submission,
        state=cycle.state,
        version=cycle.version,
        participant_ids=ids,
        scoring_policy_version=cycle.scoring_policy_version,
        form_version_id=cycle.form_version_id,
    )


def activate(db, cycle, actor):
    if cycle.state != "DRAFT":
        raise AppError(409, "INVALID_TRANSITION", "Only a draft cycle can be activated.")
    if cycle.submission_deadline <= utcnow():
        raise AppError(422, "PAST_DEADLINE", "Choose a future submission deadline before activation.")
    config = config_for(db.get(FormVersion, cycle.form_version_id).definition)
    if cycle.min_goals > config.goals_limit:
        raise AppError(422, "INVALID_FORM_MINIMUM", "The minimum goals exceed this form limit.")
    ids = list(db.scalars(select(Participant.employee_id).where(Participant.cycle_id == cycle.id)))
    if not ids:
        raise AppError(422, "NO_PARTICIPANTS", "Select at least one participant.")
    people = {u.id: u for u in db.scalars(select(User).where(User.id.in_(ids)))}
    for person_id in sorted(ids):
        person = people.get(person_id)
        manager = db.get(User, person.manager_id) if person and person.manager_id else None
        if (
            not person
            or not person.active
            or not manager
            or not manager.active
            or RoleCode.MANAGER not in manager.roles
            or manager.id == person.id
        ):
            raise AppError(
                422,
                "INVALID_PARTICIPANT",
                "Every participant needs an active account and an active, separate reporting manager with the Manager role.",
            )
        appraisal = Appraisal(
            employee_id=person.id,
            cycle_id=cycle.id,
            manager_id=manager.id,
            form_version_id=cycle.form_version_id,
            identity_snapshot={
                "employee_name": person.full_name,
                "employee_id": person.employee_id,
                "email": person.email,
                "department": person.department,
                "designation": person.designation,
                "country": person.country,
                "manager_name": manager.full_name,
            },
        )
        db.add(appraisal)
        db.flush()
        db.add(DevelopmentPlan(appraisal_id=appraisal.id))
        db.add(
            AppraisalHistory(
                appraisal_id=appraisal.id,
                actor_id=actor.user.id,
                from_state=None,
                to_state="DRAFT",
                reason="Cycle activated",
                appraisal_version=1,
            )
        )
    cycle.state = "ACTIVE"
    cycle.version += 1
    settings = db.info.get("settings")
    base_url = settings.public_base_url if settings and settings.public_base_url else "MyCareer"
    for person_id in ids:
        person = people[person_id]
        manager = people.get(person.manager_id) or db.get(User, person.manager_id)
        enqueue_email(
            db,
            settings,
            f"Action needed: {cycle.title} appraisal is open",
            f"Hello {person.full_name},\n\nYour appraisal cycle {cycle.title} is open. Please complete and submit your self-assessment by {cycle.submission_deadline:%d %b %Y, %H:%M} UTC.\n\nOpen MyCareer: {base_url}",
            [person.email],
            [manager.email] if manager else (),
        )
    db.add(
        AuditEvent(
            actor_id=actor.user.id,
            action="cycle.activated",
            resource_id=cycle.id,
            details={"participants": len(ids), "form_version": cycle.form_version_id},
        )
    )


def owned(db, appraisal_id, actor, write=False, expected_version=None):
    appraisal = db.scalar(
        select(Appraisal).where(Appraisal.id == appraisal_id, Appraisal.employee_id == actor.user.id)
    )
    if not appraisal:
        raise AppError(404, "NOT_FOUND", "Appraisal not found.")
    if write:
        db.scalar(
            select(Cycle)
            .where(Cycle.id == appraisal.cycle_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        fresh_actor(db, actor)
        appraisal = db.scalar(
            select(Appraisal)
            .where(Appraisal.id == appraisal_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        require_owner(actor.user, appraisal.employee_id)
        if appraisal.version != expected_version:
            raise AppError(
                409, "VERSION_CONFLICT", "Your appraisal changed in another window. Reload before continuing."
            )
        if appraisal.state not in EDITABLE_STATES:
            raise AppError(409, "APPRAISAL_READ_ONLY", "Submitted or finalized appraisals cannot be edited.")
        if db.get(Cycle, appraisal.cycle_id).state != "ACTIVE":
            raise AppError(409, "CYCLE_NOT_ACTIVE", "This appraisal cycle is not open for changes.")
    return appraisal


def summary(db, appraisal):
    cycle = db.get(Cycle, appraisal.cycle_id)
    return AppraisalSummary(
        id=appraisal.id,
        cycle_id=cycle.id,
        cycle_title=cycle.title,
        period_start=cycle.period_start,
        period_end=cycle.period_end,
        state=appraisal.state,
        version=appraisal.version,
        manager_name=appraisal.identity_snapshot["manager_name"],
        submission_deadline=cycle.submission_deadline,
        started_at=appraisal.started_at,
        submitted_at=appraisal.submitted_at,
    )


def responses(db, appraisal, lock=False):
    query = (
        select(AppraisalItem)
        .where(AppraisalItem.appraisal_id == appraisal.id)
        .order_by(AppraisalItem.position)
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    items = db.scalars(query).all()
    plan = db.get(DevelopmentPlan, appraisal.id, with_for_update=lock, populate_existing=lock)
    return {
        "goals": [
            {"description": i.description, "employee_narrative": i.employee_narrative}
            for i in items
            if i.kind == "GOAL"
        ],
        "contributions": [
            {"description": i.description, "employee_narrative": i.employee_narrative}
            for i in items
            if i.kind == "CONTRIBUTION"
        ],
        "development": DevelopmentInput.model_validate(plan, from_attributes=True).model_dump(),
    }


def detail(db, appraisal, *, include_draft_save_time=False):
    cycle = db.get(Cycle, appraisal.cycle_id)
    definition = db.get(FormVersion, appraisal.form_version_id).definition
    last_draft_saved_at = None
    if include_draft_save_time:
        last_draft_saved_at = db.scalar(
            select(func.max(AuditEvent.occurred_at)).where(
                AuditEvent.resource_id == appraisal.id,
                AuditEvent.actor_id == appraisal.employee_id,
                AuditEvent.action == "appraisal.draft_saved",
            )
        )
    return_reason = None
    if appraisal.state == "RETURNED_FOR_REVISION":
        return_reason = db.scalar(
            select(AppraisalHistory.reason)
            .where(
                AppraisalHistory.appraisal_id == appraisal.id,
                AppraisalHistory.to_state == "RETURNED_FOR_REVISION",
            )
            .order_by(
                AppraisalHistory.appraisal_version.desc(),
                AppraisalHistory.occurred_at.desc(),
                AppraisalHistory.id,
            )
            .limit(1)
        )
    return AppraisalResponse(
        **summary(db, appraisal).model_dump(),
        last_draft_saved_at=last_draft_saved_at.replace(tzinfo=UTC) if last_draft_saved_at else None,
        identity_snapshot=appraisal.identity_snapshot,
        content_revision=appraisal.content_revision,
        form_definition=definition,
        min_goals=cycle.min_goals,
        allow_late_submission=cycle.allow_late_submission,
        **responses(db, appraisal),
        editable=appraisal.state in EDITABLE_STATES and cycle.state == "ACTIVE",
        return_reason=return_reason,
    )


def validate_item_lengths(db, appraisal, items, kind, title_limit, response_limit):
    fields = (
        ("description", "title", title_limit),
        ("employee_narrative", "achievement description", response_limit),
    )
    over_limit = []
    for number, item in enumerate(items, 1):
        for field, label, limit in fields:
            text = getattr(item, field)
            if exceeds_limit(text, limit):
                over_limit.append((number, field, label, limit, text))
    if not over_limit:
        return
    # Allow existing over-limit values to survive saves and row reordering without allowing copies.
    saved = db.execute(
        select(AppraisalItem.description, AppraisalItem.employee_narrative)
        .where(AppraisalItem.appraisal_id == appraisal.id, AppraisalItem.kind == kind)
        .with_for_update()
    )
    existing = Counter((field, getattr(row, field)) for row in saved for field, _, _ in fields)
    for number, field, label, limit, text in over_limit:
        key = (field, text)
        if existing[key] == 0:
            raise AppError(
                422,
                f"{kind}_TEXT_LIMIT",
                f"{kind.title()} {number} {label} must be {limit} characters or fewer.",
            )
        existing[key] -= 1


def save_draft(db, appraisal, data: SelfAssessmentInput, actor):
    config = config_for(db.get(FormVersion, appraisal.form_version_id).definition)
    validate_employee(config, data)
    validate_item_lengths(
        db, appraisal, data.goals, "GOAL", config.goal_title_max_length, config.goal_description_max_length
    )
    validate_item_lengths(db, appraisal, data.contributions, "CONTRIBUTION", HEADER_LIMIT, RESPONSE_LIMIT)
    plan = db.get(DevelopmentPlan, appraisal.id, with_for_update=True, populate_existing=True)
    development = data.development.model_dump(exclude={"extra_answers"})
    for key, value in development.items():
        validate_text_change(value, getattr(plan, key), key.replace("_", " ").capitalize())
    validate_answer_lengths(data.development.extra_answers, plan.extra_answers or {})

    db.execute(delete(AppraisalItem).where(AppraisalItem.appraisal_id == appraisal.id))
    for kind, entries in [("GOAL", data.goals), ("CONTRIBUTION", data.contributions)]:
        for position, entry in enumerate(entries, start=1):
            if not entry.description.strip() and not entry.employee_narrative.strip():
                continue
            db.add(
                AppraisalItem(
                    appraisal_id=appraisal.id,
                    kind=kind,
                    position=position,
                    description=entry.description,
                    employee_narrative=entry.employee_narrative,
                )
            )
    for key, value in development.items():
        setattr(plan, key, value)
    plan.extra_answers = data.development.extra_answers
    appraisal.started_at = appraisal.started_at or utcnow()
    appraisal.version += 1
    db.add(AuditEvent(actor_id=actor.user.id, action="appraisal.draft_saved", resource_id=appraisal.id))
    db.commit()
    return detail(db, appraisal, include_draft_save_time=True)


def submit(db, appraisal, actor):
    cycle = db.get(Cycle, appraisal.cycle_id)
    if not cycle.allow_late_submission and utcnow() > cycle.submission_deadline:
        raise AppError(409, "SUBMISSION_DEADLINE_PASSED", "The submission deadline has passed. Contact HR.")
    # Locking reads avoid stale content from the ownership lookup's earlier
    # repeatable-read snapshot after waiting for a concurrent draft save.
    snapshot = responses(db, appraisal, lock=True)
    validation = SelfAssessmentInput(expected_version=appraisal.version, **snapshot)
    config = config_for(db.get(FormVersion, appraisal.form_version_id).definition)
    validate_employee(config, validation, True)
    if len(snapshot["goals"]) < cycle.min_goals:
        raise AppError(
            422, "INCOMPLETE_APPRAISAL", f"Complete at least {cycle.min_goals} goal(s) before submitting."
        )
    for item in snapshot["goals"] + snapshot["contributions"]:
        if not item["description"].strip() or not item["employee_narrative"].strip():
            raise AppError(
                422,
                "INCOMPLETE_APPRAISAL",
                "Each entered goal or contribution needs a title and an achievement description or NA.",
            )
        if any(is_single_character(value) for value in item.values()):
            raise AppError(
                422,
                "INCOMPLETE_APPRAISAL",
                f"Each entered goal or contribution field needs at least {TEXT_MINIMUM} characters.",
            )
    if config.development_enabled:
        missing = [
            key.replace("_", " ")
            for key, value in validation.development.model_dump(exclude={"extra_answers"}).items()
            if len(value.strip()) < TEXT_MINIMUM
        ]
        if missing:
            raise AppError(
                422,
                "INCOMPLETE_APPRAISAL",
                f"Enter at least {TEXT_MINIMUM} characters or NA in Achievements and development for: {', '.join(missing)}.",
            )
    manager = db.get(User, appraisal.manager_id)
    if (
        not manager
        or not manager.active
        or RoleCode.MANAGER not in manager.roles
        or manager.id == appraisal.employee_id
    ):
        raise AppError(409, "REVIEWER_UNAVAILABLE", "Your assigned reviewer is unavailable. Contact HR.")
    previous = appraisal.state
    appraisal.content_revision += 1
    appraisal.state = "SUBMITTED"
    appraisal.version += 1
    appraisal.started_at = appraisal.started_at or utcnow()
    appraisal.submitted_at = utcnow()
    db.query(AppraisalAttachment).filter(
        AppraisalAttachment.appraisal_id == appraisal.id,
        AppraisalAttachment.submitted_revision.is_(None),
        AppraisalAttachment.deleted_at.is_(None),
    ).update({AppraisalAttachment.submitted_revision: appraisal.content_revision}, synchronize_session=False)
    db.add(
        AppraisalRevision(
            appraisal_id=appraisal.id,
            revision=appraisal.content_revision,
            response_snapshot=snapshot,
            submitted_by=actor.user.id,
        )
    )
    db.add(
        AppraisalHistory(
            appraisal_id=appraisal.id,
            actor_id=actor.user.id,
            from_state=previous,
            to_state="SUBMITTED",
            appraisal_version=appraisal.version,
        )
    )
    db.add(
        AuditEvent(
            actor_id=actor.user.id,
            action="appraisal.submitted",
            resource_id=appraisal.id,
            details={"revision": appraisal.content_revision},
        )
    )
    settings = db.info.get("settings")
    base_url = settings.public_base_url if settings and settings.public_base_url else "MyCareer"
    manager = db.get(User, appraisal.manager_id)
    employee = db.get(User, appraisal.employee_id)
    cycle = db.get(Cycle, appraisal.cycle_id)
    enqueue_email(
        db,
        settings,
        f"Employee appraisal submitted: {cycle.title}",
        f"{employee.full_name} submitted a self-assessment for {cycle.title}. Please review it in MyCareer: {base_url}\n\nIf you feel the self-assessment needs changes, you can return it to the employee for revision from the review screen.",
        [manager.email] if manager else [],
    )
    db.commit()
    return detail(db, appraisal, include_draft_save_time=True)
