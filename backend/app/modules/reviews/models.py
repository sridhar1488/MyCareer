"""Mutable review drafts and immutable sign-off artifacts are separate records."""

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow
from app.modules.appraisals.models import identifier


class ReviewDraft(Base):
    __tablename__ = "manager_review_drafts"
    appraisal_id: Mapped[str] = mapped_column(
        ForeignKey("appraisals.id", ondelete="RESTRICT"), primary_key=True
    )
    submitted_revision: Mapped[int]
    evaluation: Mapped[dict] = mapped_column(JSON)
    updated_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)


class ReviewEvent(Base):
    __tablename__ = "manager_review_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    appraisal_id: Mapped[str] = mapped_column(ForeignKey("appraisals.id", ondelete="RESTRICT"), index=True)
    appraisal_version: Mapped[int]
    submitted_revision: Mapped[int]
    action: Mapped[str] = mapped_column(String(30))
    evaluation: Mapped[dict] = mapped_column(JSON)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    occurred_at: Mapped[datetime] = mapped_column(default=utcnow)


class ManagerSubmission(Base):
    """The manager's unaltered sign-off, preserved before HR calibration."""

    __tablename__ = "manager_submissions"
    appraisal_id: Mapped[str] = mapped_column(
        ForeignKey("appraisals.id", ondelete="RESTRICT"), primary_key=True
    )
    submitted_revision: Mapped[int]
    employee_snapshot: Mapped[dict] = mapped_column(JSON)
    evaluation: Mapped[dict] = mapped_column(JSON)
    score: Mapped[dict] = mapped_column(JSON)
    policy: Mapped[dict] = mapped_column(JSON)
    submitted_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    submitted_at: Mapped[datetime] = mapped_column(default=utcnow)


class CalibrationDraft(Base):
    __tablename__ = "hr_calibration_drafts"
    appraisal_id: Mapped[str] = mapped_column(
        ForeignKey("appraisals.id", ondelete="RESTRICT"), primary_key=True
    )
    evaluation: Mapped[dict] = mapped_column(JSON)
    score: Mapped[dict] = mapped_column(JSON)
    updated_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)


class CalibrationEvent(Base):
    __tablename__ = "hr_calibration_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    appraisal_id: Mapped[str] = mapped_column(ForeignKey("appraisals.id", ondelete="RESTRICT"), index=True)
    appraisal_version: Mapped[int]
    evaluation: Mapped[dict] = mapped_column(JSON)
    score: Mapped[dict] = mapped_column(JSON)
    action: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(2000), default="")
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    occurred_at: Mapped[datetime] = mapped_column(default=utcnow)


class FinalEvaluation(Base):
    __tablename__ = "final_evaluations"
    appraisal_id: Mapped[str] = mapped_column(
        ForeignKey("appraisals.id", ondelete="RESTRICT"), primary_key=True
    )
    submitted_revision: Mapped[int]
    employee_snapshot: Mapped[dict] = mapped_column(JSON)
    evaluation: Mapped[dict] = mapped_column(JSON)
    score: Mapped[dict] = mapped_column(JSON)
    policy: Mapped[dict] = mapped_column(JSON)
    finalized_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    finalized_at: Mapped[datetime] = mapped_column(default=utcnow)


class Release(Base):
    __tablename__ = "appraisal_releases"
    appraisal_id: Mapped[str] = mapped_column(
        ForeignKey("final_evaluations.appraisal_id", ondelete="RESTRICT"), primary_key=True
    )
    released_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    released_at: Mapped[datetime] = mapped_column(default=utcnow)


class Acknowledgement(Base):
    __tablename__ = "appraisal_acknowledgements"
    appraisal_id: Mapped[str] = mapped_column(
        ForeignKey("appraisal_releases.appraisal_id", ondelete="RESTRICT"), primary_key=True
    )
    employee_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    acknowledged_at: Mapped[datetime] = mapped_column(default=utcnow)
