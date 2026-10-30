import time

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.core.errors import AppError
from app.core.security import private_key
from app.modules.auth.models import RateLimit


def throttle(factory, settings, action: str, ip: str, principal: str):
    """Atomic persistent counters, shared across workers and committed even on rejected login."""
    window_seconds = settings.rate_window_seconds
    window = int(time.time()) // window_seconds
    secret = settings.secret_key.get_secret_value()
    buckets = [private_key(secret, f"{action}:ip:{ip}"), private_key(secret, f"{action}:user:{principal}")]
    limit = settings.login_attempts
    over = False
    with factory.begin() as db:
        for bucket in sorted(buckets):
            values = {"bucket": bucket, "window": window, "attempts": 1}
            if db.bind.dialect.name == "mysql":
                statement = mysql_insert(RateLimit).values(**values)
                statement = statement.on_duplicate_key_update(attempts=RateLimit.attempts + 1)
            else:
                statement = sqlite_insert(RateLimit).values(**values)
                statement = statement.on_conflict_do_update(
                    index_elements=[RateLimit.bucket, RateLimit.window],
                    set_={"attempts": RateLimit.attempts + 1},
                )
            db.execute(statement)
            count = db.scalar(
                select(RateLimit.attempts).where(RateLimit.bucket == bucket, RateLimit.window == window)
            )
            over = over or count > (limit * 5 if bucket == buckets[0] else limit)
    if over:
        retry = window_seconds - int(time.time()) % window_seconds
        raise AppError(
            429, "RATE_LIMITED", "Too many attempts. Please try again later.", {"Retry-After": str(retry)}
        )
