from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MI_", env_file="../.env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: SecretStr
    secret_key: SecretStr = Field(min_length=32)
    allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    cookie_secure: bool = False
    session_hours: int = Field(default=8, ge=1, le=24)
    session_idle_minutes: int = Field(default=30, ge=1, le=120)
    reset_minutes: int = Field(default=30, ge=5, le=60)
    login_attempts: int = Field(default=10, ge=1, le=100)
    rate_window_seconds: int = Field(default=900, ge=10, le=3600)
    attachment_directory: str = ".local/appraisal-attachments"
    static_directory: str | None = None

    @model_validator(mode="after")
    def validate_deployment(self):
        if not self.allowed_origins or any(
            urlsplit(o).scheme not in {"http", "https"}
            or not urlsplit(o).hostname
            or urlsplit(o).path
            or urlsplit(o).query
            or urlsplit(o).fragment
            or urlsplit(o).username
            for o in self.allowed_origins
        ):
            raise ValueError("Allowed origins must be exact HTTP(S) origins without a path")
        db = self.database_url.get_secret_value()
        if not db.startswith(("mysql+pymysql://", "sqlite://")):
            raise ValueError("Use MySQL/PyMySQL; SQLite is limited to local development and tests")
        if self.environment == "production":
            if not db.startswith("mysql+pymysql://") or not self.cookie_secure:
                raise ValueError("Production requires MySQL and secure cookies")
            if any(urlsplit(o).scheme != "https" for o in self.allowed_origins):
                raise ValueError("Production origins require HTTPS")
        return self
