"""Date utilities."""

from __future__ import annotations

from datetime import date, datetime


def parse_date(value: str | date | datetime) -> date:
    """Parse an ISO date-like value into a `date`."""

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(value, "%Y-%m-%d").date()


def year_fraction(
    start: str | date | datetime, end: str | date | datetime, basis: float = 365.0
) -> float:
    """Compute a simple ACT/basis year fraction."""

    start_date = parse_date(start)
    end_date = parse_date(end)
    return max((end_date - start_date).days / basis, 0.0)
