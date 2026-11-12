import asyncio
import re
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select, update

from app.core.security import token_hash
from app.db.base import utcnow
from app.modules.audit.models import AuditEvent
from app.modules.auth.models import AuthSession, Credential, PasswordToken
from app.modules.auth.service import issue_reset
from app.modules.notifications.models import NotificationOutbox
from app.modules.notifications.service import deliver_pending
from app.modules.users.models import User
from tests.conftest import PASSWORD

NEW_PASSWORD = "NewPass8!"


@pytest.mark.parametrize("role", ["SUPER_ADMIN", "HR", "MANAGER", "EMPLOYEE"])
def test_each_role_authenticates_with_safe_profile(client, user_factory, signin, factory, role):
    user = user_factory(role)
    response = signin(user)
    profile = response.json()["user"]
    assert profile["roles"] == [role]
    assert profile["employee_id"] == user.employee_id
    assert profile["date_joined"] is None and profile["manager_name"] is None
    assert not {"password_hash", "credential_version", "active"} & profile.keys()
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/api" in cookie
    raw = client.cookies.get("mi_session")
    with factory() as db:
        saved = db.scalar(select(AuthSession).where(AuthSession.user_id == user.id))
        assert saved.token_hash == token_hash(raw) and saved.token_hash != raw
        assert db.get(Credential, user.id).password_hash.startswith("$argon2id$")
    assert client.get("/api/v1/auth/me").json()["id"] == user.id
    assert client.get("/api/v1/auth/csrf").json()["csrf_token"] == response.json()["csrf_token"]


def test_login_rejects_inactive_and_unknown_without_disclosure(client, user_factory):
    user = user_factory(active=False)
    inactive = client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    unknown = client.post("/api/v1/auth/login", json={"email": "missing@example.org", "password": PASSWORD})
    assert inactive.status_code == unknown.status_code == 401
    assert inactive.json()["error"]["message"] == unknown.json()["error"]["message"]
    assert "mi_session" not in client.cookies


def test_validation_never_echoes_credentials_and_rejects_mass_assignment(client):
    response = client.post(
        "/api/v1/auth/login", json={"email": "x", "password": "PRIVATE_VALUE", "role": "SUPER_ADMIN"}
    )
    assert response.status_code == 422
    assert "PRIVATE_VALUE" not in response.text
    assert response.json()["error"]["request_id"]


def test_origin_checks_apply_before_authentication(client):
    for origin in ["", "https://attacker.example", "null"]:
        response = client.post("/api/v1/auth/login", headers={"Origin": origin}, json={})
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "ORIGIN_REJECTED"


def test_logout_requires_csrf_and_revokes_session(client, user_factory, signin):
    session = signin(user_factory()).json()
    assert client.post("/api/v1/auth/logout").status_code == 403
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "incorrect"}).status_code == 403
    assert (
        client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": session["csrf_token"]}).status_code == 204
    )
    assert client.get("/api/v1/auth/me").status_code == 401


def test_temporary_password_gate_and_rotation(client, user_factory, signin, factory):
    user = user_factory("SUPER_ADMIN", temporary=True)
    first = signin(user).json()
    previous = client.cookies.get("mi_session")
    assert client.get("/api/v1/admin/summary").json()["error"]["code"] == "PASSWORD_CHANGE_REQUIRED"
    changed = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers={"X-CSRF-Token": first["csrf_token"]},
    )
    assert changed.status_code == 200, changed.text
    assert not changed.json()["user"]["must_change_password"]
    assert previous != client.cookies.get("mi_session")
    assert client.get("/api/v1/admin/summary").status_code == 200
    with factory() as db:
        old = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(previous)))
        assert old.revoked_at is not None
        assert not db.get(Credential, user.id).must_change_password
        assert db.scalar(select(AuditEvent).where(AuditEvent.action == "auth.password_changed"))


def test_password_change_rejects_wrong_current_short_or_same_password(client, user_factory, signin):
    session = signin(user_factory()).json()
    headers = {"X-CSRF-Token": session["csrf_token"]}
    for current, password, status in [
        ("wrong", NEW_PASSWORD, 400),
        (PASSWORD, "1234567", 422),
        (PASSWORD, "1234567890123456", 422),
        (PASSWORD, PASSWORD, 422),
    ]:
        assert (
            client.post(
                "/api/v1/auth/change-password",
                json={"current_password": current, "new_password": password},
                headers=headers,
            ).status_code
            == status
        )


def test_password_change_accepts_eight_character_password(client, user_factory, signin):
    user = user_factory()
    session = signin(user).json()
    response = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "Pass8abc"},
        headers={"X-CSRF-Token": session["csrf_token"]},
    )
    assert response.status_code == 200, response.text


