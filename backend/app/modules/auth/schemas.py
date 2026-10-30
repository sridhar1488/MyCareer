from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginInput(StrictInput):
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def canonical_email(cls, value):
        return str(value).strip().lower()


class PasswordChange(StrictInput):
    current_password: SecretStr = Field(min_length=1, max_length=128)
    new_password: SecretStr = Field(min_length=8, max_length=15)


class ResetComplete(StrictInput):
    token: str = Field(min_length=32, max_length=128)
    new_password: SecretStr = Field(min_length=8, max_length=15)


class ResetRequest(StrictInput):
    email: EmailStr


class UserResponse(BaseModel):
    id: str
    employee_id: str
    email: str
    full_name: str
    department: str
    designation: str
    country: str
    roles: list[str]
    must_change_password: bool


class SessionResponse(BaseModel):
    user: UserResponse
    csrf_token: str
