import pytest
from sqlalchemy import select

from app.modules.appraisals.models import Appraisal
from app.modules.reviews.models import ReviewDraft
from tests.test_directory_appraisals import draft, headers
from tests.test_directory_appraisals import setup_appraisal as setup_appraisal


@pytest.fixture
def submitted_review(client, signin, setup_appraisal):
    admin, manager, employee, a, h = setup_appraisal
    path = f"/api/v1/appraisals/{a['id']}"
    assert client.put(path + "/self-assessment", json=draft(), headers=h).status_code == 200
    assert client.post(path + "/submit", json={"expected_version": 2}, headers=h).status_code == 200
    mh = headers(signin, manager)
    response = client.get(f"/api/v1/manager/appraisals/{a['id']}")
    assert response.status_code == 200, response.text
    return admin, manager, employee, response.json(), mh


def save_body(review):
    return {
        "expected_version": review["appraisal"]["version"],
        "submitted_revision": review["submitted_revision"],
        "evaluation": review["evaluation"],
    }


def test_manager_dashboard_hides_unsubmitted_content(client, signin, setup_appraisal):
    _, manager, _, a, _ = setup_appraisal
    headers(signin, manager)
    page = client.get("/api/v1/manager/appraisals?page_size=1").json()
    assert page["total"] == 1 and len(page["items"]) == 1
    assert page["items"][0]["submitted_revision"] == 0
    assert "goals" not in str(page)
    assert client.get(f"/api/v1/manager/appraisals/{a['id']}").status_code == 404


def test_save_manager_review_keeps_employee_content_unchanged(client, submitted_review, factory):
    _, _, _, review, h = submitted_review
    path = f"/api/v1/manager/appraisals/{review['appraisal']['id']}"
    body = save_body(review)
    body["evaluation"]["goals"][0] = {"rating": 4, "comment": "Specific manager feedback"}
    response = client.put(path + "/review", json=body, headers=h)
    assert response.status_code == 200, response.text
    assert response.json()["appraisal"]["state"] == "UNDER_REVIEW"
    assert response.json()["employee_responses"]["goals"] == review["employee_responses"]["goals"]
    assert client.put(path + "/review", json=body, headers=h).status_code == 409
    history = client.get(path + "/review-history").json()
    assert history["total"] == 1 and history["items"][0]["evaluation"]["goals"][0]["rating"] == 4
    with factory() as db:
        assert db.scalar(select(ReviewDraft)).submitted_revision == 1


@pytest.mark.parametrize("value", [0, 6, -1, 1.5, True, "4"])
def test_strict_manager_rating_validation(client, submitted_review, value):
    _, _, _, review, h = submitted_review
    body = save_body(review)
    body["evaluation"]["goals"][0]["rating"] = value
    assert (
        client.put(
            f"/api/v1/manager/appraisals/{review['appraisal']['id']}/review", json=body, headers=h
        ).status_code
        == 422
    )


@pytest.mark.parametrize("value", [1, 2, 3, 4, 5, None])
def test_all_source_ratings_and_missing_draft_rating(client, submitted_review, value):
    _, _, _, review, h = submitted_review
    body = save_body(review)
    body["evaluation"]["goals"][0]["rating"] = value
    assert (
        client.put(
            f"/api/v1/manager/appraisals/{review['appraisal']['id']}/review", json=body, headers=h
        ).status_code
        == 200
    )


@pytest.mark.parametrize("role", ["SUPER_ADMIN", "HR", "EMPLOYEE", "MANAGER"])
def test_other_actors_cannot_review(client, signin, user_factory, submitted_review, role):
    _, _, _, review, _ = submitted_review
    h = headers(signin, user_factory(role))
    path = f"/api/v1/manager/appraisals/{review['appraisal']['id']}"
    status = 404 if role == "MANAGER" else 403
    for suffix in ["", "/history", "/review-history"]:
        assert client.get(path + suffix).status_code == status
    assert client.put(path + "/review", json=save_body(review), headers=h).status_code == status
    assert (
        client.post(
            path + "/return",
            json={**{k: v for k, v in save_body(review).items() if k != "evaluation"}, "reason": "Revise"},
            headers=h,
        ).status_code
        == status
    )


def test_return_reason_resubmit_resets_draft_and_preserves_history(client, signin, submitted_review):
    _, manager, employee, review, h = submitted_review
    identifier = review["appraisal"]["id"]
    path = f"/api/v1/manager/appraisals/{identifier}"
    body = save_body(review)
    saved = client.put(path + "/review", json=body, headers=h).json()
    command = {"expected_version": saved["appraisal"]["version"], "submitted_revision": 1}
    assert client.post(path + "/return", json={**command, "reason": "   "}, headers=h).status_code == 422
    returned = client.post(
        path + "/return", json={**command, "reason": "Please clarify the result"}, headers=h
    )
    assert returned.status_code == 200
    eh = headers(signin, employee)
    ownpath = f"/api/v1/appraisals/{identifier}"
    own = client.get(ownpath).json()
    updated = client.put(ownpath + "/self-assessment", json=draft(own["version"], count=2), headers=eh).json()
    mh = headers(signin, manager)
    visible = client.get(path).json()
    assert len(visible["employee_responses"]["goals"]) == 1
    assert len(visible["appraisal"]["goals"]) == 1  # Returned live edits never leak.
    eh = headers(signin, employee)
    assert (
        client.post(
            ownpath + "/submit", json={"expected_version": updated["version"]}, headers=eh
        ).status_code
        == 200
    )
    assert "evaluation" not in client.get(ownpath).json()
    mh = headers(signin, manager)
    current = client.get(path).json()
    assert current["submitted_revision"] == 2 and not current["draft_is_current"]
    assert len(current["evaluation"]["goals"]) == 2
    assert client.get(path + "/review-history").json()["total"] == 1
    stale = save_body(current)
    stale["submitted_revision"] = 1
    assert client.put(path + "/review", json=stale, headers=mh).status_code == 409


def test_self_review_even_with_corrupt_assignment_is_denied(client, signin, factory, submitted_review):
    _, manager, _, review, _ = submitted_review
    with factory.begin() as db:
        a = db.get(Appraisal, review["appraisal"]["id"])
        a.employee_id = manager.id
    headers(signin, manager)
    assert client.get(f"/api/v1/manager/appraisals/{review['appraisal']['id']}").status_code == 404
    assert client.get("/api/v1/manager/appraisals").json()["total"] == 0
