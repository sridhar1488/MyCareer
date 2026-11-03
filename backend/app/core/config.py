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
    setup_link_minutes: int = Field(default=10080, ge=5, le=43200)
    login_attempts: int = Field(default=10, ge=1, le=100)
    rate_window_seconds: int = Field(default=900, ge=10, le=3600)
    attachment_directory: str = ".local/appraisal-attachments"
    static_directory: str | None = None
    mail_enabled: bool = False
    mail_test_mode: bool = True
    mail_test_recipient: str | None = None
    mail_from_address: str | None = None
    mail_from_name: str = "MyCareer"
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_starttls: bool = True
    public_base_url: str | None = None

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
        if self.mail_enabled:
            if not all([self.smtp_host, self.mail_from_address, self.public_base_url]):
                raise ValueError("Enabled mail requires SMTP host, sender address, and public app URL")
            if self.mail_test_mode and not self.mail_test_recipient:
                raise ValueError("Mail test mode requires a test recipient mailbox")
            if (self.smtp_username is None) != (self.smtp_password is None):
                raise ValueError("SMTP username and password must be configured together")
        if self.public_base_url and (
            urlsplit(self.public_base_url).scheme not in {"http", "https"}
            or not urlsplit(self.public_base_url).hostname
            or urlsplit(self.public_base_url).path not in {"", "/"}
        ):
            raise ValueError("Public app URL must be an HTTP(S) origin")
        return self
