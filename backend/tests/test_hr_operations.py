import asyncio
import json
from copy import deepcopy
from datetime import date, datetime
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from app.core.config import Settings
from app.modules.appraisals.models import FormVersion
from app.modules.forms.config import config_for
from app.modules.forms.schemas import FormConfig
from app.modules.imports.service import COLUMNS, FIELDS, read_file, template
from app.modules.notifications.service import deliver_pending
from app.modules.users.models import UserRole
from tests.test_directory_appraisals import cycle_body, draft, headers, profile
from tests.test_directory_appraisals import setup_appraisal as setup_appraisal
from tests.test_finalization import command, complete_review
from tests.test_manager_reviews import submitted_review as submitted_review


def workbook_bytes(rows):
    book = load_workbook(BytesIO(template()))
    for i, row in enumerate(rows, 2):
        values = {
            "employee_id": row.get("employee_id", ""),
            "full_name": row.get("full_name", ""),
            "email": row.get("email", ""),
            "location": row.get("location", ""),
            "department": row.get("department", ""),
            "designation": row.get("designation", ""),
            "reporting_to": row.get("reporting_to", row.get("manager_employee_id", "")),
            "date_joined": row.get("date_joined", ""),
        }
        for j, key in enumerate(FIELDS, 1):
            book["Users"].cell(i, j, values[key])
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
    for field, value in (("goal_title_max_length", 501), ("goal_description_max_length", 1001)):
        assert client.post("/api/v1/hr/forms", json={**cfg, field: value}, headers=h).status_code == 422
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
    assert [cell.value for cell in book["Evaluations"][1]] == [
        "Cycle",
        "Employee ID",
        "Employee",
        "Department",
        "Manager",
        "Status",
        "Approved Date",
        "Overall / 5",
    ]
    assert book["Evaluations"]["H2"].value == 3.8
    assert book["Evaluations"].auto_filter.ref == "A1:H2"
    assert book["Responses"].max_row > 10
    assert client.get("/api/v1/hr/evaluations/export/pdf").content.startswith(b"%PDF")
    assert client.get("/api/v1/hr/evaluations/export/xlsx?q=no-match").status_code == 200
    analytics_path = "/api/v1/hr/analytics"
    download_path = f"{analytics_path}/export/xlsx"
    pdf_path = f"{analytics_path}/export/pdf"
    cycle_filter = {"cycle_id": review["appraisal"]["cycle_id"]}
    analytics = client.get(analytics_path, params=cycle_filter).json()
    pdf = client.get(pdf_path, params=cycle_filter)
    assert pdf.status_code == 200, pdf.text[:200]
    assert pdf.content.startswith(b"%PDF")
    assert pdf.headers["Content-Type"] == "application/pdf"
    assert 'filename="hr-analytics.pdf"' in pdf.headers["Content-Disposition"]
    assert pdf.headers["Cache-Control"] == "private, no-store"
    downloaded = client.get(download_path, params=cycle_filter)
    assert downloaded.status_code == 200, downloaded.text[:200]
    assert 'filename="hr-analytics.xlsx"' in downloaded.headers["Content-Disposition"]
    assert downloaded.headers["Cache-Control"] == "private, no-store"
    workbook = load_workbook(BytesIO(downloaded.content))
    assert workbook["Summary"]["B2"].value == review["appraisal"]["cycle_title"]
    assert workbook["Summary"]["B3"].value == analytics["summary"]["appraisal_count"] == 1
    assert workbook["Summary"]["B5"].value == 1
    assert workbook["Summary"]["B6"].value == float(analytics["summary"]["approved_average"])
    distribution = workbook["Score distribution"]
    assert [distribution[f"C{row}"].value for row in range(31, 39)] == analytics["distribution"]["bin_counts"]
    assert [distribution[f"F{row}"].value for row in range(31, 112)] == pytest.approx(
        analytics["distribution"]["reference_counts"]
    )
    assert [series.title.v for series in distribution._charts[0].series] == [
        "Observed score counts",
        "Bell curve reference",
        "Individual employee score",
    ]
    assert tuple(cell.value for cell in workbook["Employee scores"][2]) == (
        employee.employee_id,
        employee.full_name,
        3.8,
        "Yes",
    )
    assert workbook["Departments"]["E2"].value == float(analytics["departments"][0]["average_score"])
    assert workbook["Top performers"]["G2"].value == float(analytics["top_performers"][0]["average_score"])
    assert len(workbook["Departments"]._charts) == len(workbook["Top performers"]._charts) == 1
    department_chart = workbook["Departments"]._charts[0]
    assert department_chart.type == "col"
    assert department_chart.title.tx.rich.p[0].r[0].t == "Department score comparison"
    assert department_chart.series[0].cat.strRef.strCache.pt[0].v == analytics["departments"][0]["department"]
    assert department_chart.series[0].val.numRef.numCache.pt[0].v == workbook["Departments"]["E2"].value
    assert workbook["Top performers"]._charts[0].type == "bar"
    empty = client.get(download_path, params={"cycle_id": "unmatched"})
    assert empty.status_code == 200
    empty_book = load_workbook(BytesIO(empty.content))
    assert empty_book["Summary"]["B3"].value == 0
    assert empty_book["Score distribution"]._charts == []
    assert client.get(pdf_path, params={"cycle_id": "unmatched"}).content.startswith(b"%PDF")
    headers(signin, manager)
    assert client.get(download_path).status_code == 403
    assert client.get(pdf_path).status_code == 403
    with factory.begin() as db:
        db.add(UserRole(user_id=employee.id, role_code="SUPER_ADMIN"))
    headers(signin, employee)
    own = client.get(download_path, params=cycle_filter)
    assert own.status_code == 200
    own_book = load_workbook(BytesIO(own.content))
    assert own_book["Employee scores"].max_row == 1
    assert client.get("/api/v1/hr/evaluations").json()["total"] == 0
    assert client.get(f"/api/v1/hr/evaluations/{identifier}").status_code == 404
    assert client.get(f"/api/v1/hr/evaluations/export/pdf?appraisal_id={identifier}").status_code == 404
    assert (
        load_workbook(BytesIO(client.get("/api/v1/hr/evaluations/export/xlsx").content))[
            "Evaluations"
        ].max_row
        == 1
    )


