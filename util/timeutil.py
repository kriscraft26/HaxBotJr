from datetime import datetime
import pytz


def now() -> datetime:
    return datetime.now(tz=pytz.timezone("UTC"))


def add_tz_info(dt: datetime) -> datetime:
    return pytz.UTC.localize(dt)