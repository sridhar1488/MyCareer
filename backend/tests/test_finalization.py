import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from app.modules.appraisals.models import Cycle
from app.modules.reviews.models import FinalEvaluation
from tests.test_directory_appraisals import headers
from tests.test_directory_appraisals import setup_appraisal as setup_appraisal
from tests.test_manager_reviews import save_body
from tests.test_manager_reviews import submitted_review as submitted_review
from tests.test_scoring import evaluation


@pytest.mark.parametrize("role", ["SUPER_ADMIN", "MANAGER", "EMPLOYEE"])
def test_personal_role_never_reveals_own_unreleased_score(client, signin, submitted_review, factory, role):
    from sqlalchemy import delete

    from app.modules.users.models import UserRole

    _, _, employee, review, h = submitted_review
    review = complete_review(client, review, h)
    identifier = review["appraisal"]["id"]
    assert (
        client.post(
            f"/api/v1/manager/appraisals/{identifier}/finalize",
            json=command(review),
            headers=h,
        ).status_code
        == 200
    )
    with factory.begin() as db:
        db.execute(delete(UserRole).where(UserRole.user_id == employee.id))
        db.add(UserRole(user_id=employee.id, role_code=role))
    headers(signin, employee)
    assert client.get(f"/api/v1/appraisals/{identifier}/released-result").status_code == 404
    personal = client.get(f"/api/v1/appraisals/{identifier}").json()
    assert "evaluation" not in personal and "score" not in personal
    if role == "MANAGER":
        assert client.get(f"/api/v1/manager/appraisals/{identifier}").status_code == 404


def complete_review(client, review, h):
    body = save_body(review)
    body["evaluation"] = evaluation().model_dump()
    response = client.put(
        f"/api/v1/manager/appraisals/{review['appraisal']['id']}/review", json=body, headers=h
    )
    assert response.status_code == 200, response.text
    return response.json()


def command(review, **extra):
    return {
        "expected_version": review["appraisal"]["version"],
        "submitted_revision": review["submitted_revision"],
        **extra,
    }


