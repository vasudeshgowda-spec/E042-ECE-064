"""Calendar helpers. All terms are inclusive of both start and end dates."""
import calendar
from datetime import date, timedelta


def add_months(d: date, n: int) -> date:
    """Add n calendar months, clamping the day to the target month's length."""
    total = d.year * 12 + (d.month - 1) + n
    year, month = divmod(total, 12)
    month += 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def add_years(d: date, n: int) -> date:
    return add_months(d, 12 * n)


def term_end_for(start: date) -> date:
    """One-year term starting on `start`, inclusive: ends the day before the anniversary."""
    return add_years(start, 1) - timedelta(days=1)


def inclusive_days(start: date, end: date) -> int:
    return (end - start).days + 1