@pytest.mark.parametrize(
    ("password", "valid"),
    [("1234567", False), ("12345678", True), ("123456789012345", True), ("1234567890123456", False)],
)
def test_password_change_schema_enforces_eight_to_fifteen_characters(password, valid):
    from pydantic import ValidationError

    from app.modules.auth.schemas import PasswordChange, ResetComplete
    from app.modules.users.schemas import CreateUser, ResetPassword

    schemas = [
        lambda: PasswordChange(current_password="Current8!", new_password=password),
        lambda: ResetComplete(token="T" * 64, new_password=password),
        lambda: ResetPassword(expected_version=1, temporary_password=password),
        lambda: CreateUser(
            full_name="Test User",
            employee_id="TEST-USER",
            email="user@example.org",
            department="Test",
            designation="Tester",
            country="Testland",
            role="EMPLOYEE",
            temporary_password=password,
        ),
    ]
    for build in schemas:
        if valid:
            build()
        else:
            with pytest.raises(ValidationError):
                build()


@pytest.mark.parametrize("reason", ["expired", "idle", "deactivated", "revoked", "credentials_changed"])
def test_session_invalidation(client, user_factory, signin, factory, reason):
    user = user_factory()
    signin(user)
    with factory.begin() as db:
        session = db.scalar(select(AuthSession).where(AuthSession.user_id == user.id))
        if reason == "expired":
            session.expires_at = utcnow() - timedelta(seconds=1)
        if reason == "idle":
            session.last_seen_at = utcnow() - timedelta(hours=2)
        if reason == "revoked":
            session.revoked_at = utcnow()
        if reason == "deactivated":
            db.get(User, user.id).active = False
        if reason == "credentials_changed":
            db.get(User, user.id).credential_version += 1
    assert client.get("/api/v1/auth/me").status_code == 401


def test_reset_is_one_use_hashed_and_revokes_existing_sessions(client, factory, app, user_factory, signin):
    user = user_factory(temporary=True)
    signin(user)
    with factory() as db:
        raw = issue_reset(db, app.state.settings, db.get(User, user.id))
        saved = db.scalar(select(PasswordToken).where(PasswordToken.user_id == user.id))
        assert raw not in saved.token_hash
        assert saved.token_hash == token_hash(raw)
    assert client.get("/api/v1/auth/me").status_code == 401
    payload = {"token": raw, "new_password": NEW_PASSWORD}
    assert client.post("/api/v1/auth/complete-password-setup", json=payload).status_code == 204
    assert client.post("/api/v1/auth/complete-password-setup", json=payload).status_code == 400
    signed = client.post("/api/v1/auth/login", json={"email": user.email, "password": NEW_PASSWORD})
    assert signed.status_code == 200 and not signed.json()["user"]["must_change_password"]


def test_reset_expiry_and_superseded_token(client, factory, app, user_factory):
    user = user_factory()
    with factory() as db:
        first = issue_reset(db, app.state.settings, db.get(User, user.id))
        second = issue_reset(db, app.state.settings, db.get(User, user.id))
        db.execute(
            update(PasswordToken)
            .where(PasswordToken.token_hash == token_hash(second))
            .values(expires_at=utcnow() - timedelta(seconds=1))
        )
        db.commit()
    for token in [first, second, "A" * 64]:
        assert (
            client.post(
                "/api/v1/auth/complete-password-setup", json={"token": token, "new_password": NEW_PASSWORD}
            ).status_code
            == 400
        )


