import hashlib
import hmac
import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import Identity, csrf, get_db, require_role
from app.core.errors import AppError
from app.db.base import utcnow
from app.modules.appraisals.models import Appraisal, Cycle
from app.modules.audit.models import AuditEvent
from app.modules.auth.schemas import StrictInput
from app.modules.notifications.models import CycleReminderSettings, ScheduledReminder
from app.modules.notifications.service import enqueue
from app.modules.users.models import RoleCode, User, UserRole
from app.modules.users.service import admin_transaction

router = APIRouter(
    prefix="/hr/cycle-reminders",
    tags=["HR cycle reminders"],
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN))],
)

Stage = Literal["employee", "manager", "hr"]
Audience = Literal["pending", "all"]
Offset = Literal[8, 24, 72, 168]

STAGES = {
    "employee": ("self-assessments", "personal", {"DRAFT", "RETURNED_FOR_REVISION"}),
    "manager": ("manager reviews", "team", {"SUBMITTED", "UNDER_REVIEW"}),
    "hr": ("HR calibrations", "calibrations", {"HR_REVIEW"}),
}


class ReminderSettingsInput(StrictInput):
    expected_version: int = Field(ge=0)
    manager_deadline: AwareDatetime | None = None
    hr_deadline: AwareDatetime | None = None
    hours_before: list[Offset] = Field(max_length=4)


class ReminderSettingsResponse(BaseModel):
    state: str
    employee_deadline: datetime
    manager_deadline: datetime | None
    hr_deadline: datetime | None
    hours_before: list[Offset]
    version: int


class ReminderSelection(StrictInput):
    stage: Stage
    audience: Audience = "pending"


class ReminderSend(ReminderSelection):
    request_id: UUID
    fingerprint: str = Field(min_length=64, max_length=64)


class ReminderPreview(BaseModel):
    request_id: UUID
    fingerprint: str
    recipient_count: int
    subject: str
    body: str
    mail_mode: Literal["disabled", "test", "live"]


class ReminderSent(BaseModel):
    queued: int


def get_cycle(db, cycle_id, *, lock=False):
    query = select(Cycle).where(Cycle.id == cycle_id)
    cycle = db.scalar(query.with_for_update() if lock else query)
    if cycle is None:
        raise AppError(404, "NOT_FOUND", "Appraisal cycle not found.")
    return cycle


def settings_response(cycle, config):
    return ReminderSettingsResponse(
        state=cycle.state,
        employee_deadline=cycle.submission_deadline,
        manager_deadline=config.manager_deadline if config else None,
        hr_deadline=config.hr_deadline if config else None,
        hours_before=config.hours_before if config else [],
        version=config.version if config else 0,
    )


@router.get("/{cycle_id}/settings", response_model=ReminderSettingsResponse)
def read_settings(cycle_id: str, db: Session = Depends(get_db)):
    return settings_response(get_cycle(db, cycle_id), db.get(CycleReminderSettings, cycle_id))


@router.put("/{cycle_id}/settings", response_model=ReminderSettingsResponse)
def save_settings(
    cycle_id: str,
    data: ReminderSettingsInput,
    actor: Identity = Depends(csrf),
    db: Session = Depends(get_db),
):
    admin_transaction(db, actor)
    cycle = get_cycle(db, cycle_id, lock=True)
    if cycle.state not in {"DRAFT", "ACTIVE"}:
        raise AppError(409, "CYCLE_CLOSED", "Reminder settings can be edited for draft and active cycles.")
    config = db.get(CycleReminderSettings, cycle_id)
    version = config.version if config else 0
    if version != data.expected_version:
        raise AppError(409, "VERSION_CONFLICT", "Reminder settings changed. Reload before saving.")
    manager = data.manager_deadline.astimezone(UTC).replace(tzinfo=None) if data.manager_deadline else None
    hr = data.hr_deadline.astimezone(UTC).replace(tzinfo=None) if data.hr_deadline else None
    if (manager and manager <= cycle.submission_deadline) or (
        hr and hr <= (manager or cycle.submission_deadline)
    ):
        raise AppError(
            422, "INVALID_DEADLINES", "Set reminder deadlines in order: employee, manager, then HR."
        )
    if config is None:
        config = CycleReminderSettings(cycle_id=cycle_id)
        db.add(config)
    config.manager_deadline = manager
    config.hr_deadline = hr
    config.hours_before = sorted(set(data.hours_before), reverse=True)
    config.version = version + 1
    db.add(AuditEvent(actor_id=actor.user.id, action="cycle.reminder_settings_changed", resource_id=cycle_id))
    db.commit()
    return settings_response(cycle, config)


