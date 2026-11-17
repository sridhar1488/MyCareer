"""Present timestamps in India Standard Time at the application boundary."""

from datetime import UTC, datetime, timedelta, timezone
from typing import Annotated

from pydantic import PlainSerializer

IST = timezone(timedelta(hours=5, minutes=30), "IST")


def as_ist(value: datetime) -> datetime:
    # Database DATETIME fields and legacy zone-less API values represent UTC.
    instant = value.replace(tzinfo=UTC) if value.tzinfo is None else value
    return instant.astimezone(IST)


def format_ist(value: datetime) -> str:
    return as_ist(value).strftime("%d %b %Y, %H:%M IST")


IstDateTime = Annotated[datetime, PlainSerializer(as_ist, return_type=datetime, when_used="json")]
