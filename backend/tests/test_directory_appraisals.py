from datetime import timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DatabaseError

from app.db.base import utcnow
from app.modules.appraisals.models import Appraisal, AppraisalHistory, Cycle
from app.modules.auth.models import Credential
from app.modules.users.models import ReportingRelationship, User
from tests.conftest import PASSWORD


def headers(signin, user):
    return {"X-CSRF-Token": signin(user).json()["csrf_token"]}


def profile(**overrides):
    return {
        "full_name": "New Employee",
        "employee_id": "NEW-42",
        "email": "new@example.org",
        "department": "Engineering",
        "designation": "Engineer",
        "country": "India",
        **overrides,
    }


def cycle_body(ids, **overrides):
    return {
        "title": "Annual appraisal",
        "period_start": "2026-01-01",
        "period_end": "2026-12-31",
        "submission_deadline": (utcnow() + timedelta(days=7)).isoformat() + "Z",
        "min_goals": 1,
        "allow_late_submission": False,
        "participant_ids": ids,
        **overrides,
    }


def draft(version=1, count=1, **overrides):
    return {
        "expected_version": version,
        "goals": [
            {"description": f"Goal {i}", "employee_narrative": "Delivered measurable progress"}
            for i in range(count)
        ],
        "contributions": [],
        "development": {"support_requested": "Mentoring"},
        **overrides,
    }


@pytest.fixture
def setup_appraisal(client, signin, user_factory, factory):
    admin = user_factory("SUPER_ADMIN")
    manager = user_factory("MANAGER")
    employee = user_factory()
    with factory.begin() as db:
        db.get(User, employee.id).manager_id = manager.id
    h = headers(signin, admin)
    response = client.post("/api/v1/cycles", json=cycle_body([employee.id]), headers=h)
    assert response.status_code == 201, response.text
    cycle = response.json()
    response = client.post(f"/api/v1/cycles/{cycle['id']}/activate", json={"expected_version": 1}, headers=h)
    assert response.status_code == 200, response.text
    h = headers(signin, employee)
    appraisal = client.get("/api/v1/me/appraisals").json()["items"][0]
    return admin, manager, employee, appraisal, h