def test_calibration_grid_export_and_overall_override(client, signin, submitted_review, factory):
    from app.modules.users.models import User

    admin, manager, employee, review, manager_headers = submitted_review
    review = complete_review(client, review, manager_headers)
    appraisal_id = review["appraisal"]["id"]
    assert (
        client.post(
            f"/api/v1/manager/appraisals/{appraisal_id}/finalize",
            json=command(review),
            headers=manager_headers,
        ).status_code
        == 200
    )

    queue = "/api/v1/hr/calibrations"
    export = queue + "/export/xlsx"
    path = f"{queue}/{appraisal_id}"
    assert client.get(queue).status_code == 403
    assert client.get(export).status_code == 403
    assert client.put(path + "/overall-score", json={}, headers=manager_headers).status_code == 403
    hr_headers = headers(signin, admin)
    rows = client.get(queue, params={"q": employee.employee_id}).json()
    row = rows["items"][0]
    assert rows["total"] == 1
    assert row["manager_overall"] == row["calibrated_overall"] == "3.8"
    assert row["form_name"]
    assert "employee_email" not in row and "date_joined" not in row
    assert client.get(queue, params={"cycle_id": "missing"}).json()["total"] == 0
    assert client.get(queue, params={"page": 2, "page_size": 1}).json()["items"] == []

    version = {"expected_version": row["version"], "submitted_revision": row["submitted_revision"]}
    for invalid in ("-0.1", "5.1", "4.27"):
        assert (
            client.put(
                path + "/overall-score",
                json={**version, "score": invalid, "reason": "Test"},
                headers=hr_headers,
            ).status_code
            == 422
        )
    assert (
        client.put(
            path + "/overall-score",
            json={**version, "score": "4.2", "reason": "  "},
            headers=hr_headers,
        ).status_code
        == 422
    )
    assert (
        client.put(
            path + "/overall-score",
            json={**version, "score": "4.2", "reason": "R" * 1001},
            headers=hr_headers,
        ).status_code
        == 422
    )
    assert (
        client.put(
            path + "/overall-score",
            json={**version, "score": "4.2", "reason": "HR read-across discussion"},
            headers=hr_headers,
        ).status_code
        == 204
    )
    assert client.post(path + "/approve", json=version, headers=hr_headers).status_code == 409

    response = client.get(export, params={"q": employee.employee_id, "page": 2})
    assert response.status_code == 200 and "no-store" in response.headers["cache-control"]
    assert load_workbook(BytesIO(response.content))["Calibration queue"]["D2"].value is None
    joining_date = date(2020, 7, 11)
    with factory.begin() as db:
        db.get(User, employee.id).date_joined = joining_date
    response = client.get(export, params={"q": employee.employee_id, "page": 2})
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.content))
    grid = book["Calibration queue"]
    assert [cell.value for cell in grid[1]] == [
        "Employee ID",
        "EMP Name",
        "Email",
        "Joining Date",
        "Department",
        "Manager",
        "Cycle",
        "Manager score / 5",
        "Calibrated score / 5",
        "Approval status",
        "Manager submitted (UTC)",
    ]
    assert grid["A2"].value == employee.employee_id and grid["A2"].data_type == "s"
    assert grid["B2"].value == row["employee_name"]
    assert grid["C2"].value == employee.email
    assert grid["D2"].is_date and grid["D2"].value.date() == joining_date
    assert [grid[f"{c}2"].value for c in "EFG"] == [
        row["department"],
        row["manager_name"],
        row["cycle_title"],
    ]
    assert [grid[f"{c}2"].value for c in "HI"] == [3.8, 4.2]
    assert grid["J2"].value == "Waiting for HR approval"
    submitted_at = datetime.fromisoformat(row["manager_submitted_at"]).replace(tzinfo=None)
    assert grid["K2"].is_date and abs((grid["K2"].value - submitted_at).total_seconds()) < 0.001
    assert grid.auto_filter.ref == "A1:K2"
    assert grid.freeze_panes == "B2"
    assert book.sheetnames == ["Calibration queue"]
    filtered = load_workbook(BytesIO(client.get(export, params={"cycle_id": "missing"}).content))
    assert filtered["Calibration queue"].max_row == 1

    detail = client.get(path).json()
    assert detail["score_preview"]["overall"]["display"] == "4.2"
    assert detail["events"][-1]["reason"] == "HR read-across discussion"
    assert detail["events"][-1]["actor_name"] == admin.full_name
    version["expected_version"] = detail["version"]
    assert (
        client.put(
            path + "/overall-score",
            json={**version, "score": None, "reason": "Restore calculation"},
            headers=hr_headers,
        ).status_code
        == 204
    )
    detail = client.get(path).json()
    assert detail["score_preview"]["overall"]["display"] == "3.8"
    assert "calculated_overall" not in detail["score_preview"]
    version["expected_version"] = detail["version"]
    assert (
        client.put(
            path + "/overall-score",
            json={**version, "score": "4.2", "reason": "Confirm override"},
            headers=hr_headers,
        ).status_code
        == 204
    )
    detail = client.get(path).json()
    changed = detail["evaluation"]
    changed["goals"][0]["rating"] = 5
    version["expected_version"] = detail["version"]
    saved = client.put(
        path,
        json={**version, "evaluation": changed, "reason": "Adjust the item rating"},
        headers=hr_headers,
    )
    assert saved.status_code == 200, saved.text
    calibrated = saved.json()
    assert calibrated["score_preview"]["overall"]["display"] == "4.2"
    assert calibrated["score_preview"]["calculated_overall"]["display"] == "4.5"
    assert calibrated["manager_score"]["overall"]["display"] == "3.8"

    version["expected_version"] = calibrated["version"]
    approved = client.post(path + "/approve", json=version, headers=hr_headers)
    assert approved.status_code == 200, approved.text
    assert approved.json()["score"] == calibrated["score_preview"]
    assert client.get(queue).json()["total"] == 0
    assert (
        client.put(
            path + "/overall-score",
            json={**version, "score": "4.3", "reason": "Post approval"},
            headers=hr_headers,
        ).status_code
        == 409
    )

    manager_headers = headers(signin, manager)
    manager_path = f"/api/v1/manager/appraisals/{appraisal_id}"
    manager_detail = client.get(manager_path).json()
    assert (
        client.post(
            manager_path + "/release",
            json={**command(manager_detail), "review_meeting_confirmed": True},
            headers=manager_headers,
        ).status_code
        == 200
    )
    headers(signin, employee)
    result = client.get(f"/api/v1/appraisals/{appraisal_id}/released-result").json()
    assert result["score"] == calibrated["score_preview"]


