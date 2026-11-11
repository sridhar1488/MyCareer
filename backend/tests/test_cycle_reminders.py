from datetime import UTC, timedelta
from unittest.mock import AsyncMock

from sqlalchemy import select

from app.db.base import utcnow
from app.modules.appraisals.models import Appraisal, Cycle
from app.modules.notifications.models import NotificationOutbox
from app.modules.notifications.reminders import queue_scheduled_reminders
from tests.test_directory_appraisals import headers
from tests.test_directory_appraisals import setup_appraisal as setup_appraisal


def enable_test_mail(client, monkeypatch):
    monkeypatch.setattr("app.main.deliver_pending", AsyncMock())
    settings = client.app.state.settings
    settings.mail_enabled = True
    settings.mail_test_mode = True
    settings.mail_test_recipient = "qa@example.org"
    settings.public_base_url = "https://mycareer.example.org"
    return settings


def test_manual_preview_scopes_recipients_and_queues_once(
    client, signin, setup_appraisal, factory, user_factory, monkeypatch
):
    admin, manager, employee, appraisal, _ = setup_appraisal
    extra = user_factory()
    with factory.begin() as db:
        original = db.get(Appraisal, appraisal["id"])
        cycle_id = original.cycle_id
        db.add(
            Appraisal(
                employee_id=extra.id,
                manager_id=manager.id,
                cycle_id=cycle_id,
                form_version_id=original.form_version_id,
                identity_snapshot={},
                state="UNDER_REVIEW",
            )
        )
        original.state = "SUBMITTED"
    endpoint = f"/api/v1/hr/cycle-reminders/{cycle_id}"
    manager_headers = headers(signin, manager)
    assert (
        client.post(endpoint + "/preview", json={"stage": "manager"}, headers=manager_headers).status_code
        == 403
    )
    admin_headers = headers(signin, admin)
    empty = client.post(endpoint + "/preview", json={"stage": "employee"}, headers=admin_headers).json()
    assert empty["recipient_count"] == 0 and empty["mail_mode"] == "disabled"
    enable_test_mail(client, monkeypatch)
    selection = {"stage": "manager", "audience": "pending"}
    preview = client.post(endpoint + "/preview", json=selection, headers=admin_headers).json()
    assert preview["recipient_count"] == 1 and preview["mail_mode"] == "test"
    command = {**selection, "request_id": preview["request_id"], "fingerprint": preview["fingerprint"]}
    for _ in range(2):
        assert client.post(endpoint + "/send", json=command, headers=admin_headers).json() == {"queued": 1}
    with factory() as db:
        message = db.scalars(select(NotificationOutbox)).one()
        assert message.recipients == ["qa@example.org"] and manager.email in message.body
        assert "Pending manager reviews: 2." in message.body and "/?view=team" in message.body
        assert employee.email not in message.body

    all_employees = client.post(
        endpoint + "/preview", json={"stage": "employee", "audience": "all"}, headers=admin_headers
    )
    assert all_employees.json()["recipient_count"] == 2
    fresh = client.post(endpoint + "/preview", json=selection, headers=admin_headers).json()
    with factory.begin() as db:
        db.get(Appraisal, appraisal["id"]).state = "HR_REVIEW"
    stale = {**command, "request_id": fresh["request_id"], "fingerprint": fresh["fingerprint"]}
    assert client.post(endpoint + "/send", json=stale, headers=admin_headers).status_code == 409


def test_scheduled_reminders_use_each_deadline_and_skip_completed_work(
    client, signin, setup_appraisal, factory, monkeypatch
):
    admin, manager, employee, appraisal, _ = setup_appraisal
    settings = enable_test_mail(client, monkeypatch)
    now = utcnow().replace(microsecond=0)
    employee_deadline = now + timedelta(hours=4)
    with factory.begin() as db:
        cycle_id = db.get(Appraisal, appraisal["id"]).cycle_id
        db.get(Cycle, cycle_id).submission_deadline = employee_deadline
    manager_deadline = now + timedelta(days=4)
    hr_deadline = now + timedelta(days=8)
    endpoint = f"/api/v1/hr/cycle-reminders/{cycle_id}/settings"
    h = headers(signin, admin)
    payload = {
        "expected_version": 0,
        "hours_before": [72, 8],
        "manager_deadline": manager_deadline.replace(tzinfo=UTC).isoformat(),
        "hr_deadline": hr_deadline.replace(tzinfo=UTC).isoformat(),
    }
    saved = client.put(endpoint, json=payload, headers=h)
    assert saved.status_code == 200 and saved.json()["hours_before"] == [72, 8]
    assert client.put(endpoint, json=payload, headers=h).status_code == 409

    queue_scheduled_reminders(factory, settings, now)
    queue_scheduled_reminders(factory, settings, now)
    with factory.begin() as db:
        db.get(Appraisal, appraisal["id"]).state = "SUBMITTED"
    queue_scheduled_reminders(factory, settings, manager_deadline - timedelta(hours=72))
    with factory.begin() as db:
        db.get(Appraisal, appraisal["id"]).state = "HR_REVIEW"
    queue_scheduled_reminders(factory, settings, manager_deadline - timedelta(hours=8))
    queue_scheduled_reminders(factory, settings, hr_deadline - timedelta(hours=72))
    with factory() as db:
        messages = {message.subject: message.body for message in db.scalars(select(NotificationOutbox))}
        assert len(messages) == 3
        for stage, email in [
            ("self-assessments", employee.email),
            ("manager reviews", manager.email),
            ("HR calibrations", admin.email),
        ]:
            body = next(body for subject, body in messages.items() if stage in subject)
            assert email in body and f"Pending {stage}: 1." in body
