"""
Date/Time Normalization — Step 9

Converts all date representations to UTC-aware ISO 8601 datetime.

CRITICAL: Normalization puts dates in a common format.
          It does NOT collapse date differences.
          A settlement date of Aug 3 and bank date of Aug 5
          must remain Aug 3 and Aug 5 in the DB.

Supported input formats:
    "01/08/2026"              → Indian date (DD/MM/YYYY)
    "2026-08-01"              → ISO date
    "Aug 01 2026"             → English month name
    "2026-08-01T10:30:00+05:30" → ISO with timezone
    "01-08-2026"              → DD-MM-YYYY

Output: UTC-aware datetime as ISO string "2026-08-01T05:00:00+00:00"
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
import re

# IST offset
IST = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc

# Date format patterns to try in order
DATE_FORMATS = [
    "%Y-%m-%dT%H:%M:%S%z",        # ISO 8601 with tz
    "%Y-%m-%dT%H:%M:%S.%f%z",     # ISO 8601 with microseconds + tz
    "%Y-%m-%dT%H:%M:%S",          # ISO 8601 no tz (assume IST)
    "%Y-%m-%d %H:%M:%S",          # SQL datetime no tz
    "%Y-%m-%d",                    # ISO date only
    "%d/%m/%Y %H:%M:%S",          # Indian datetime
    "%d/%m/%Y",                    # Indian date DD/MM/YYYY
    "%d-%m-%Y",                    # Indian date DD-MM-YYYY
    "%m/%d/%Y",                    # US date (ambiguous, tried last)
    "%d %b %Y",                    # "01 Aug 2026"
    "%b %d %Y",                    # "Aug 01 2026"
    "%d %B %Y",                    # "01 August 2026"
    "%B %d %Y",                    # "August 01 2026"
    "%d %b %Y %H:%M:%S",          # "01 Aug 2026 10:30:00"
]


def normalize_datetime(raw_value, assume_tz=IST) -> Optional[datetime]:
    """
    Normalize a date/time value to a UTC-aware datetime object.

    Args:
        raw_value: Raw date string or datetime object
        assume_tz: Timezone to assume if source has no timezone info (default IST)

    Returns:
        UTC-aware datetime, or None if value is missing/empty.

    Raises:
        ValueError if value is present but cannot be parsed.
    """
    if raw_value is None:
        return None

    if isinstance(raw_value, datetime):
        if raw_value.tzinfo is None:
            raw_value = raw_value.replace(tzinfo=assume_tz)
        return raw_value.astimezone(UTC)

    raw = str(raw_value).strip()
    if not raw or raw.lower() in ("null", "none", "n/a", ""):
        return None

    # Handle "+05:30" format that Python < 3.7 chokes on
    # by normalizing to +0530
    raw_clean = raw
    if "+05:30" in raw_clean:
        raw_clean = raw_clean.replace("+05:30", "+0530")
    elif "+00:00" in raw_clean:
        raw_clean = raw_clean.replace("+00:00", "+0000")

    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(raw_clean, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=assume_tz)
            return dt.astimezone(UTC)
        except ValueError:
            continue

    raise ValueError(
        f"Cannot parse '{raw}' as a date/time. Tried {len(DATE_FORMATS)} formats."
    )


def normalize_datetime_safe(raw_value, field_name: str = "date") -> tuple:
    """
    Safe wrapper — returns (datetime_or_None, error_or_None).
    """
    try:
        result = normalize_datetime(raw_value)
        return result, None
    except ValueError as e:
        return None, str(e)


def to_iso_string(dt: Optional[datetime]) -> Optional[str]:
    """
    Serialize a UTC datetime to ISO 8601 string for JSON/DB.

    Example: datetime(2026,8,1,5,0,0,tzinfo=UTC) → "2026-08-01T05:00:00+00:00"
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat()


def to_date_string(dt: Optional[datetime]) -> Optional[str]:
    """
    Serialize a datetime to date-only string YYYY-MM-DD.
    """
    if dt is None:
        return None
    return dt.date().isoformat()


def date_diff_days(dt1: Optional[datetime], dt2: Optional[datetime]) -> Optional[int]:
    """
    Compute |dt1 - dt2| in whole days.

    Used by reconciliation engine for date tolerance checks.
    Returns None if either value is missing.
    """
    if dt1 is None or dt2 is None:
        return None
    delta = abs((dt1 - dt2).days)
    return delta