def recipients(db, cycle, stage, audience):
    pending_states = STAGES[stage][2]
    rows = db.execute(
        select(Appraisal.employee_id, Appraisal.manager_id, Appraisal.state).where(
            Appraisal.cycle_id == cycle.id
        )
    ).all()
    counts = Counter()
    if stage == "hr":
        pending = [row for row in rows if row.state in pending_states]
        if audience == "pending" and not pending:
            return []
        own = Counter(row.employee_id for row in pending)
        users = db.scalars(
            select(User)
            .join(UserRole)
            .where(
                User.active.is_(True),
                UserRole.role_code == RoleCode.SUPER_ADMIN,
            )
            .order_by(User.email)
        )
        return [
            (user.email, len(pending) - own[user.id])
            for user in users
            if audience == "all" or len(pending) > own[user.id]
        ]

    for employee_id, manager_id, state in rows:
        if stage == "manager" and employee_id == manager_id:
            continue
        pending = state in pending_states
        if pending or audience == "all":
            counts[employee_id if stage == "employee" else manager_id] += int(pending)
    query = select(User).where(User.id.in_(counts), User.active.is_(True))
    if stage == "manager":
        query = query.join(UserRole).where(UserRole.role_code == RoleCode.MANAGER)
    return [(user.email, counts[user.id]) for user in db.scalars(query.order_by(User.email))]


def deadline_for(cycle, config, stage):
    if stage == "employee":
        return cycle.submission_deadline
    if config is not None:
        return config.manager_deadline if stage == "manager" else config.hr_deadline
    return None


def reminder_email(settings, cycle, stage, deadline, count):
    task, view, _ = STAGES[stage]
    title = " ".join(cycle.title.split())
    subject = f"MyCareer reminder for {task} · {title}"
    body = f"Appraisal cycle: {title}\n\nPending {task}: {count}. Please complete any outstanding work in MyCareer."
    if deadline:
        body += f"\nDeadline: {deadline:%d %b %Y, %H:%M} UTC."
    if stage == "employee" and deadline and deadline <= utcnow() and not cycle.allow_late_submission:
        body += "\nThe submission window has closed. Contact HR if you still need to submit."
    if settings.public_base_url:
        body += f"\n\nOpen MyCareer: {settings.public_base_url.rstrip('/')}/?view={view}"
    if settings.alternate_public_base_url:
        body += f"\nAlternate address: {settings.alternate_public_base_url.rstrip('/')}/?view={view}"
    return subject, body


