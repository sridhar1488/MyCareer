import os

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.core.security import hasher
from app.main import create_app
from app.modules.auth.models import Credential
from app.modules.users.models import User, UserRole

PASSWORD = "TestPass8!"
ORIGIN = "http://localhost:5173"


@pytest.fixture(scope="session")
def mysql_engine():
    url = os.environ.get("MI_TEST_DATABASE_URL")
    if not url:
        pytest.skip("MI_TEST_DATABASE_URL is not set; MySQL integration suite skipped")
    from sqlalchemy.engine import make_url

    parsed = make_url(url)
    if not parsed.database or not parsed.database.endswith("_test"):
        raise RuntimeError("MySQL tests require a dedicated database ending in _test")
    original = os.environ.get("MI_DATABASE_URL")
    migration = os.environ.pop("MI_MIGRATION_DATABASE_URL", None)
    os.environ["MI_DATABASE_URL"] = url
    try:
        command.upgrade(Config("alembic.ini"), "head")
    finally:
        if original is None:
            os.environ.pop("MI_DATABASE_URL", None)
        else:
            os.environ["MI_DATABASE_URL"] = original
        if migration:
            os.environ["MI_MIGRATION_DATABASE_URL"] = migration
    engine = create_engine(url, pool_pre_ping=True, hide_parameters=True)
    yield engine
    engine.dispose()


@pytest.fixture(params=["sqlite", "mysql"])
def app(request, tmp_path, monkeypatch):
    if request.param == "mysql":
        engine = request.getfixturevalue("mysql_engine")
        settings = Settings(
            _env_file=None,
            environment="test",
            database_url=engine.url.render_as_string(hide_password=False),
            secret_key="test-only-rate-limit-and-csrf-secret-48",
        )
    else:
        url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
        monkeypatch.setenv("MI_DATABASE_URL", url)
        monkeypatch.delenv("MI_MIGRATION_DATABASE_URL", raising=False)
        command.upgrade(Config("alembic.ini"), "head")
        settings = Settings(
            _env_file=None,
            environment="test",
            database_url=url,
            secret_key="test-only-rate-limit-and-csrf-secret-48",
        )
    application = create_app(settings)
    if request.param == "mysql":
        # Service commits release SAVEPOINTs, never the outer rollback-only fixture transaction.
        connection = engine.connect()
        outer = connection.begin()
        application.state.sessions = sessionmaker(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
    yield application
    application.state.engine.dispose()
    if request.param == "mysql":
        outer.rollback()
        connection.close()


@pytest.fixture
def client(app):
    with TestClient(app, headers={"Origin": ORIGIN}) as browser:
        yield browser


@pytest.fixture
def factory(app):
    return app.state.sessions


@pytest.fixture
def user_factory(factory):
    def create(role="EMPLOYEE", temporary=False, active=True, email=None):
        import uuid

        identity = str(uuid.uuid4())
        with factory.begin() as db:
            user = User(
                id=identity,
                employee_id=identity,
                email=email or f"{identity}@example.org",
                full_name="Test Team Member",
                department="Technology",
                designation="Engineer",
                active=active,
            )
            db.add(user)
            db.flush()
            user.role_assignments = [UserRole(user_id=user.id, role_code=role)]
            db.add(
                Credential(
                    user_id=user.id, password_hash=hasher.hash(PASSWORD), must_change_password=temporary
                )
            )
        return user

    return create


@pytest.fixture
def signin(client):
    def login(user):
        response = client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
        assert response.status_code == 200, response.text
        return response

    return login