@pytest.mark.parametrize("alternate", [None, "https://mycareer-vpn.example.org"])
@pytest.mark.parametrize("test_mode", [False, True])
def test_public_reset_emails_registered_user_and_completes_once(
    client,
    user_factory,
    signin,
    factory,
    monkeypatch,
    alternate,
    test_mode,
):
    monkeypatch.setattr("app.main.deliver_pending", AsyncMock())
    settings = client.app.state.settings
    settings.mail_enabled = True
    settings.mail_test_mode = test_mode
    settings.mail_test_recipient = "reset.member@example.org"
    settings.smtp_host = "smtp.example.org"
    settings.mail_from_address = "mycareer@example.org"
    settings.public_base_url = "https://mycareer.example.org"
    settings.alternate_public_base_url = alternate
    smtp = MagicMock()
    smtp_class = MagicMock()
    smtp_class.return_value.__enter__.return_value = smtp
    monkeypatch.setattr("app.modules.notifications.service.smtplib.SMTP", smtp_class)
    user = user_factory(email="reset.member@example.org")
    signin(user)
    response = client.post("/api/v1/auth/forgot-password", json={"email": user.email.upper()})
    assert response.status_code == 202, response.text
    assert set(response.json()) == {"message"}
    assert client.get("/api/v1/auth/me").status_code == 200
    with factory.begin() as db:
        queued = db.scalars(select(NotificationOutbox)).all()
        assert len(queued) == 1
        assert queued[0].recipients == [user.email]
        raw = re.search(r"/#reset=([A-Za-z0-9_-]+)", queued[0].body).group(1)
        saved = db.scalar(select(PasswordToken).where(PasswordToken.user_id == user.id))
        assert saved.token_hash == token_hash(raw) and saved.token_hash != raw
        assert 0 < (saved.expires_at - utcnow()).total_seconds() <= settings.reset_minutes * 60 + 1
        assert raw not in response.text
        queued[0].available_at = utcnow() - timedelta(seconds=2)
    asyncio.run(deliver_pending(factory, settings))
    smtp.send_message.assert_called_once()
    message = smtp.send_message.call_args.args[0]
    assert str(message["To"]) == user.email
    assert f"https://mycareer.example.org/#reset={raw}" in message.get_content()
    if alternate:
        assert f"{alternate}/#reset={raw}" in message.get_content()
    body = {"token": raw, "new_password": NEW_PASSWORD}
    assert client.post("/api/v1/auth/complete-password-setup", json=body).status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.post("/api/v1/auth/complete-password-setup", json=body).status_code == 400
    assert (
        client.post("/api/v1/auth/login", json={"email": user.email, "password": NEW_PASSWORD}).status_code
        == 200
    )


def test_public_reset_rejects_unknown_inactive_and_disabled_email(client, user_factory, factory):
    path = "/api/v1/auth/forgot-password"
    unknown = client.post(path, json={"email": "unknown@example.org"})
    assert unknown.status_code == 404
    assert unknown.json()["error"]["message"] == "User is not registered. Please contact your administrator."
    inactive = user_factory(active=False)
    assert client.post(path, json={"email": inactive.email}).status_code == 403
    user = user_factory()
    unavailable = client.post(path, json={"email": user.email})
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "MAIL_UNAVAILABLE"
    with factory() as db:
        assert db.scalar(select(PasswordToken)) is None
        assert db.scalar(select(NotificationOutbox)) is None


def test_public_reset_test_mail_omits_usable_links(client, user_factory, factory, monkeypatch):
    monkeypatch.setattr("app.main.deliver_pending", AsyncMock())
    settings = client.app.state.settings
    settings.mail_enabled = settings.mail_test_mode = True
    settings.mail_test_recipient = "qa@example.org"
    user = user_factory()
    response = client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    assert response.status_code == 202
    assert "test mode" in response.json()["message"]
    with factory() as db:
        queued = db.scalar(select(NotificationOutbox))
        assert queued.recipients == ["qa@example.org"]
        assert "#reset=" not in queued.body
        assert db.scalar(select(PasswordToken)) is None


def test_shared_rate_limit_persists_across_app_instances(client, app, factory):
    app.state.settings.login_attempts = 2
    body = {"email": "unknown@example.org", "password": PASSWORD}
    assert client.post("/api/v1/auth/login", json=body).status_code == 401
    assert client.post("/api/v1/auth/login", json=body).status_code == 401
    from app.core.errors import AppError
    from app.modules.auth.rate_limit import throttle

    # New DB session, same durable counters, as another worker would use.
    with pytest.raises(AppError) as error:
        throttle(factory, app.state.settings, "login", "different-ip", body["email"])
    assert error.value.status == 429 and int(error.value.headers["Retry-After"]) > 0


def test_audit_events_cannot_be_edited_with_orm(factory, user_factory, signin):
    signin(user_factory())
    with factory() as db:
        event = db.scalar(select(AuditEvent).where(AuditEvent.action == "auth.login"))
        event.action = "altered"
        with pytest.raises(ValueError, match="append-only"):
            db.commit()


def test_health_and_headers(client):
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert client.get("/api/v1/health/ready").status_code == 200


def test_unexpected_errors_use_safe_consistent_responses(app):
    from fastapi.testclient import TestClient

    @app.get("/api/v1/test-fault")
    def faulty_route():
        raise RuntimeError("PRIVATE_INTERNAL_VALUE")

    with TestClient(app, raise_server_exceptions=False) as browser:
        response = browser.get("/api/v1/test-fault")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert response.json()["error"]["request_id"]
    assert "PRIVATE_INTERNAL_VALUE" not in response.text
    assert response.headers["cache-control"] == "no-store"
