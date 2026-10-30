import sys

import pytest
from sqlalchemy import select

from app import cli
from app.modules.auth.models import Credential
from app.modules.users.models import User
from tests.conftest import PASSWORD


def test_bootstrap_is_one_time_and_forces_password_change(app, factory, monkeypatch):
    monkeypatch.setattr(cli, "Settings", lambda: app.state.settings)
    monkeypatch.setattr(cli, "make_engine", lambda _: app.state.engine)
    monkeypatch.setattr(cli, "session_factory", lambda _: factory)
    monkeypatch.setattr(cli.getpass, "getpass", lambda _: PASSWORD)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "operator",
            "bootstrap-admin",
            "--email",
            "initial@example.org",
            "--employee-id",
            "TEST-BOOTSTRAP",
            "--name",
            "Test Administrator",
        ],
    )
    cli.main()
    with factory() as db:
        user = db.scalar(select(User).where(User.email == "initial@example.org"))
        assert user.roles == ["SUPER_ADMIN"]
        assert db.get(Credential, user.id).must_change_password
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
