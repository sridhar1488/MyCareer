from copy import deepcopy
from io import BytesIO

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from app.modules.appraisals.models import FormVersion
from app.modules.forms.config import config_for
from app.modules.forms.schemas import FormConfig
from app.modules.imports.service import COLUMNS, read_file, template
from app.modules.users.models import UserRole
from tests.test_directory_appraisals import cycle_body, draft, headers, profile
from tests.test_directory_appraisals import setup_appraisal as setup_appraisal
from tests.test_finalization import command, complete_review
from tests.test_manager_reviews import submitted_review as submitted_review


def workbook_bytes(rows):
    book = load_workbook(BytesIO(template()))
    for i, row in enumerate(rows, 2):
        for j, key in enumerate(COLUMNS, 1):
            book["Users"].cell(i, j, row.get(key, ""))
    stream = BytesIO()
    book.save(stream)
    return stream.getvalue()


def test_manager_with_additional_hr_access(client, signin, user_factory):
    admin = user_factory("SUPER_ADMIN")
    h = headers(signin, admin)
    result = client.post(
        "/api/v1/admin/users",
        json={
            **profile(),
            "role": "MANAGER",
            "super_admin": True,
            "temporary_password": "SecurePass8!",
        },
        headers=h,
    )
    assert result.status_code == 201, result.text
    assert set(result.json()["roles"]) == {"MANAGER", "SUPER_ADMIN"}


def test_form_publication_and_future_cycle_binding(client, signin, user_factory, factory):
    admin = user_factory("SUPER_ADMIN")
    h = headers(signin, admin)
    cfg = client.get("/api/v1/hr/forms/default").json()
    cfg.update(name="Engineering review", goals_limit=8)
    cfg["text_sections"] = [
        {
            "id": "reflection",
            "title": "Reflection",
            "owner": "EMPLOYEE",
            "questions": [{"id": "impact", "label": "What changed?", "required": True}],
        }
    ]
    cfg["section_order"].append("reflection")
    created = client.post("/api/v1/hr/forms", json=cfg, headers=h)
    assert created.status_code == 201, created.text
    form = created.json()
    published = client.post(
        f"/api/v1/hr/forms/{form['id']}/publish", json={"expected_version": form["version"]}, headers=h
    )
    assert published.status_code == 200, published.text
    version = published.json()["published_form_id"]
    cfg["name"] = "Edited future version"
    saved = client.put(
        f"/api/v1/hr/forms/{form['id']}",
        json={"expected_version": published.json()["version"], "config": cfg},
        headers=h,
    )
    assert saved.status_code == 200
    with factory() as db:
        assert config_for(db.get(FormVersion, version).definition).name == "Engineering review"
    cycle = client.post("/api/v1/cycles", json=cycle_body([admin.id], form_version_id=version), headers=h)
    assert cycle.status_code == 201, cycle.text
    assert cycle.json()["form_version_id"] == version
    assert (
        client.post(
            f"/api/v1/hr/forms/{form['id']}/publish", json={"expected_version": 1}, headers=h
        ).status_code
        == 409
    )


def test_monitor_status_and_manager_totals(client, signin, setup_appraisal):
    admin, manager, employee, a, h = setup_appraisal
    headers(signin, admin)
    page = client.get("/api/v1/hr/monitor").json()
    assert page["status_counts"]["NOT_STARTED"] == 1
    assert page["items"][0]["pending_action"] == "Start self-assessment"
    assert "goals" not in page["items"][0] and "score" not in page["items"][0]
    groups = client.get("/api/v1/hr/monitor?view=managers").json()
    assert groups["managers"][0]["manager_id"] == manager.id
    assert groups["managers"][0]["total"] == page["total"] == 1
    assert client.get("/api/v1/hr/monitor?status=SUBMITTED").json()["total"] == 0
    headers(signin, employee)
    assert client.get("/api/v1/hr/monitor").status_code == 403


