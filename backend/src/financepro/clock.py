"""Time in one place: timestamps are UTC, calendar dates are Brazilian (America/Sao_Paulo)."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/Sao_Paulo")


def now() -> datetime:
    return datetime.now(UTC)


def today() -> date:
    """'Today' for the user: a purchase at 23:30 in São Paulo is still that day, not tomorrow in UTC."""
    return now().astimezone(LOCAL_TZ).date()