def test_create_profile_duplicate_and_no_credential_disclosure(client, signin, user_factory, factory):
    admin = user_factory("SUPER_ADMIN")
    manager = user_factory("MANAGER")
    h = headers(signin, admin)
    body = profile(role="EMPLOYEE", manager_id=manager.id, temporary_password=PASSWORD)
    response = client.post("/api/v1/admin/users", json=body, headers=h)
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["roles"] == ["EMPLOYEE"] and row["manager_id"] == manager.id
    assert "password" not in response.text and PASSWORD not in response.text
    with factory() as db:
        assert db.get(Credential, row["id"]).must_change_password
        assert db.get(User, row["id"]).department_id
        assert db.scalar(select(ReportingRelationship).where(ReportingRelationship.employee_id == row["id"]))
    assert client.post("/api/v1/admin/users", json=body, headers=h).status_code == 409
    assert client.post("/api/v1/admin/users", json={**body, "role": "HR"}, headers=h).status_code == 422
    edited = client.patch(
        f"/api/v1/admin/users/{row['id']}", json=profile(full_name="Updated", expected_version=1), headers=h
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["version"] == 2
    assert (
        client.patch(
            f"/api/v1/admin/users/{row['id']}", json=profile(expected_version=1), headers=h
        ).status_code
        == 409
    )
    listing = client.get("/api/v1/admin/users?q=Updated&role=EMPLOYEE&page_size=1").json()
    assert listing["total"] == 1 and listing["items"][0]["full_name"] == "Updated"
    events = client.get("/api/v1/admin/audit-events?q=admin.").json()["items"]
    assert {e["action"] for e in events} >= {
        "admin.user_created",
        "admin.profile_changed",
        "admin.manager_changed",
    }
    assert PASSWORD not in str(events)


@pytest.mark.parametrize("role", ["EMPLOYEE", "MANAGER", "HR"])
def test_directory_and_cycles_are_super_admin_only(client, signin, user_factory, role):
    user = user_factory(role)
    h = headers(signin, user)
    for path in ["/admin/users", "/admin/audit-events", "/cycles", "/cycles/participant-options"]:
        assert client.get("/api/v1" + path).status_code == 403
    assert (
        client.post(
            "/api/v1/admin/users", json=profile(role="EMPLOYEE", temporary_password=PASSWORD), headers=h
        ).status_code
        == 403
    )
    assert client.post("/api/v1/cycles", json=cycle_body([user.id]), headers=h).status_code == 403


def test_csrf_self_role_last_admin_and_reporting_cycles(client, signin, user_factory):
    admin = user_factory("SUPER_ADMIN")
    a, b = user_factory("MANAGER"), user_factory("MANAGER")
    h = headers(signin, admin)
    assert (
        client.post(
            "/api/v1/admin/users", json=profile(role="EMPLOYEE", temporary_password=PASSWORD)
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/api/v1/admin/users/{admin.id}/role",
            json={"expected_version": 1, "role": "EMPLOYEE"},
            headers=h,
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/admin/users/{admin.id}/deactivate", json={"expected_version": 1}, headers=h
        ).json()["error"]["code"]
        == "LAST_ADMIN"
    )
    assert (
        client.put(
            f"/api/v1/admin/users/{a.id}/manager", json={"expected_version": 1, "manager_id": a.id}, headers=h
        ).status_code
        == 422
    )
    assert (
        client.put(
            f"/api/v1/admin/users/{a.id}/manager", json={"expected_version": 1, "manager_id": b.id}, headers=h
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/v1/admin/users/{b.id}/manager", json={"expected_version": 1, "manager_id": a.id}, headers=h
        ).json()["error"]["code"]
        == "REPORTING_CYCLE"
    )
    assert (
        client.put(
            f"/api/v1/admin/users/{b.id}/role", json={"expected_version": 1, "role": "EMPLOYEE"}, headers=h
        ).status_code
        == 409
    )


@pytest.mark.parametrize("action", ["role", "deactivate", "reset"])
def test_account_access_changes_revoke_sessions(client, signin, user_factory, action):
    admin, employee = user_factory("SUPER_ADMIN"), user_factory()
    signin(employee)
    cookie = client.cookies.get("mi_session")
    h = headers(signin, admin)
    path = f"/api/v1/admin/users/{employee.id}"
    if action == "role":
        response = client.put(path + "/role", json={"expected_version": 1, "role": "MANAGER"}, headers=h)
    elif action == "reset":
        response = client.put(
            path + "/temporary-password",
            json={"expected_version": 1, "temporary_password": "ResetPass8!"},
            headers=h,
        )
    else:
        response = client.post(path + "/deactivate", json={"expected_version": 1}, headers=h)
    assert response.status_code in [200, 204], response.text
    client.cookies.clear()
    client.cookies.set("mi_session", cookie)
    assert client.get("/api/v1/auth/me").status_code == 401
    if action == "reset":
        client.cookies.clear()
        login = client.post("/api/v1/auth/login", json={"email": employee.email, "password": "ResetPass8!"})
        assert login.status_code == 200 and login.json()["user"]["must_change_password"]
        assert client.get("/api/v1/me/appraisals").status_code == 403


def test_activation_validates_all_participants_atomically(client, signin, user_factory, factory):
    admin, employee = user_factory("SUPER_ADMIN"), user_factory()
    h = headers(signin, admin)
    c = client.post("/api/v1/cycles", json=cycle_body([employee.id]), headers=h).json()
    response = client.post(f"/api/v1/cycles/{c['id']}/activate", json={"expected_version": 1}, headers=h)
    assert response.status_code == 422
    with factory() as db:
        assert not db.scalar(select(Appraisal))
        assert db.get(Cycle, c["id"]).state == "DRAFT"
    for overrides in [
        {"min_goals": 0},
        {"participant_ids": []},
        {"participant_ids": [employee.id, employee.id]},
        {"period_end": "2025-01-01"},
        {"submission_deadline": "2026-01-01T12:00:00"},
    ]:
        assert (
            client.post("/api/v1/cycles", json=cycle_body([employee.id], **overrides), headers=h).status_code
            == 422
        )


def test_employee_save_extra_goals_submit_immutable_snapshot(client, factory, setup_appraisal):
    _, _, _, a, h = setup_appraisal
    path = f"/api/v1/appraisals/{a['id']}"
    assert client.post(path + "/submit", json={"expected_version": 1}, headers=h).status_code == 422
    response = client.put(path + "/self-assessment", json=draft(count=7), headers=h)
    assert response.status_code == 200, response.text
    assert len(response.json()["goals"]) == 7 and response.json()["started_at"]
    assert client.put(path + "/self-assessment", json=draft(), headers=h).status_code == 409
    submitted = client.post(path + "/submit", json={"expected_version": 2}, headers=h)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["state"] == "SUBMITTED" and not submitted.json()["editable"]
    assert client.put(path + "/self-assessment", json=draft(3), headers=h).status_code == 409
    assert client.post(path + "/submit", json={"expected_version": 3}, headers=h).status_code == 409
    snapshot = client.get(path + "/revisions/1").json()
    assert len(snapshot["responses"]["goals"]) == 7
    history = client.get(path + "/history?page_size=1").json()
    assert history["total"] == 2 and len(history["items"]) == 1
    for table in ["appraisal_revisions", "appraisal_history", "appraisal_form_versions"]:
        with factory() as db:
            with pytest.raises(DatabaseError):
                db.execute(text(f"DELETE FROM {table}"))
            db.rollback()


@pytest.mark.parametrize("role", ["SUPER_ADMIN", "MANAGER", "EMPLOYEE"])
def test_ownership_blocks_read_write_history_for_every_other_role(
    client, signin, user_factory, setup_appraisal, role
):
    _, _, _, a, _ = setup_appraisal
    h = headers(signin, user_factory(role))
    path = f"/api/v1/appraisals/{a['id']}"
    for suffix in ["", "/history", "/revisions/1"]:
        assert client.get(path + suffix).status_code == 404
    assert client.put(path + "/self-assessment", json=draft(), headers=h).status_code == 404
    assert client.post(path + "/submit", json={"expected_version": 1}, headers=h).status_code == 404
    assert client.get("/api/v1/me/appraisals").json()["total"] == 0


@pytest.mark.parametrize("attack", ["rating", "status", "oversize", "contributions", "development"])
def test_strict_employee_fields_reject_ratings_and_mass_assignment(client, setup_appraisal, attack):
    _, _, _, a, h = setup_appraisal
    data = draft()
    if attack == "rating":
        data["goals"][0]["manager_rating"] = 5
    elif attack == "status":
        data["state"] = "FINALIZED"
    elif attack == "oversize":
        data = draft(count=101)
    elif attack == "contributions":
        data["contributions"] = data["goals"] * 4
    else:
        data["development"]["manager_comments"] = "Override"
    assert (
        client.put(f"/api/v1/appraisals/{a['id']}/self-assessment", json=data, headers=h).status_code == 422
    )


@pytest.mark.parametrize("late", [True, False])
def test_deadline_policy_is_enforced_on_submit(client, factory, setup_appraisal, late):
    _, _, _, a, h = setup_appraisal
    path = f"/api/v1/appraisals/{a['id']}"
    with factory.begin() as db:
        cycle = db.get(Cycle, a["cycle_id"])
        cycle.submission_deadline = utcnow() - timedelta(hours=1)
        cycle.allow_late_submission = late
    assert client.put(path + "/self-assessment", json=draft(), headers=h).status_code == 200
    response = client.post(path + "/submit", json={"expected_version": 2}, headers=h)
    assert response.status_code == (200 if late else 409)


def test_partial_rows_block_submit_and_returned_revision_preserves_original(client, factory, setup_appraisal):
    _, manager, _, a, h = setup_appraisal
    path = f"/api/v1/appraisals/{a['id']}"
    assert (
        client.put(
            path + "/self-assessment",
            json=draft(contributions=[{"description": "Mentoring", "employee_narrative": ""}]),
            headers=h,
        ).status_code
        == 200
    )
    assert client.post(path + "/submit", json={"expected_version": 2}, headers=h).status_code == 422
    assert client.put(path + "/self-assessment", json=draft(2), headers=h).status_code == 200
    assert client.post(path + "/submit", json={"expected_version": 3}, headers=h).status_code == 200
    # Manager return UI belongs to Phase 5; exercise the supported returned-state contract.
    with factory.begin() as db:
        current = db.get(Appraisal, a["id"])
        current.state = "RETURNED_FOR_REVISION"
        current.version += 1
        db.add(
            AppraisalHistory(
                appraisal_id=current.id,
                actor_id=manager.id,
                from_state="SUBMITTED",
                to_state="RETURNED_FOR_REVISION",
                reason="Clarify results",
            )
        )
    assert client.put(path + "/self-assessment", json=draft(5, count=2), headers=h).status_code == 200
    assert client.post(path + "/submit", json={"expected_version": 6}, headers=h).status_code == 200
    assert len(client.get(path + "/revisions/1").json()["responses"]["goals"]) == 1
    assert len(client.get(path + "/revisions/2").json()["responses"]["goals"]) == 2


def test_reassignment_preserves_snapshot_and_protects_reviewer(
    client, signin, user_factory, factory, setup_appraisal
):
    admin, manager, employee, a, _ = setup_appraisal
    other = user_factory("MANAGER")
    h = headers(signin, admin)
    assert (
        client.put(
            f"/api/v1/admin/users/{employee.id}/manager",
            json={"expected_version": 1, "manager_id": other.id},
            headers=h,
        ).status_code
        == 200
    )
    for suffix, method, data in [
        ("/deactivate", client.post, {"expected_version": 1}),
        ("/role", client.put, {"expected_version": 1, "role": "EMPLOYEE"}),
    ]:
        response = method(f"/api/v1/admin/users/{manager.id}" + suffix, json=data, headers=h)
        assert response.status_code == 409 and response.json()["error"]["code"] == "MANAGER_HAS_APPRAISALS"
    with factory() as db:
        assert db.get(Appraisal, a["id"]).manager_id == manager.id


@pytest.mark.parametrize("role", ["SUPER_ADMIN", "MANAGER"])
def test_all_roles_have_personal_appraisals(client, signin, user_factory, factory, role):
    admin, manager, owner = user_factory("SUPER_ADMIN"), user_factory("MANAGER"), user_factory(role)
    with factory.begin() as db:
        db.get(User, owner.id).manager_id = manager.id
    h = headers(signin, admin)
    c = client.post("/api/v1/cycles", json=cycle_body([owner.id]), headers=h).json()
    assert (
        client.post(f"/api/v1/cycles/{c['id']}/activate", json={"expected_version": 1}, headers=h).status_code
        == 200
    )
    h = headers(signin, owner)
    a = client.get("/api/v1/me/appraisals").json()["items"][0]
    assert (
        client.put(f"/api/v1/appraisals/{a['id']}/self-assessment", json=draft(), headers=h).status_code
        == 200
    )
