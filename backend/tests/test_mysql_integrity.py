import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core.config import Settings
from app.core.errors import AppError
from app.db.session import session_factory
from app.modules.audit.models import AuditEvent
from app.modules.auth.rate_limit import throttle
from app.modules.users.models import User


@pytest.mark.mysql
def test_atomic_shared_rate_limit_under_concurrency(mysql_engine):
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=mysql_engine.url.render_as_string(hide_password=False),
        secret_key="concurrent-test-secret-with-32-characters",
        login_attempts=4,
    )
    factory = session_factory(mysql_engine)
    principal, ip = str(uuid.uuid4()), str(uuid.uuid4())

    def attempt(_):
        try:
            throttle(factory, settings, "concurrent-test", ip, principal)
            return True
        except AppError as error:
            assert error.status == 429
            return False

    with ThreadPoolExecutor(max_workers=4) as workers:
        outcomes = list(workers.map(attempt, range(12)))
    assert outcomes.count(True) == 4
    assert outcomes.count(False) == 8


def test_unique_employee_and_email_constraints(factory, user_factory):
    user = user_factory()
    for field in ["email", "employee_id"]:
        with factory() as db:
            other = User(
                employee_id=str(uuid.uuid4()),
                email=f"{uuid.uuid4()}@example.org",
                full_name="Constraint test",
            )
            setattr(other, field, getattr(user, field))
            db.add(other)
            with pytest.raises(IntegrityError):
                db.commit()


def test_database_audit_triggers_reject_raw_sql(app, factory, user_factory, signin):
    if app.state.engine.dialect.name != "mysql":
        pytest.skip("MySQL trigger verification; SQLite has ORM guard only")
    signin(user_factory())
    with factory() as db:
        event_id = db.scalar(select(AuditEvent.id).limit(1))
    for statement in [
        "UPDATE audit_events SET action = :value WHERE id = :id",
        "DELETE FROM audit_events WHERE id = :id",
    ]:
        with factory() as db:
            with pytest.raises(DBAPIError):
                db.execute(text(statement), {"value": "tampered", "id": event_id})
            db.rollback()
