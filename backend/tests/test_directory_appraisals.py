from datetime import date, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DatabaseError

from app.db.base import utcnow
from app.modules.appraisals.models import Appraisal, AppraisalHistory, AppraisalItem, Cycle, DevelopmentPlan
from app.modules.appraisals.schemas import DevelopmentInput
from app.modules.auth.models import Credential
from app.modules.users.models import ReportingRelationship, RoleCode, User, UserRole
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
    development = dict.fromkeys(DevelopmentInput.model_fields.keys() - {"extra_answers"}, "NA")
    development.update(support_requested="Mentoring")
    development.update(overrides.pop("development", {}))
    return {
        "expected_version": version,
        "goals": [
            {"description": f"Goal {i}", "employee_narrative": "Delivered measurable progress"}
            for i in range(count)
        ],
        "contributions": [],
        "development": development,
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


def test_bulk_cycle_participants_resolve_eligible_roles_across_pages(client, signin, user_factory, factory):
    admin = user_factory("SUPER_ADMIN")
    reviewer = user_factory("MANAGER")
    eligible_manager = user_factory("MANAGER")
    inactive_employee = user_factory(active=False)
    unassigned_employee = user_factory()
    ineligible_employee = user_factory()
    with factory.begin() as db:
        db.get(User, eligible_manager.id).manager_id = reviewer.id
        db.add(UserRole(user_id=eligible_manager.id, role_code=RoleCode.SUPER_ADMIN))
        db.get(User, inactive_employee.id).manager_id = reviewer.id
        db.get(User, ineligible_employee.id).manager_id = unassigned_employee.id
        employees = [
            User(
                employee_id=f"BULK-{index}",
                email=f"bulk-{index}@example.org",
                full_name=f"Bulk employee {index}",
                manager_id=reviewer.id,
                role_assignments=[UserRole(role_code=RoleCode.EMPLOYEE)],
            )
            for index in range(26)
        ]
        db.add_all(employees)
        db.flush()
        expected = {employee.id for employee in employees}

    admin_headers = headers(signin, admin)
    path = "/api/v1/cycles/participant-options/bulk"
    selected = client.get(path, params={"role": "EMPLOYEE"}).json()
    assert set(selected["participant_ids"]) == expected
    assert selected["skipped"] == 2
    managers = client.get(path, params={"role": "MANAGER"}).json()
    assert managers == {"participant_ids": [eligible_manager.id], "skipped": 1}
    assert client.get(path, params={"role": "SUPER_ADMIN"}).status_code == 422

    ids = [*selected["participant_ids"], *managers["participant_ids"]]
    created = client.post("/api/v1/cycles", json=cycle_body(ids), headers=admin_headers)
    assert created.status_code == 201, created.text
    cycle = created.json()
    assert set(cycle["participant_ids"]) == {*expected, eligible_manager.id}
    activated = client.post(
        f"/api/v1/cycles/{cycle['id']}/activate", json={"expected_version": 1}, headers=admin_headers
    )
    assert activated.status_code == 200, activated.text


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
    assert client.get("/api/v1/cycles/participant-options/bulk?role=EMPLOYEE").status_code == 403
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
    promotion = client.put(
        f"/api/v1/admin/users/{admin.id}/role",
        json={"expected_version": 1, "role": "MANAGER", "super_admin": True},
        headers=h,
    )
    assert promotion.status_code == 200, promotion.text
    assert set(promotion.json()["roles"]) == {"MANAGER", "SUPER_ADMIN"}
    assert client.get("/api/v1/auth/me").status_code == 401
    h = headers(signin, admin)
    assert (
        client.post(
            f"/api/v1/admin/users/{admin.id}/deactivate", json={"expected_version": 2}, headers=h
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
    last_draft_saved_at = response.json()["last_draft_saved_at"]
    assert last_draft_saved_at and last_draft_saved_at.endswith("Z")
    assert client.put(path + "/self-assessment", json=draft(), headers=h).status_code == 409
    assert client.get(path).json()["last_draft_saved_at"] == last_draft_saved_at
    submitted = client.post(path + "/submit", json={"expected_version": 2}, headers=h)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["state"] == "SUBMITTED" and not submitted.json()["editable"]
    assert submitted.json()["last_draft_saved_at"] == last_draft_saved_at
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


def test_assessment_character_limits_preserve_existing_long_drafts(client, factory, setup_appraisal):
    _, _, _, appraisal, h = setup_appraisal
    path = f"/api/v1/appraisals/{appraisal['id']}"
    goal = {"description": "G" * 500, "employee_narrative": "A" * 1000}
    for section, error in (("goals", "GOAL_TEXT_LIMIT"), ("contributions", "CONTRIBUTION_TEXT_LIMIT")):
        for field in goal:
            over_limit = {**goal, field: goal[field] + "x"}
            response = client.put(path + "/self-assessment", json=draft(**{section: [over_limit]}), headers=h)
            assert response.status_code == 422
            assert response.json()["error"]["code"] == error
    response = client.put(
        path + "/self-assessment", json=draft(development={"development_plan": "D" * 1001}), headers=h
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "APPRAISAL_TEXT_LIMIT"
    saved = client.put(path + "/self-assessment", json=draft(goals=[goal], contributions=[goal]), headers=h)
    assert saved.status_code == 200, saved.text

    # Simulate data saved under the original limits.
    legacy = {**goal, "description": "G" * 501}
    legacy_contribution = {**goal, "employee_narrative": "A" * 1001}
    legacy_development = "D" * 1001
    with factory.begin() as db:
        items = db.scalars(select(AppraisalItem).where(AppraisalItem.appraisal_id == appraisal["id"]))
        by_kind = {item.kind: item for item in items}
        by_kind["GOAL"].description = legacy["description"]
        by_kind["CONTRIBUTION"].employee_narrative = legacy_contribution["employee_narrative"]
        db.get(DevelopmentPlan, appraisal["id"]).development_plan = legacy_development

    duplicate = client.put(path + "/self-assessment", json=draft(2, goals=[legacy, legacy]), headers=h)
    assert duplicate.status_code == 422
    edited = {**legacy, "employee_narrative": "Updated achievement"}
    saved = client.put(
        path + "/self-assessment",
        json=draft(
            2,
            goals=[edited],
            contributions=[legacy_contribution],
            development={"development_plan": legacy_development},
        ),
        headers=h,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["goals"] == [edited]
    assert saved.json()["contributions"] == [legacy_contribution]
    assert saved.json()["development"]["development_plan"] == legacy_development
    submitted = client.post(path + "/submit", json={"expected_version": 3}, headers=h)
    assert submitted.status_code == 200, submitted.text


def test_each_development_answer_is_required_only_at_submission(client, setup_appraisal):
    _, _, _, appraisal, h = setup_appraisal
    path = f"/api/v1/appraisals/{appraisal['id']}"
    version = 1
    for field in draft()["development"]:
        saved = client.put(
            path + "/self-assessment", json=draft(version, development={field: "  "}), headers=h
        )
        assert saved.status_code == 200, saved.text
        version = saved.json()["version"]
        rejected = client.post(path + "/submit", json={"expected_version": version}, headers=h)
        assert rejected.status_code == 422
        assert rejected.json()["error"]["code"] == "INCOMPLETE_APPRAISAL"
        assert field.replace("_", " ") in rejected.json()["error"]["message"]

    saved = client.put(
        path + "/self-assessment", json=draft(version, development={"support_requested": " N "}), headers=h
    )
    assert saved.status_code == 200, saved.text
    version = saved.json()["version"]
    rejected = client.post(path + "/submit", json={"expected_version": version}, headers=h)
    assert rejected.status_code == 422
    assert "support requested" in rejected.json()["error"]["message"]

    body = draft(
        version,
        goals=[{"description": "Goal title", "employee_narrative": "NA"}],
        contributions=[{"description": "Contribution", "employee_narrative": "N/A"}],
    )
    saved = client.put(path + "/self-assessment", json=body, headers=h)
    assert saved.status_code == 200, saved.text
    submitted = client.post(path + "/submit", json={"expected_version": saved.json()["version"]}, headers=h)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["development"]["development_plan"] == "NA"


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
    with factory.begin() as db:
        db.get(User, employee.id).date_joined = date(2024, 1, 15)
        db.get(User, other.id).full_name = "New Reporting Manager"
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

    cycle = client.post(
        "/api/v1/cycles",
        json=cycle_body(
            [employee.id], title="Cross-year review", period_start="2026-07-01", period_end="2027-06-30"
        ),
        headers=h,
    )
    assert cycle.status_code == 201, cycle.text
    cycle_id = cycle.json()["id"]
    assert (
        client.post(
            f"/api/v1/cycles/{cycle_id}/activate", json={"expected_version": 1}, headers=h
        ).status_code
        == 200
    )

    login_profile = signin(employee).json()["user"]
    assert login_profile == client.get("/api/v1/auth/me").json()
    assert login_profile["date_joined"] == "2024-01-15"
    assert login_profile["manager_name"] == "New Reporting Manager"
    assigned = {row["cycle_id"]: row for row in client.get("/api/v1/me/appraisals").json()["items"]}
    original, latest = assigned[a["cycle_id"]], assigned[cycle_id]
    assert (original["period_start"], original["period_end"]) == ("2026-01-01", "2026-12-31")
    assert (latest["period_start"], latest["period_end"]) == ("2026-07-01", "2027-06-30")
    assert original["manager_name"] == manager.full_name
    assert latest["manager_name"] == "New Reporting Manager"
    assert client.get(f"/api/v1/appraisals/{a['id']}").json()["manager_name"] == manager.full_name


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