def prepare(db, settings, cycle, selection, request_id, actor_id):
    if cycle.state != "ACTIVE":
        raise AppError(409, "CYCLE_NOT_ACTIVE", "Activate this cycle before sending reminders.")
    config = db.get(CycleReminderSettings, cycle.id)
    deadline = deadline_for(cycle, config, selection.stage)
    roster = recipients(db, cycle, selection.stage, selection.audience)
    subject, body = reminder_email(settings, cycle, selection.stage, deadline, "[your count]")
    mode = "disabled" if not settings.mail_enabled else "test" if settings.mail_test_mode else "live"
    payload = json.dumps(
        [
            str(request_id),
            actor_id,
            cycle.id,
            selection.stage,
            selection.audience,
            roster,
            subject,
            body,
            mode,
        ]
    )
    fingerprint = hmac.new(
        settings.secret_key.get_secret_value().encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    preview = ReminderPreview(
        request_id=request_id,
        fingerprint=fingerprint,
        recipient_count=len(roster),
        subject=subject,
        body=body,
        mail_mode=mode,
    )
    return preview, roster, deadline


@router.post("/{cycle_id}/preview", response_model=ReminderPreview)
def preview_reminder(
    cycle_id: str,
    data: ReminderSelection,
    request: Request,
    actor: Identity = Depends(csrf),
    db: Session = Depends(get_db),
):
    result, _, _ = prepare(
        db, request.app.state.settings, get_cycle(db, cycle_id), data, uuid4(), actor.user.id
    )
    return result


def queue_messages(db, settings, cycle, stage, deadline, roster):
    for email, count in roster:
        subject, body = reminder_email(settings, cycle, stage, deadline, count)
        enqueue(db, settings, subject, body, [email])


@router.post("/{cycle_id}/send", response_model=ReminderSent)
def send_reminder(
    cycle_id: str,
    data: ReminderSend,
    request: Request,
    actor: Identity = Depends(csrf),
    db: Session = Depends(get_db),
):
    admin_transaction(db, actor)
    request_id = str(data.request_id)
    previous = db.get(AuditEvent, request_id)
    if previous is not None:
        if (
            previous.action == "cycle.reminder_sent"
            and previous.actor_id == actor.user.id
            and previous.resource_id == cycle_id
        ):
            return ReminderSent(queued=previous.details["queued"])
        raise AppError(409, "REQUEST_CONFLICT", "Preview the reminder again before sending.")
    settings = request.app.state.settings
    if not settings.mail_enabled:
        raise AppError(409, "MAIL_DISABLED", "Email delivery is disabled for MyCareer.")
    cycle = get_cycle(db, cycle_id, lock=True)
    preview, roster, deadline = prepare(db, settings, cycle, data, data.request_id, actor.user.id)
    if not hmac.compare_digest(preview.fingerprint, data.fingerprint):
        raise AppError(409, "REMINDER_CHANGED", "The reminder or recipient list changed. Preview it again.")
    queue_messages(db, settings, cycle, data.stage, deadline, roster)
    db.add(
        AuditEvent(
            id=request_id,
            actor_id=actor.user.id,
            action="cycle.reminder_sent",
            resource_id=cycle.id,
            details={
                "stage": data.stage,
                "audience": data.audience,
                "queued": len(roster),
                "mail_mode": preview.mail_mode,
            },
        )
    )
    db.commit()
    return ReminderSent(queued=len(roster))


def queue_scheduled_reminders(sessions, settings, now=None):
    if not settings.mail_enabled:
        return
    now = now if now is not None else utcnow()
    with sessions() as db:
        cycle_ids = db.scalars(
            select(Cycle.id).join(CycleReminderSettings).where(Cycle.state == "ACTIVE")
        ).all()
    for cycle_id in cycle_ids:
        with sessions.begin() as db:
            cycle = get_cycle(db, cycle_id, lock=True)
            config = db.get(CycleReminderSettings, cycle_id)
            if cycle.state != "ACTIVE" or not config or not config.hours_before:
                continue
            for stage in STAGES:
                deadline = deadline_for(cycle, config, stage)
                if not deadline or deadline <= now:
                    continue
                due = [hours for hours in config.hours_before if deadline - timedelta(hours=hours) <= now]
                if not due:
                    continue
                hours = min(due)
                if db.get(ScheduledReminder, (cycle_id, stage, deadline, hours)) is not None:
                    continue
                roster = recipients(db, cycle, stage, "pending")
                if not roster:
                    continue
                queue_messages(db, settings, cycle, stage, deadline, roster)
                db.add(
                    ScheduledReminder(cycle_id=cycle_id, stage=stage, deadline=deadline, hours_before=hours)
                )