def test_bulk_preview_confirm_and_replay(client, signin, user_factory, factory):
    admin = user_factory("SUPER_ADMIN")
    h = headers(signin, admin)
    rows = [
        {
            **profile(employee_id="001", email="one@example.org"),
            "location": "Bengaluru",
            "date_joined": "2020-02-03",
            "reporting_to": "002",
        },
        {**profile(employee_id="002", email="two@example.org")},
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
    assert page["items"][0]["location"] == "Bengaluru"
    assert page["items"][0]["date_joined"] == "2020-02-03"
    manager = client.get("/api/v1/admin/users?q=002").json()["items"][0]
    assert manager["roles"] == ["MANAGER"]
    duplicate = client.post(
        "/api/v1/admin/user-imports/preview", content=workbook_bytes(rows), headers=h
    ).json()
    assert duplicate["batch_id"] is None and len(duplicate["errors"]) == 2


@pytest.mark.parametrize("attack", ["formula", "bad_zip", "empty", "macro"])
def test_reject_unsafe_import(attack):
    from app.core.errors import AppError

    data = workbook_bytes([profile()])
    if attack == "formula":
        data = workbook_bytes([profile(full_name="=1+1")])
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
    cfg.update(goal_title_max_length=12, goal_description_max_length=40)
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
    for title, narrative in [("G" * 13, "Evidence"), ("Goal", "A" * 41)]:
        invalid = client.put(
            path + "/self-assessment",
            json=draft(goals=[{"description": title, "employee_narrative": narrative}]),
            headers=h,
        )
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "GOAL_TEXT_LIMIT"
    assert client.put(path + "/self-assessment", json=draft(), headers=h).status_code == 200
    assert client.post(path + "/submit", json={"expected_version": 2}, headers=h).status_code == 422
    assert (
        client.put(
            path + "/self-assessment",
            json=draft(2, development={"extra_answers": {"impact": "A" * 1001}}),
            headers=h,
        ).status_code
        == 422
    )
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
        {**profile(employee_id="NEW-A", email="a@example.org")},
        {**profile(employee_id="NEW-B", email="b@example.org")},
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


@pytest.mark.parametrize("alternate_url", ["", "https://mycareer-vpn.example.org"])
def test_confirmed_import_sends_each_employee_their_setup_link(
    client,
    signin,
    user_factory,
    factory,
    tmp_path,
    monkeypatch,
    alternate_url,
):
    monkeypatch.setattr("app.main.deliver_pending", AsyncMock())
    smtp = MagicMock()
    smtp_class = MagicMock()
    smtp_class.return_value.__enter__.return_value = smtp
    monkeypatch.setattr("app.modules.notifications.service.smtplib.SMTP", smtp_class)
    app_url = "https://mycareer.example.org"
    current = client.app.state.settings
    allowed_origins = [*current.allowed_origins, app_url]
    if alternate_url:
        allowed_origins.append(alternate_url)
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"MI_MAIL_ENABLED=true\nMI_MAIL_TEST_MODE=false\nMI_PUBLIC_BASE_URL={app_url}\n"
        f"MI_ALTERNATE_PUBLIC_BASE_URL={alternate_url}\nMI_ALLOWED_ORIGINS={json.dumps(allowed_origins)}\n"
        "MI_SMTP_HOST=smtp.example.org\nMI_MAIL_FROM_ADDRESS=mycareer@example.org\n",
        encoding="utf-8",
    )
    settings = Settings(
        _env_file=env_file,
        environment="test",
        database_url=current.database_url,
        secret_key=current.secret_key,
    )
    current.allowed_origins = allowed_origins
    client.app.state.settings = settings
    h = headers(signin, user_factory("SUPER_ADMIN"))
    rows = [profile(employee_id=f"MAIL-{index}", email=f"employee{index}@example.org") for index in (1, 2)]
    preview = client.post(
        "/api/v1/admin/user-imports/preview", content=workbook_bytes(rows), headers=h
    ).json()
    confirmed = client.post(f"/api/v1/admin/user-imports/{preview['batch_id']}/confirm", headers=h)
    assert confirmed.status_code == 201, confirmed.text
    links = {link["email"]: link["setup_url"] for link in confirmed.json()["setup_links"]}
    assert set(links) == {row["email"] for row in rows}

    asyncio.run(deliver_pending(factory, settings))
    messages = [call.args[0] for call in smtp.send_message.call_args_list]
    assert len(messages) == 2
    assert {str(message["To"]) for message in messages} == set(links)
    for message in messages:
        recipient = str(message["To"])
        body = message.get_content()
        assert links[recipient].startswith(f"{app_url}/#reset=")
        assert links[recipient] in body
        assert f"sign in at {app_url} with your work email ({recipient})" in body
        assert "can only be used once" in body
        assert all(link not in body for email, link in links.items() if email != recipient)
        if alternate_url:
            token = links[recipient].split("#reset=", 1)[1]
            assert f"{alternate_url}/#reset={token}" in body
            assert f"Alternate sign-in address: {alternate_url}" in body
            setup = {"token": token, "new_password": "ImportPass8!"}
            path = "/api/v1/auth/complete-password-setup"
            assert client.post(path, json=setup, headers={"Origin": alternate_url}).status_code == 204
            assert client.post(path, json=setup, headers={"Origin": app_url}).status_code == 400
        else:
            assert "Alternate setup link" not in body


def test_import_setup_link_works_once_and_is_hashed(client, signin, user_factory, factory):
    from app.core.security import token_hash
    from app.modules.auth.models import PasswordToken

    admin = user_factory("SUPER_ADMIN")
    h = headers(signin, admin)
    preview = client.post(
        "/api/v1/admin/user-imports/preview",
        content=workbook_bytes([profile()]),
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


@pytest.mark.parametrize("legacy_header", ["Role", "Super Admin"])
def test_hrms_import_rejects_legacy_role_columns(client, signin, user_factory, legacy_header):
    h = headers(signin, user_factory("SUPER_ADMIN"))
    book = load_workbook(BytesIO(workbook_bytes([profile()])))
    sheet = book["Users"]
    sheet.cell(1, len(COLUMNS) + 1, legacy_header)
    sheet.cell(2, len(COLUMNS) + 1, "SUPER_ADMIN")
    stream = BytesIO()
    book.save(stream)
    response = client.post(
        "/api/v1/admin/user-imports/preview",
        content=stream.getvalue(),
        headers=h,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_IMPORT"
