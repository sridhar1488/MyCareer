from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, SecretStr, StrictBool, field_validator

from app.modules.auth.schemas import StrictInput
from app.modules.users.models import RoleCode


class ProfileInput(StrictInput):
    full_name: str = Field(min_length=1, max_length=150)
    employee_id: str = Field(min_length=1, max_length=40)
    email: EmailStr = Field(max_length=254)
    department: str = Field(min_length=1, max_length=100)
    designation: str = Field(min_length=1, max_length=100)
    country: str = Field(min_length=1, max_length=80)

    @field_validator("full_name", "employee_id", "department", "designation", "country")
    @classmethod
    def nonblank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("A nonblank value is required")
        return value

    @field_validator("email")
    @classmethod
    def canonical(cls, value):
        return str(value).lower()


class CreateUser(ProfileInput):
    role: RoleCode
    super_admin: StrictBool = False
    manager_id: str | None = None
    temporary_password: SecretStr = Field(min_length=8, max_length=15)

    @field_validator("role")
    @classmethod
    def supported_role(cls, value):
        if value == RoleCode.HR:
            raise ValueError("HR accounts use the Super Admin role")
        return value


class EditUser(ProfileInput):
    expected_version: int = Field(ge=1)


class VersionInput(StrictInput):
    expected_version: int = Field(ge=1)


class ChangeRole(VersionInput):
    role: RoleCode
    super_admin: StrictBool = False

    @field_validator("role")
    @classmethod
    def supported_role(cls, value):
        return CreateUser.supported_role(value)


class ChangeManager(VersionInput):
    manager_id: str | None


class ResetPassword(VersionInput):
    temporary_password: SecretStr = Field(min_length=8, max_length=15)


class DirectoryUser(BaseModel):
    id: str
    full_name: str
    employee_id: str
    email: str
    department: str
    designation: str
    country: str
    roles: list[str]
    manager_id: str | None
    manager_name: str | None
    active: bool
    version: int
    created_at: datetime
    last_login_at: datetime | None


class DirectoryPage(BaseModel):
    items: list[DirectoryUser]
    total: int
    page: int
    page_size: int


class AuditRow(BaseModel):
    id: str
    actor_id: str | None
    action: str
    resource_id: str | None
    details: dict
    occurred_at: datetime


class AuditPage(BaseModel):
    items: list[AuditRow]
    total: int
    page: int
    page_size: int
