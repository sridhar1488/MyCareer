from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select

from app.modules.appraisals.models import Appraisal
from app.modules.reviews.models import Acknowledgement, FinalEvaluation
from app.modules.users.models import User
from tests.test_directory_appraisals import draft
from tests.test_scoring import evaluation
from tests.test_workflow_concurrency import account, appraisal_fixture, login
from tests.test_workflow_concurrency import concurrent_app as concurrent_app


def ready_for_signoff(app):
    employee, a = appraisal_fixture(app)
    with login(app, employee) as browser:
        assert browser.put(f"/api/v1/appraisals/{a.id}/self-assessment", json=draft()).status_code == 200
        assert (
            browser.post(f"/api/v1/appraisals/{a.id}/submit", json={"expected_version": 2}).status_code == 200
        )
    with app.state.sessions() as db:
        manager = db.get(User, a.manager_id)
    with login(app, manager) as browser:
        response = browser.put(
            f"/api/v1/manager/appraisals/{a.id}/review",
            json={"expected_version": 3, "submitted_revision": 1, "evaluation": evaluation().model_dump()},
        )
        assert response.status_code == 200, response.text
    return employee, manager, a


@pytest.mark.parametrize("competing_action", ["return", "review", "finalize"])
def test_concurrent_finalize_and_competing_write_have_one_winner(concurrent_app, competing_action):
    app = concurrent_app
    _, manager, a = ready_for_signoff(app)
    clients = [login(app, manager), login(app, manager)]
    base = f"/api/v1/manager/appraisals/{a.id}"
    data = {"expected_version": 4, "submitted_revision": 1}

    def attempt(i):
        if i == 0 or competing_action == "finalize":
            return (
                clients[i]
                .post(base + "/finalize", json=data)
                .status_code
            )
        if competing_action == "return":
            return clients[i].post(base + "/return", json={**data, "reason": "Clarify results"}).status_code
        return (
            clients[i]
            .put(base + "/review", json={**data, "evaluation": evaluation((3,)).model_dump()})
            .status_code
        )

    with ThreadPoolExecutor(max_workers=2) as workers:
        statuses = list(workers.map(attempt, range(2)))
    assert sorted(statuses) == [200, 409]
    with app.state.sessions() as db:
        record = db.get(Appraisal, a.id)
        count = db.scalar(select(func.count()).select_from(FinalEvaluation))
        assert record.state == "HR_REVIEW" and count == 0
    for client in clients:
        client.close()


def test_release_once_and_acknowledgement_idempotent_under_concurrency(concurrent_app):
    app = concurrent_app
    employee, manager, a = ready_for_signoff(app)
    base = f"/api/v1/manager/appraisals/{a.id}"
    with login(app, manager) as client:
        final = client.post(
            base + "/finalize",
            json={"expected_version": 4, "submitted_revision": 1},
        )
        assert final.status_code == 200
        assert final.json()["appraisal"]["state"] == "HR_REVIEW"
    admin = account(app, "SUPER_ADMIN")
    with login(app, admin) as hr:
        calibration = hr.get(f"/api/v1/hr/calibrations/{a.id}").json()
        approved = hr.post(
            f"/api/v1/hr/calibrations/{a.id}/approve",
            json={"expected_version": calibration["version"], "submitted_revision": calibration["submitted_revision"]},
        )
        assert approved.status_code == 200, approved.text
        score = approved.json()["score"]
    with login(app, manager) as manager_client:
        review = manager_client.get(base).json()
        release_body = {
            "expected_version": review["appraisal"]["version"],
            "submitted_revision": review["submitted_revision"],
            "review_meeting_confirmed": True,
        }
    clients = [login(app, manager), login(app, manager)]

    def release(i):
        return (
            clients[i]
            .post(base + "/release", json=release_body)
            .status_code
        )

    with ThreadPoolExecutor(max_workers=2) as workers:
        assert sorted(workers.map(release, range(2))) == [200, 409]
    for client in clients:
        client.close()
    clients = [login(app, employee), login(app, employee)]

    def acknowledge(i):
        return clients[i].post(f"/api/v1/appraisals/{a.id}/acknowledge", json={"expected_version": 6})

    with ThreadPoolExecutor(max_workers=2) as workers:
        responses = list(workers.map(acknowledge, range(2)))
    assert all(r.status_code == 200 and r.json()["score"] == score for r in responses)
    with app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(Acknowledgement)) == 1
    for client in clients:
        client.close()
