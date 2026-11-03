import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow


class RoleCode(enum.StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    HR = "HR"
    MANAGER = "MANAGER"
    EMPLOYEE = "EMPLOYEE"


class Role(Base):
    __tablename__ = "roles"
    code: Mapped[str] = mapped_column(String(20), primary_key=True)


class OperatorGuard(Base):
    __tablename__ = "operator_guard"
    id: Mapped[int] = mapped_column(primary_key=True)


class UserRole(Base):
    __tablename__ = "user_roles"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    role_code: Mapped[str] = mapped_column(ForeignKey("roles.code", ondelete="RESTRICT"), primary_key=True)


class Department(Base):
    __tablename__ = "departments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), unique=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    employee_id: Mapped[str] = mapped_column(String(40), unique=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    full_name: Mapped[str] = mapped_column(String(150))
    department: Mapped[str] = mapped_column(String(100), default="")
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"))
    manager_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    version: Mapped[int] = mapped_column(default=1, server_default="1")
    designation: Mapped[str] = mapped_column(String(100), default="")
    country: Mapped[str] = mapped_column(String(80), default="")
    location: Mapped[str] = mapped_column(String(120), default="", server_default="")
    date_joined: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    credential_version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_login_at: Mapped[datetime | None]
    role_assignments: Mapped[list[UserRole]] = relationship(lazy="selectin")

    @property
    def roles(self) -> list[str]:
        return sorted(r.role_code for r in self.role_assignments)


class ReportingRelationship(Base):
    __tablename__ = "reporting_relationships"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    employee_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    manager_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    valid_from: Mapped[datetime] = mapped_column(default=utcnow)
    valid_to: Mapped[datetime | None]
    changed_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
