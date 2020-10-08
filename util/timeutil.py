from datetime import datetime, date, timedelta
from typing import Tuple
import pytz


def now() -> datetime:
    return datetime.now(tz=pytz.timezone("UTC"))


def add_tz_info(dt: datetime) -> datetime:
    return pytz.UTC.localize(dt)


BI_WEEK_REF = add_tz_info(datetime.strptime("2020/09/13", "%Y/%m/%d"))


def get_bw_range(day: date) -> Tuple[date, date]:
    lower = day - timedelta(days=(day - BI_WEEK_REF.date()).days % 14)
    upper = lower + timedelta(days=13)
    return lower, upper