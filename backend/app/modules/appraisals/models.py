import uuid
from datetime import date, datetime

from sqlalchemy import JSON, CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


def identifier():
    return str(uuid.uuid4())


class FormVersion(Base):
    __tablename__ = "appraisal_form_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_sha256: Mapped[str] = mapped_column(String(64))
    definition: Mapped[dict] = mapped_column(JSON)


class Cycle(Base):
    __tablename__ = "appraisal_cycles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    title: Mapped[str] = mapped_column(String(150))
    period_start: Mapped[date]
    period_end: Mapped[date]
    submission_deadline: Mapped[datetime]
    min_goals: Mapped[int]
    allow_late_submission: Mapped[bool] = mapped_column(default=False)
    form_version_id: Mapped[str] = mapped_column(
        ForeignKey("appraisal_form_versions.id", ondelete="RESTRICT")
    )
    state: Mapped[str] = mapped_column(String(20), default="DRAFT")
    version: Mapped[int] = mapped_column(default=1)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    scoring_policy_version: Mapped[str] = mapped_column(
        String(40), default="mi-2026-10-20-v1", server_default="mi-2026-10-20-v1"
    )
    __table_args__ = (CheckConstraint("min_goals BETWEEN 1 AND 5", name="min_goals"),)


class Participant(Base):
    __tablename__ = "cycle_participants"
    cycle_id: Mapped[str] = mapped_column(
        ForeignKey("appraisal_cycles.id", ondelete="RESTRICT"), primary_key=True
    )
    employee_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)


class Appraisal(Base):
    __tablename__ = "appraisals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    employee_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    cycle_id: Mapped[str] = mapped_column(ForeignKey("appraisal_cycles.id", ondelete="RESTRICT"), index=True)
    manager_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    form_version_id: Mapped[str] = mapped_column(
        ForeignKey("appraisal_form_versions.id", ondelete="RESTRICT")
    )
    identity_snapshot: Mapped[dict] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String(30), default="DRAFT")
    version: Mapped[int] = mapped_column(default=1)
    content_revision: Mapped[int] = mapped_column(default=0)
    started_at: Mapped[datetime | None]
    submitted_at: Mapped[datetime | None]
    __table_args__ = (UniqueConstraint("employee_id", "cycle_id", name="uq_employee_cycle"),)


class AppraisalItem(Base):
    __tablename__ = "appraisal_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    appraisal_id: Mapped[str] = mapped_column(ForeignKey("appraisals.id", ondelete="RESTRICT"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    position: Mapped[int]
    description: Mapped[str] = mapped_column(Text)
    employee_narrative: Mapped[str] = mapped_column(Text)
    __table_args__ = (
        UniqueConstraint("appraisal_id", "kind", "position", name="uq_appraisal_item_position"),
    )


class DevelopmentPlan(Base):
    __tablename__ = "development_plans"
    appraisal_id: Mapped[str] = mapped_column(
        ForeignKey("appraisals.id", ondelete="RESTRICT"), primary_key=True
    )
    business_achievements: Mapped[str] = mapped_column(Text, default="")
    development_achievements: Mapped[str] = mapped_column(Text, default="")
    six_month_growth: Mapped[str] = mapped_column(Text, default="")
    development_needs: Mapped[str] = mapped_column(Text, default="")
    development_plan: Mapped[str] = mapped_column(Text, default="")
    support_requested: Mapped[str] = mapped_column(Text, default="")
    extra_answers: Mapped[dict | None] = mapped_column(JSON, default=dict)


class AppraisalRevision(Base):
    __tablename__ = "appraisal_revisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    appraisal_id: Mapped[str] = mapped_column(ForeignKey("appraisals.id", ondelete="RESTRICT"), index=True)
    revision: Mapped[int]
    response_snapshot: Mapped[dict] = mapped_column(JSON)
    submitted_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    submitted_at: Mapped[datetime] = mapped_column(default=utcnow)
    __table_args__ = (UniqueConstraint("appraisal_id", "revision", name="uq_appraisal_revision"),)


class AppraisalAttachment(Base):
    __tablename__ = "appraisal_attachments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    appraisal_id: Mapped[str] = mapped_column(ForeignKey("appraisals.id", ondelete="RESTRICT"), index=True)
    uploader_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    original_name: Mapped[str] = mapped_column(String(255))
    object_key: Mapped[str] = mapped_column(String(80), unique=True)
    media_type: Mapped[str] = mapped_column(String(100))
    byte_size: Mapped[int]
    uploaded_at: Mapped[datetime] = mapped_column(default=utcnow)
    submitted_revision: Mapped[int | None]
    deleted_at: Mapped[datetime | None]


class AppraisalHistory(Base):
    __tablename__ = "appraisal_history"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    appraisal_id: Mapped[str] = mapped_column(ForeignKey("appraisals.id", ondelete="RESTRICT"), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    from_state: Mapped[str | None] = mapped_column(String(30))
    to_state: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(default=utcnow)
    appraisal_version: Mapped[int] = mapped_column(default=0, server_default="0")
