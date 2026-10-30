import pytest

from app.api.dependencies import require_assigned_manager, require_owner
from app.core.config import Settings
from app.core.errors import AppError
from app.modules.users.models import RoleCode


@pytest.mark.parametrize("role", list(RoleCode))
def test_only_admin_reads_account_summary(client, user_factory, signin, role):
    signin(user_factory(role.value))
    result = client.get("/api/v1/admin/summary")
    assert result.status_code == (200 if role == RoleCode.SUPER_ADMIN else 403)
    if result.status_code == 200:
        assert result.json()["total_accounts"] == 1


@pytest.mark.parametrize("role", list(RoleCode))
def test_resource_guards_never_grant_admin_or_hr_appraisal_privileges(user_factory, role):
    actor = user_factory(role.value)
    require_owner(actor, actor.id)
    with pytest.raises(AppError):
        require_owner(actor, "someone-else")
    with pytest.raises(AppError):
        require_assigned_manager(actor, actor.id, actor.id)
    with pytest.raises(AppError):
        require_assigned_manager(actor, "other", "other-manager")
    if role == RoleCode.MANAGER:
        require_assigned_manager(actor, "other", actor.id)
    else:
        with pytest.raises(AppError):
            require_assigned_manager(actor, "other", actor.id)


def test_unauthenticated_admin_access_is_rejected(client):
    assert client.get("/api/v1/admin/summary").status_code == 401


def test_production_settings_fail_closed():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production", database_url="sqlite://", secret_key="short")
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            database_url="mysql+pymysql://user:pass@localhost/db",
            secret_key="test-only-secret-key-with-more-than-32-characters",
            cookie_secure=False,
        )
