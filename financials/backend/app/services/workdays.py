"""Dutch working days.

Payroll runs on a fixed date but never on a day the banks are closed, so the
payment moves back to the previous working day. Predicting the next salary
therefore needs the Dutch holiday calendar, not just weekends: 25 May 2026 was
Whit Monday, which is why that month's salary landed on Friday the 22nd.
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache


def easter_sunday(year: int) -> date:
    """Anonymous Gregorian algorithm. Everything movable hangs off this."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


@lru_cache(maxsize=32)
def dutch_holidays(year: int) -> frozenset[date]:
    """Days Dutch banks do not process payments.

    Bevrijdingsdag (5 May) is deliberately absent: it is only a general day off
    every five years, and payroll does not consistently move for it.
    """
    easter = easter_sunday(year)

    kings_day = date(year, 4, 27)
    if kings_day.weekday() == 6:  # a Sunday moves it forward to the Saturday
        kings_day -= timedelta(days=1)

    return frozenset({
        date(year, 1, 1),                 # Nieuwjaarsdag
        easter - timedelta(days=2),       # Goede Vrijdag
        easter + timedelta(days=1),       # Tweede Paasdag
        kings_day,                        # Koningsdag
        easter + timedelta(days=39),      # Hemelvaartsdag
        easter + timedelta(days=50),      # Tweede Pinksterdag
        date(year, 12, 25),               # Eerste Kerstdag
        date(year, 12, 26),               # Tweede Kerstdag
    })


def is_working_day(value: date) -> bool:
    return value.weekday() < 5 and value not in dutch_holidays(value.year)


def previous_working_day(value: date) -> date:
    """Step back to the last day banks were open, `value` included."""
    guard = 0
    while not is_working_day(value) and guard < 10:
        value -= timedelta(days=1)
        guard += 1
    return value


def working_days_between(start: date, end: date) -> int:
    """Working days in `[start, end)` — used for "how long must this last"."""
    if end <= start:
        return 0
    count = 0
    cursor = start
    while cursor < end:
        if is_working_day(cursor):
            count += 1
        cursor += timedelta(days=1)
    return count
