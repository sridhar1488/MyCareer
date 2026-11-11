"""Use independent committed connections in a disposable MySQL schema."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text

from app.core.config import Settings
from app.core.security import hasher
from app.main import create_app
from app.modules.appraisals import service
from app.modules.appraisals.models import Appraisal
from app.modules.auth.models import Credential
from app.modules.users.models import User, UserRole
from tests.conftest import ORIGIN, PASSWORD
from tests.test_directory_appraisals import cycle_body, draft, profile


@pytest.fixture
def concurrent_app(mysql_engine, monkeypatch):
    name = "concurrency_" + uuid.uuid4().hex[:12] + "_test"
    root = create_engine(mysql_engine.url.set(database=None), hide_parameters=True)
    with root.begin() as db:
        db.execute(text(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4"))
    url = mysql_engine.url.set(database=name).render_as_string(hide_password=False)
    monkeypatch.setenv("MI_MIGRATION_DATABASE_URL", url)
    app = None
    try:
        command.upgrade(Config("alembic.ini"), "head")
        app = create_app(
            Settings(
                _env_file=None,
                environment="test",
                database_url=url,
                secret_key="concurrent-workflow-test-secret-48-characters",
            )
        )
        yield app
    finally:
        if app:
            app.state.engine.dispose()
        with root.begin() as db:
            db.execute(text(f"DROP DATABASE `{name}`"))
        root.dispose()


def account(app, role, manager_id=None):
    with app.state.sessions.begin() as db:
        user = User(
            employee_id=str(uuid.uuid4()),
            email=f"{uuid.uuid4()}@example.org",
            full_name="Concurrency test",
            manager_id=manager_id,
        )
        db.add(user)
        db.flush()
        db.add(UserRole(user_id=user.id, role_code=role))
        db.add(Credential(user_id=user.id, password_hash=hasher.hash(PASSWORD), must_change_password=False))
    return user


def login(app, user):
    browser = TestClient(app, headers={"Origin": ORIGIN})
    response = browser.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200
    browser.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return browser


def test_concurrent_admin_removal_keeps_one_active_admin(concurrent_app):
    app = concurrent_app
    a, b = account(app, "SUPER_ADMIN"), account(app, "SUPER_ADMIN")
    clients = [login(app, a), login(app, b)]
    targets = [b, a]

    def remove(i):
        return (
            clients[i]
            .post(f"/api/v1/admin/users/{targets[i].id}/deactivate", json={"expected_version": 1})
            .status_code
        )

    with ThreadPoolExecutor(max_workers=2) as workers:
        statuses = list(workers.map(remove, range(2)))
    assert statuses.count(200) == 1
    assert all(status in [200, 401, 403, 409] for status in statuses)
    with app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(User).where(User.active.is_(True))) == 1
    for browser in clients:
        browser.close()


def test_concurrent_duplicate_account_creation(concurrent_app):
    app = concurrent_app
    admin = account(app, "SUPER_ADMIN")
    clients = [login(app, admin), login(app, admin)]

    def create(i):
        return (
            clients[i]
            .post("/api/v1/admin/users", json=profile(role="EMPLOYEE", temporary_password=PASSWORD))
            .status_code
        )

    with ThreadPoolExecutor(max_workers=2) as workers:
        assert sorted(workers.map(create, range(2))) == [201, 409]
    for browser in clients:
        browser.close()


def appraisal_fixture(app):
    admin, manager = account(app, "SUPER_ADMIN"), account(app, "MANAGER")
    employee = account(app, "EMPLOYEE", manager.id)
    with login(app, admin) as browser:
        response = browser.post("/api/v1/cycles", json=cycle_body([employee.id]))
        c = response.json()
        assert (
            browser.post(f"/api/v1/cycles/{c['id']}/activate", json={"expected_version": 1}).status_code
            == 200
        )
    with app.state.sessions() as db:
        a = db.scalar(select(Appraisal))
    return employee, a


def test_concurrent_saves_accept_exactly_one_version(concurrent_app):
    app = concurrent_app
    employee, a = appraisal_fixture(app)
    clients = [login(app, employee), login(app, employee)]

    def save(i):
        return (
            clients[i].put(f"/api/v1/appraisals/{a.id}/self-assessment", json=draft(count=i + 1)).status_code
        )

    with ThreadPoolExecutor(max_workers=2) as workers:
        assert sorted(workers.map(save, range(2))) == [200, 409]
    for browser in clients:
        browser.close()


def test_concurrent_duplicate_uploads_save_one_file(concurrent_app, tmp_path):
    app = concurrent_app
    app.state.settings.attachment_directory = str(tmp_path)
    employee, appraisal = appraisal_fixture(app)
    path = f"/api/v1/appraisals/{appraisal.id}/attachments"
    start = Barrier(2)

    with login(app, employee) as first, login(app, employee) as second:

        def upload(browser, name):
            start.wait(timeout=5)
            return browser.post(path, content=b"%PDF-1.4\nShared evidence", headers={"X-File-Name": name})

        with ThreadPoolExecutor(max_workers=2) as workers:
            responses = [
                workers.submit(upload, first, "evidence.pdf"),
                workers.submit(upload, second, "renamed.pdf"),
            ]
            results = sorted((response.result() for response in responses), key=lambda r: r.status_code)
        assert [result.status_code for result in results] == [201, 409]
        assert results[1].json()["error"]["code"] == "DUPLICATE_ATTACHMENT"
        assert [item["id"] for item in first.get(path).json()["items"]] == [results[0].json()["id"]]
        assert len(list(tmp_path.iterdir())) == 1


def test_submit_reads_current_content_after_an_earlier_snapshot(concurrent_app):
    app = concurrent_app
    employee, a = appraisal_fixture(app)
    with app.state.sessions() as db, login(app, employee) as browser:
        owner = db.get(User, employee.id)
        actor = SimpleNamespace(
            user=owner, session=SimpleNamespace(credential_version=owner.credential_version)
        )
        service.owned(db, a.id, actor)  # Begin a MySQL repeatable-read snapshot.
        assert (
            browser.put(f"/api/v1/appraisals/{a.id}/self-assessment", json=draft(count=7)).status_code == 200
        )
        current = service.owned(db, a.id, actor, write=True, expected_version=2)
        submitted = service.submit(db, current, actor)
        assert submitted.content_revision == 1
        assert len(browser.get(f"/api/v1/appraisals/{a.id}/revisions/1").json()["responses"]["goals"]) == 7