def approve_in_hr(client, signin, admin, appraisal_id):
    h = headers(signin, admin)
    detail = client.get(f"/api/v1/hr/calibrations/{appraisal_id}", headers=h)
    assert detail.status_code == 200, detail.text
    result = detail.json()
    response = client.post(
        f"/api/v1/hr/calibrations/{appraisal_id}/approve",
        json={"expected_version": result["version"], "submitted_revision": result["submitted_revision"]},
        headers=h,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_finalize_release_acknowledge_and_immutable_artifacts(client, signin, submitted_review, factory):
    admin, manager, employee, review, h = submitted_review
    identifier = review["appraisal"]["id"]
    path = f"/api/v1/manager/appraisals/{identifier}"
    own = f"/api/v1/appraisals/{identifier}"
    review = complete_review(client, review, h)
    assert review["score_preview"]["overall"]["display"] == "3.8"
    final = client.post(path + "/finalize", json=command(review), headers=h)
    assert final.status_code == 200, final.text
    review = final.json()
    assert review["appraisal"]["state"] == "HR_REVIEW" and review["final_result"] is None
    for suffix, method, body in [
        ("/review", client.put, {**command(review), "evaluation": evaluation().model_dump()}),
        ("/return", client.post, command(review, reason="Override")),
        ("/finalize", client.post, command(review)),
    ]:
        assert method(path + suffix, json=body, headers=h).status_code == 409
    assert client.post(
        path + "/release", json={**command(review), "review_meeting_confirmed": True}, headers=h
    ).status_code == 409
    eh = headers(signin, employee)
    assert client.get(own + "/released-result").status_code == 404
    assert "evaluation" not in client.get(own).json()
    assert (
        client.post(
            own + "/acknowledge", json={"expected_version": review["appraisal"]["version"]}, headers=eh
        ).status_code
        == 404
    )
    approve_in_hr(client, signin, admin, identifier)
    h = headers(signin, manager)
    review = client.get(path, headers=h).json()
    score = review["final_result"]["score"]
    missing_meeting = client.post(path + "/release", json={**command(review), "review_meeting_confirmed": False}, headers=h)
    assert missing_meeting.status_code == 422 and missing_meeting.json()["error"]["code"] == "MEETING_REQUIRED"
    release_body = {**command(review), "review_meeting_confirmed": True}
    released = client.post(path + "/release", json=release_body, headers=h)
    assert released.status_code == 200, released.text
    review = released.json()
    assert review["final_result"]["score"] == score
    assert client.post(path + "/release", json={**command(review), "review_meeting_confirmed": True}, headers=h).status_code == 409
    eh = headers(signin, employee)
    result = client.get(own + "/released-result").json()
    assert result["score"] == score and result["released_at"] and not result["acknowledged_at"]
    ack = client.post(
        own + "/acknowledge", json={"expected_version": result["appraisal_version"]}, headers=eh
    )
    assert ack.status_code == 200 and ack.json()["acknowledged_at"] and ack.json()["score"] == score
    repeated = client.post(
        own + "/acknowledge", json={"expected_version": result["appraisal_version"]}, headers=eh
    )
    assert repeated.json()["acknowledged_at"] == ack.json()["acknowledged_at"]
    for table in [
        "final_evaluations",
        "appraisal_releases",
        "appraisal_acknowledgements",
        "manager_review_events",
    ]:
        for statement in [f"DELETE FROM {table}", f"UPDATE {table} SET appraisal_id=appraisal_id"]:
            with factory() as db:
                with pytest.raises(DatabaseError):
                    db.execute(text(statement))
                db.rollback()
    with factory() as db:
        final = db.get(FinalEvaluation, identifier)
        assert final.score == score and final.policy["empty_contributions"].startswith("zero")


def test_incomplete_draft_cannot_finalize(client, submitted_review):
    _, _, _, review, h = submitted_review
    identifier = review["appraisal"]["id"]
    path = f"/api/v1/manager/appraisals/{identifier}"
    review = client.put(path + "/review", json=save_body(review), headers=h).json()
    assert not review["score_preview"] and review["validation_errors"]
    response = client.post(path + "/finalize", json=command(review), headers=h)
    assert response.status_code == 422 and response.json()["error"]["code"] == "INCOMPLETE_REVIEW"


def test_approved_results_do_not_recalculate_when_policy_registry_changes(
    client, signin, submitted_review, factory, monkeypatch
):
    admin, manager, employee, review, h = submitted_review
    review = complete_review(client, review, h)
    path = f"/api/v1/manager/appraisals/{review['appraisal']['id']}"
    review = client.post(path + "/finalize", json=command(review), headers=h).json()
    approve_in_hr(client, signin, admin, review["appraisal"]["id"])
    h = headers(signin, manager)
    review = client.get(path, headers=h).json()
    score = review["final_result"]["score"]

    def forbidden(*args, **kwargs):
        raise AssertionError("Final scores must never be recalculated")

    monkeypatch.setattr("app.modules.reviews.scoring.calculate", forbidden)
    monkeypatch.setattr("app.modules.reviews.scoring.policy", forbidden)
    with factory.begin() as db:
        db.get(Cycle, review["appraisal"]["cycle_id"]).scoring_policy_version = "future-policy"
    assert client.get(path).json()["final_result"]["score"] == score
    released = client.post(path + "/release", json={**command(review), "review_meeting_confirmed": True}, headers=h)
    assert released.status_code == 200 and released.json()["final_result"]["score"] == score
    headers(signin, employee)
    assert (
        client.get(f"/api/v1/appraisals/{review['appraisal']['id']}/released-result").json()["score"] == score
    )


@pytest.mark.parametrize("role", ["SUPER_ADMIN", "EMPLOYEE", "MANAGER"])
def test_unrelated_and_own_unreleased_results_are_hidden(
    client, signin, user_factory, submitted_review, role
):
    _, _, _, review, h = submitted_review
    review = complete_review(client, review, h)
    identifier = review["appraisal"]["id"]
    client.post(
        f"/api/v1/manager/appraisals/{identifier}/finalize",
        json=command(review),
        headers=h,
    )
    h = headers(signin, user_factory(role))
    assert client.get(f"/api/v1/appraisals/{identifier}/released-result").status_code == 404
    assert (
        client.post(
            f"/api/v1/appraisals/{identifier}/acknowledge", json={"expected_version": 1}, headers=h
        ).status_code
        == 404
    )
    expected = 404 if role == "MANAGER" else 403
    for action, extra in [("finalize", {}), ("release", {"review_meeting_confirmed": True})]:
        assert (
            client.post(
                f"/api/v1/manager/appraisals/{identifier}/{action}", json=command(review, **extra), headers=h
            ).status_code
            == expected
        )
