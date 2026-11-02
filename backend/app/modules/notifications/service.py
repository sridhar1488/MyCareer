import logging
import smtplib
import ssl
from datetime import timedelta
from email.message import EmailMessage

from sqlalchemy import select

from app.db.base import utcnow
from app.modules.notifications.models import NotificationOutbox

logger = logging.getLogger(__name__)


def enqueue(db, settings, subject, body, to, cc=()):
    """Persist an alert in the caller's transaction; SMTP delivery is asynchronous."""
    if settings is None:
        return
    if not settings.mail_enabled:
        return
    recipients = [*to, *cc]
    if settings.mail_test_mode:
        recipients = [settings.mail_test_recipient]
        subject = f"[TEST] {subject}"
        body = f"TEST MODE - intended recipients: {', '.join([*to, *cc])}\n\n{body}"
    recipients = list(dict.fromkeys(address for address in recipients if address))
    if recipients:
        db.add(NotificationOutbox(recipients=recipients, subject=subject, body=body))


def _deliver(settings, item):
    message = EmailMessage()
    message["Subject"] = item.subject
    message["From"] = f"{settings.mail_from_name} <{settings.mail_from_address}>"
    message["To"] = ", ".join(item.recipients)
    message.set_content(item.body)
    context = ssl.create_default_context()
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        server.ehlo()
        if settings.smtp_starttls:
            server.starttls(context=context)
            server.ehlo()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password.get_secret_value())
        server.send_message(message)


async def deliver_pending(sessions, settings):
    """Deliver queued messages; failed messages are retried with bounded backoff."""
    import asyncio

    if not settings.mail_enabled:
        return
    now = utcnow()
    with sessions() as db:
        pending = db.scalars(
            select(NotificationOutbox)
            .where(NotificationOutbox.sent_at.is_(None), NotificationOutbox.available_at <= now)
            .order_by(NotificationOutbox.created_at)
            .limit(20)
        ).all()
        ids = [item.id for item in pending]
    for item_id in ids:
        with sessions() as db:
            item = db.scalar(
                select(NotificationOutbox).where(NotificationOutbox.id == item_id).with_for_update()
            )
            if not item or item.sent_at or item.available_at > utcnow():
                continue
            try:
                await asyncio.to_thread(_deliver, settings, item)
                item.sent_at = utcnow()
                item.last_error = None
            except Exception as exc:
                item.attempts += 1
                item.last_error = type(exc).__name__
                item.available_at = utcnow() + timedelta(seconds=min(3600, 30 * (2 ** min(item.attempts, 7))))
                logger.warning("Email delivery failed; retry scheduled (outbox id %s)", item.id)
            db.commit()
