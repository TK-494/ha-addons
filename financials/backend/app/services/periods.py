"""Month boundaries.

The month boundary is a *display* setting, never a stored property of a
transaction. Switching from calendar months to salary-aligned months therefore
re-buckets eight years of history instantly, instead of requiring a re-import.

Three modes:
  calendar   — the 1st (default)
  day        — a fixed day of the month, 1–28
  salary     — the day your salary lands, detected from the data
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Category, Setting, Transaction

MODE_CALENDAR = "calendar"
MODE_DAY = "day"
MODE_SALARY = "salary"

SETTING_MODE = "month_start_mode"
SETTING_DAY = "month_start_day"

# 28 keeps every month able to contain the boundary; 29–31 would silently
# shift in February and make period comparisons inconsistent.
MAX_START_DAY = 28


@dataclass(frozen=True)
class PeriodConfig:
    mode: str = MODE_CALENDAR
    start_day: int = 1

    @property
    def effective_day(self) -> int:
        return 1 if self.mode == MODE_CALENDAR else max(1, min(self.start_day, MAX_START_DAY))


def get_setting(db: Session, key: str, default: str) -> str:
    row = db.get(Setting, key)
    return row.value if row else default


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.get(Setting, key)
    if row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value


def load_config(db: Session) -> PeriodConfig:
    mode = get_setting(db, SETTING_MODE, MODE_CALENDAR)
    try:
        day = int(get_setting(db, SETTING_DAY, "1"))
    except ValueError:
        day = 1
    if mode == MODE_SALARY:
        day = detect_salary_day(db) or day
    return PeriodConfig(mode=mode, start_day=day)


def detect_salary_day(db: Session) -> Optional[int]:
    """Most common day-of-month for income booked to the Inkomen category.

    Dutch salaries land on a fixed day (often the 24th or the last working
    day), so the mode over the last couple of years is a solid signal. Falls
    back to None when there is nothing categorised as income yet.
    """
    category_id = db.scalar(select(Category.id).where(Category.name == "Inkomen"))
    if category_id is None:
        return None

    cutoff = date.today() - timedelta(days=730)
    rows = db.execute(
        select(
            func.cast(func.strftime("%d", Transaction.booked_on), func.INTEGER().type).label("dom"),
            func.count().label("n"),
        )
        .where(
            Transaction.category_id == category_id,
            Transaction.amount_cents > 100_000,  # > €1000: a salary, not a refund
            Transaction.booked_on >= cutoff,
            Transaction.is_internal.is_(False),
        )
        .group_by("dom")
        .order_by(func.count().desc())
        .limit(1)
    ).first()

    if not rows or rows[0] is None:
        return None
    return max(1, min(int(rows[0]), MAX_START_DAY))


def period_bounds(year: int, month: int, config: PeriodConfig) -> tuple[date, date]:
    """Return `[start, end)` for the given period label.

    With a start day of 24, the period labelled 2026-08 runs 2026-08-24 →
    2026-09-24. The label always names the month the period *starts* in.
    """
    day = config.effective_day
    start = date(year, month, min(day, monthrange(year, month)[1]))
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    end = date(next_year, next_month, min(day, monthrange(next_year, next_month)[1]))
    return start, end


def period_of(value: date, config: PeriodConfig) -> tuple[int, int]:
    """Which period label a date falls into — the inverse of `period_bounds`."""
    if value.day >= config.effective_day:
        return value.year, value.month
    return (value.year - 1, 12) if value.month == 1 else (value.year, value.month - 1)


def shift_period(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def recent_periods(count: int, config: PeriodConfig, today: Optional[date] = None) -> list[tuple[int, int]]:
    """The `count` most recent period labels, oldest first."""
    year, month = period_of(today or date.today(), config)
    return [shift_period(year, month, -offset) for offset in range(count - 1, -1, -1)]