def test_approved_report_access_and_own_privacy(client, signin, submitted_review, factory):
    admin, manager, employee, review, h = submitted_review
    review = complete_review(client, review, h)
    identifier = review["appraisal"]["id"]
    submitted = client.post(
        f"/api/v1/manager/appraisals/{identifier}/finalize", json=command(review), headers=h
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["appraisal"]["state"] == "HR_REVIEW"
    admin_headers = headers(signin, admin)
    calibration = client.get(f"/api/v1/hr/calibrations/{identifier}", headers=admin_headers).json()
    approved = client.post(
        f"/api/v1/hr/calibrations/{identifier}/approve",
        json={
            "expected_version": calibration["version"],
            "submitted_revision": calibration["submitted_revision"],
        },
        headers=admin_headers,
    )
    assert approved.status_code == 200, approved.text
    expected = approved.json()["score"]
    headers(signin, admin)
    response = client.get(f"/api/v1/hr/evaluations/{identifier}")
    assert response.status_code == 200, response.text
    assert response.json()["score"] == expected
    assert client.get("/api/v1/hr/evaluations").json()["total"] == 1
    excel = client.get("/api/v1/hr/evaluations/export/xlsx")
    assert excel.status_code == 200, excel.text[:200]
    book = load_workbook(BytesIO(excel.content))
    assert book["Evaluations"]["K2"].value == 3.8
    assert book["Responses"].max_row > 10
    assert client.get("/api/v1/hr/evaluations/export/pdf").content.startswith(b"%PDF")
    assert client.get("/api/v1/hr/evaluations/export/xlsx?q=no-match").status_code == 200
    with factory.begin() as db:
        db.add(UserRole(user_id=employee.id, role_code="SUPER_ADMIN"))
    headers(signin, employee)
    assert client.get("/api/v1/hr/evaluations").json()["total"] == 0
    assert client.get(f"/api/v1/hr/evaluations/{identifier}").status_code == 404
    assert client.get(f"/api/v1/hr/evaluations/export/pdf?appraisal_id={identifier}").status_code == 404
    assert (
        load_workbook(BytesIO(client.get("/api/v1/hr/evaluations/export/xlsx").content))[
            "Evaluations"
        ].max_row
        == 1
    )


def test_bulk_preview_confirm_and_replay(client, signin, user_factory, factory):
    admin = user_factory("SUPER_ADMIN")
    h = headers(signin, admin)
    rows = [
        {
            **profile(employee_id="001", email="one@example.org"),
            "role": "EMPLOYEE",
            "manager_employee_id": "002",
        },
        {**profile(employee_id="002", email="two@example.org"), "role": "MANAGER", "super_admin": True},
    ]
    preview = client.post("/api/v1/admin/user-imports/preview", content=workbook_bytes(rows), headers=h)
    assert preview.status_code == 200, preview.text
    assert preview.json()["errors"] == []
    batch = preview.json()["batch_id"]
    imported = client.post(f"/api/v1/admin/user-imports/{batch}/confirm", headers=h)
    assert imported.status_code == 201, imported.text
    assert imported.json()["created"] == 2
    assert all("#reset=" in link["setup_url"] for link in imported.json()["setup_links"])
    assert client.post(f"/api/v1/admin/user-imports/{batch}/confirm", headers=h).status_code == 409
    page = client.get("/api/v1/admin/users?q=001").json()
    assert page["items"][0]["employee_id"] == "001" and page["items"][0]["manager_id"]
    duplicate = client.post(
        "/api/v1/admin/user-imports/preview", content=workbook_bytes(rows), headers=h
    ).json()
    assert duplicate["batch_id"] is None and len(duplicate["errors"]) == 2


@pytest.mark.parametrize("attack", ["formula", "bad_zip", "empty", "macro"])
def test_reject_unsafe_import(attack):
    from app.core.errors import AppError

    data = workbook_bytes([{**profile(), "role": "EMPLOYEE"}])
    if attack == "formula":
        data = workbook_bytes([{**profile(full_name="=1+1"), "role": "EMPLOYEE"}])
    if attack == "bad_zip":
        data = b"not a workbook"
    if attack == "empty":
        data = template()
    if attack == "macro":
        from zipfile import ZipFile

        stream = BytesIO(data)
        with ZipFile(stream, "a") as archive:
            archive.writestr("xl/vbaProject.bin", b"blocked")
        data = stream.getvalue()
    with pytest.raises(AppError):
        read_file(data)


def test_configurable_scoring_and_required_questions():
    from app.core.errors import AppError
    from app.modules.reviews.scoring import calculate
    from tests.test_scoring import content, evaluation

    cfg = FormConfig(
        name="Goals only",
        competencies=[{"id": "one", "label": "Leadership", "leadership": True}],
        contributions_enabled=False,
        competencies_enabled=False,
        weights={"goals": 100, "contributions": 0, "competencies": 0},
        text_sections=[
            {
                "id": "manager",
                "title": "Manager context",
                "owner": "MANAGER",
                "questions": [{"id": "context", "label": "Context", "required": True}],
            }
        ],
        section_order=["goals", "contributions", "competencies", "development", "manager"],
    )
    definition = {"competencies": [], "form_config": cfg.model_dump()}
    value = evaluation(competencies=[])
    with pytest.raises(AppError):
        calculate(value, content(), competency_count=0, definition=definition)
    value.extra_answers = {"context": "Evidence"}
    result = calculate(value, content(), competency_count=0, definition=definition)
    assert result.overall.display == "4.0"
    assert result.sections[2].enabled is False
    invalid = deepcopy(cfg.model_dump())
    invalid["weights"]["goals"] = 90
    with pytest.raises(ValueError):
        FormConfig.model_validate(invalid)


def test_custom_employee_questions_required_and_owner_guard(client, signin, user_factory, factory):
    from app.modules.users.models import User

    admin = user_factory("SUPER_ADMIN")
    manager = user_factory("MANAGER")
    employee = user_factory()
    with factory.begin() as db:
        db.get(User, employee.id).manager_id = manager.id
    h = headers(signin, admin)
    cfg = client.get("/api/v1/hr/forms/default").json()
    cfg["text_sections"] = [
        {
            "id": "reflection",
            "title": "Reflection",
            "owner": "EMPLOYEE",
            "questions": [{"id": "impact", "label": "Impact", "required": True}],
        },
        {
            "id": "manager",
            "title": "Manager notes",
            "owner": "MANAGER",
            "questions": [{"id": "notes", "label": "Notes", "required": True}],
        },
    ]
    cfg["section_order"] += ["reflection", "manager"]
    template = client.post("/api/v1/hr/forms", json=cfg, headers=h).json()
    form = client.post(
        f"/api/v1/hr/forms/{template['id']}/publish", json={"expected_version": 1}, headers=h
    ).json()
    cycle = client.post(
        "/api/v1/cycles", json=cycle_body([employee.id], form_version_id=form["published_form_id"]), headers=h
    ).json()
    assert (
        client.post(
            f"/api/v1/cycles/{cycle['id']}/activate", json={"expected_version": 1}, headers=h
        ).status_code
        == 200
    )
    h = headers(signin, employee)
    a = client.get("/api/v1/me/appraisals").json()["items"][0]
    path = f"/api/v1/appraisals/{a['id']}"
    assert client.put(path + "/self-assessment", json=draft(), headers=h).status_code == 200
    assert client.post(path + "/submit", json={"expected_version": 2}, headers=h).status_code == 422
    assert (
        client.put(
            path + "/self-assessment",
            json=draft(2, development={"extra_answers": {"notes": "Wrong respondent"}}),
            headers=h,
        ).status_code
        == 422
    )
    assert (
        client.put(
            path + "/self-assessment",
            json=draft(2, development={"extra_answers": {"impact": "Delivered change"}}),
            headers=h,
        ).status_code
        == 200
    )
    assert client.post(path + "/submit", json={"expected_version": 3}, headers=h).status_code == 200
    headers(signin, manager)
    review = client.get(f"/api/v1/manager/appraisals/{a['id']}").json()
    assert review["employee_responses"]["development"]["extra_answers"] == {"impact": "Delivered change"}
    assert "Complete: Notes" in review["validation_errors"]


def test_bulk_atomic_revalidation_and_operator_isolation(client, signin, user_factory, factory):
    from app.modules.users.models import User

    first = user_factory("SUPER_ADMIN")
    second = user_factory("SUPER_ADMIN")
    h = headers(signin, first)
    rows = [
        {**profile(employee_id="NEW-A", email="a@example.org"), "role": "EMPLOYEE"},
        {**profile(employee_id="NEW-B", email="b@example.org"), "role": "EMPLOYEE"},
    ]
    preview = client.post(
        "/api/v1/admin/user-imports/preview", content=workbook_bytes(rows), headers=h
    ).json()
    identifier = preview["batch_id"]
    assert identifier
    with factory() as db:
        assert db.scalar(select(User).where(User.employee_id == "NEW-A")) is None
    other = headers(signin, second)
    assert client.post(f"/api/v1/admin/user-imports/{identifier}/confirm", headers=other).status_code == 404
    # Another admin creates one matching account after preview: reject the whole batch.
    response = client.post(
        "/api/v1/admin/users",
        json={
            **profile(employee_id="NEW-A", email="a@example.org"),
            "role": "EMPLOYEE",
            "temporary_password": "OtherPass8!",
        },
        headers=other,
    )
    assert response.status_code == 201, response.text
    h = headers(signin, first)
    assert client.post(f"/api/v1/admin/user-imports/{identifier}/confirm", headers=h).status_code == 409
    with factory() as db:
        assert db.scalar(select(User).where(User.employee_id == "NEW-B")) is None


def test_import_setup_link_works_once_and_is_hashed(client, signin, user_factory, factory):
    from app.core.security import token_hash
    from app.modules.auth.models import PasswordToken

    admin = user_factory("SUPER_ADMIN")
    h = headers(signin, admin)
    preview = client.post(
        "/api/v1/admin/user-imports/preview",
        content=workbook_bytes([{**profile(), "role": "EMPLOYEE"}]),
        headers=h,
    ).json()
    created = client.post(f"/api/v1/admin/user-imports/{preview['batch_id']}/confirm", headers=h).json()
    token = created["setup_links"][0]["setup_url"].split("#reset=")[1]
    with factory() as db:
        stored = db.scalar(
            select(PasswordToken).where(PasswordToken.user_id == created["setup_links"][0]["user_id"])
        )
        assert stored.token_hash == token_hash(token) and stored.token_hash != token
    body = {"token": token, "new_password": "ImportPass8!"}
    assert client.post("/api/v1/auth/complete-password-setup", json=body).status_code == 204
    assert client.post("/api/v1/auth/complete-password-setup", json=body).status_code == 400


@pytest.mark.parametrize("invalid", [1, "perhaps"])
def test_bulk_rejects_ambiguous_admin_flag(client, signin, user_factory, invalid):
    h = headers(signin, user_factory("SUPER_ADMIN"))
    response = client.post(
        "/api/v1/admin/user-imports/preview",
        content=workbook_bytes([{**profile(), "role": "EMPLOYEE", "super_admin": invalid}]),
        headers=h,
    )
    assert response.status_code == 200
    assert response.json()["batch_id"] is None and response.json()["errors"]
