from datetime import timedelta

from sqlalchemy import select

from app.db.base import utcnow
from app.modules.appraisals.models import AppraisalAttachment
from app.modules.auth.models import PasswordToken
from app.modules.notifications.models import NotificationOutbox
from tests.test_directory_appraisals import headers
from tests.test_directory_appraisals import setup_appraisal as setup_appraisal
from tests.test_manager_reviews import submitted_review as submitted_review


def test_directory_setup_link_email_modes_and_seven_day_expiry(client, signin, user_factory, factory):
    admin = user_factory("SUPER_ADMIN")
    employee = user_factory("EMPLOYEE", email="new.employee@example.org")
    settings = client.app.state.settings
    settings.mail_enabled = True
    settings.mail_test_mode = True
    settings.mail_test_recipient = "qa@example.org"

    response = client.post(
        f"/api/v1/admin/users/{employee.id}/setup-link",
        json={"expected_version": employee.version},
        headers=headers(signin, admin),
    )
    assert response.status_code == 200, response.text
    test_link = response.json()
    assert test_link["email_status"] == "test_only"
    assert "#reset=" in test_link["setup_url"]
    expires_at = utcnow().fromisoformat(test_link["expires_at"].replace("Z", "+00:00"))
    if expires_at.tzinfo:
        expires_at = expires_at.replace(tzinfo=None)
    assert timedelta(days=6, hours=23) < expires_at - utcnow() <= timedelta(days=7)
    with factory() as db:
        messages = db.scalars(select(NotificationOutbox).order_by(NotificationOutbox.created_at)).all()
        test_token = db.scalar(select(PasswordToken).where(PasswordToken.user_id == employee.id))
        # MySQL stores DATETIME to whole seconds while API timestamps retain microseconds.
        assert abs((test_token.expires_at - expires_at).total_seconds()) < 1
        assert len(messages) == 1
        assert messages[0].recipients == ["qa@example.org"]
        assert employee.email in messages[0].body
        assert "#reset=" not in messages[0].body

    settings.mail_test_mode = False
    response = client.post(
        f"/api/v1/admin/users/{employee.id}/setup-link",
        json={"expected_version": employee.version + 1},
        headers=headers(signin, admin),
    )
    assert response.status_code == 200, response.text
    live_link = response.json()
    assert live_link["email_status"] == "queued"
    with factory() as db:
        messages = db.scalars(select(NotificationOutbox).order_by(NotificationOutbox.created_at)).all()
        assert len(messages) == 2
        assert messages[1].recipients == [employee.email]
        assert live_link["setup_url"] in messages[1].body
        assert messages[1].sent_at is None


def test_pdf_and_image_previews_share_employee_manager_and_hr_access(
    client, signin, submitted_review, user_factory, factory, tmp_path
):
    admin, manager, employee, review, _ = submitted_review
    appraisal_id = review["appraisal"]["id"]
    settings = client.app.state.settings
    settings.attachment_directory = str(tmp_path)
    files = [
        ("proof.pdf", "application/pdf", b"%PDF-1.4\npreview test"),
        ("award.png", "image/png", b"\x89PNG\r\n\x1a\npreview test"),
        ("photo.jpg", "image/jpeg", b"\xff\xd8\xffpreview test"),
    ]
    with factory.begin() as db:
        for filename, media_type, content in files:
            (tmp_path / filename).write_bytes(content)
            db.add(
                AppraisalAttachment(
                    appraisal_id=appraisal_id,
                    uploader_id=employee.id,
                    original_name=filename,
                    object_key=filename,
                    media_type=media_type,
                    byte_size=len(content),
                    submitted_revision=review["submitted_revision"],
                )
            )

    authorized_users = [employee, manager, admin]
    for person in authorized_users:
        auth_headers = headers(signin, person)
        listed = client.get(f"/api/v1/appraisals/{appraisal_id}/attachments", headers=auth_headers)
        assert listed.status_code == 200
        assert len(listed.json()["items"]) == len(files)
        files_by_name = {filename: (media_type, content) for filename, media_type, content in files}
        for item in listed.json()["items"]:
            media_type, content = files_by_name[item["name"]]
            url = f"/api/v1/appraisals/{appraisal_id}/attachments/{item['id']}"
            preview = client.get(url + "?inline=true", headers=auth_headers)
            assert preview.status_code == 200
            assert preview.headers["content-type"].startswith(media_type)
            assert preview.headers["content-disposition"].startswith("inline;")
            assert preview.headers["content-security-policy"] == "default-src 'none'; sandbox"
            assert preview.headers["x-content-type-options"] == "nosniff"
            assert preview.headers["cache-control"] == "private, no-store"
            assert preview.content == content
            download = client.get(url, headers=auth_headers)
            assert download.status_code == 200
            assert download.headers["content-disposition"].startswith("attachment;")

    outsider = user_factory("EMPLOYEE")
    outsider_headers = headers(signin, outsider)
    assert (
        client.get(f"/api/v1/appraisals/{appraisal_id}/attachments", headers=outsider_headers).status_code
        == 404
    )
