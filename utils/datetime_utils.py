from datetime import datetime, timezone
import calendar

def parse_iso_z(s: str) -> datetime:
    s = s.rstrip("Z")
    if "." in s:
        base, frac = s.split(".", 1)
        frac = frac[:6]
        micro = int(frac.ljust(6, "0"))
        dt = datetime.fromisoformat(base)
        return dt.replace(microsecond=micro)
    return datetime.fromisoformat(s)

def format_iso_z(dt: datetime) -> str:
    ms = dt.microsecond // 1000
    return dt.strftime(f"%Y-%m-%dT%H:%M:%S.{ms:03d}Z")

def subtract_months(dt: datetime, months: int) -> datetime:
    y = dt.year
    m = dt.month - months
    while m <= 0:
        y -= 1
        m += 12
    while m > 12:
        y += 1
        m -= 12
    last_day = calendar.monthrange(y, m)[1]
    day = min(dt.day, last_day)
    return datetime(y, m, day, dt.hour, dt.minute, dt.second, dt.microsecond, dt.tzinfo)

def two_months_ago() -> str:
    now = datetime.now(timezone.utc)
    dt = subtract_months(now, 2)
    return format_iso_z(dt)

def current_time() -> str:
    now = datetime.now(timezone.utc)
    return format_iso_z(now)
