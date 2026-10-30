from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow
from app.modules.appraisals.models import identifier


class FormTemplate(Base):
    __tablename__ = "form_templates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    name: Mapped[str] = mapped_column(String(150))
    config: Mapped[dict] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(default=1)
    published_form_id: Mapped[str | None] = mapped_column(
        ForeignKey("appraisal_form_versions.id", ondelete="RESTRICT")
    )
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)
