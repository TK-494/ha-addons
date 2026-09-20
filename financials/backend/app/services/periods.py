"""Month boundaries.

The boundary is a *display* setting: no transaction is rewritten, so switching
re-buckets the whole history on the next request.

Three modes:
  calendar   — the 1st (default)
  day        — a fixed day of the month, 1–28
  salary     — the day your salary actually landed, per month

The salary mode is not a fixed day. Dutch employers pay on a set date but move
it when that date falls on a weekend or around the holidays: in this dataset
the salary hit the 25th in 14 months and some other day in 12. A fixed boundary
on the 25th therefore pushes the salary into the previous period in more than
half of all months. So each period starts on the date its salary was actually
booked, with a manual override per month for the cases nothing can infer.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session

from ..models import Account, PeriodOverride, Setting, Transaction
from .workdays import previous_working_day

MODE_CALENDAR = "calendar"
MODE_DAY = "day"
MODE_SALARY = "salary"

SETTING_MODE = "month_start_mode"
SETTING_DAY = "month_start_day"
SETTING_SALARY_MATCH = "salary_counterparty"
SETTING_SALARY_ACCOUNT = "salary_account_id"
SETTING_SALARY_MIN = "salary_min_amount_cents"

# 28 keeps every month able to contain the fallback boundary; 29–31 would shift
# in February and make period comparisons inconsistent.
MAX_START_DAY = 28

# Below this, an incoming payment is not somebody's salary.
DEFAULT_SALARY_MIN_CENTS = 50_000


@dataclass
class SalarySource:
    """How to recognise the salary payment.

    Matching on the payer rather than on "income above €1000" matters: that
    threshold also catches loan payouts, which land on unrelated dates and drag
    the detected day with them.
    """

    counterparty: str = ""
    account_id: Optional[int] = None
    min_amount_cents: int = DEFAULT_SALARY_MIN_CENTS

    @property
    def configured(self) -> bool:
        return bool(self.counterparty.strip())


@dataclass
class PeriodConfig:
    mode: str = MODE_CALENDAR
    start_day: int = 1
    salary: SalarySource = field(default_factory=SalarySource)
    # (year, month) -> the date that period actually starts on. Only holds the
    # months that differ from the fixed-day rule, so the common case stays a
    # plain arithmetic boundary.
    overrides: dict[tuple[int, int], date] = field(default_factory=dict)

    @property
    def effective_day(self) -> int:
        return 1 if self.mode == MODE_CALENDAR else max(1, min(self.start_day, MAX_START_DAY))

    def fixed_start(self, year: int, month: int) -> date:
        day = self.effective_day
        return date(year, month, min(day, monthrange(year, month)[1]))

    def start_of(self, year: int, month: int) -> date:
        return self.overrides.get((year, month)) or self.fixed_start(year, month)


# ─── settings plumbing ──────────────────────────────────────────────────────

def get_setting(db: Session, key: str, default: str) -> str:
    row = db.get(Setting, key)
    return row.value if row else default


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.get(Setting, key)
    if row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value


def load_salary_source(db: Session) -> SalarySource:
    account_raw = get_setting(db, SETTING_SALARY_ACCOUNT, "")
    try:
        minimum = int(get_setting(db, SETTING_SALARY_MIN, str(DEFAULT_SALARY_MIN_CENTS)))
    except ValueError:
        minimum = DEFAULT_SALARY_MIN_CENTS
    return SalarySource(
        counterparty=get_setting(db, SETTING_SALARY_MATCH, ""),
        account_id=int(account_raw) if account_raw.isdigit() else None,
        min_amount_cents=minimum,
    )


def load_config(db: Session) -> PeriodConfig:
    mode = get_setting(db, SETTING_MODE, MODE_CALENDAR)
    try:
        day = int(get_setting(db, SETTING_DAY, "1"))
    except ValueError:
        day = 1

    salary = load_salary_source(db)
    config = PeriodConfig(mode=mode, start_day=day, salary=salary)

    if mode != MODE_SALARY:
        return config

    # Fall back to the typical day so the boundary is sane before any salary
    # has been identified.
    config.start_day = detect_salary_day(db, salary) or day
    config.overrides = _resolve_salary_boundaries(db, config)
    return config


# ─── finding the salary ─────────────────────────────────────────────────────

def _salary_query(config_or_source):
    source = config_or_source.salary if isinstance(config_or_source, PeriodConfig) else config_or_source
    stmt = select(Transaction).where(
        Transaction.amount_cents >= source.min_amount_cents,
        Transaction.is_internal.is_(False),
    )
    if source.counterparty.strip():
        needle = f"%{source.counterparty.strip()}%"
        stmt = stmt.where(Transaction.counter_name.ilike(needle))
    if source.account_id:
        stmt = stmt.where(Transaction.account_id == source.account_id)
    return stmt


# One or two payments say nothing about a "usual" day. Below this the
# configured fallback day is kept instead of inventing one from noise.
MIN_PAYMENTS_FOR_TYPICAL_DAY = 3


def detect_salary_day(db: Session, source: Optional[SalarySource] = None) -> Optional[int]:
    """The most common day-of-month the salary lands on — the fallback for
    months where no payment can be found."""
    source = source or SalarySource()
    if not source.configured:
        return None

    cutoff = date.today() - timedelta(days=1095)
    row = db.execute(
        select(
            cast(func.strftime("%d", Transaction.booked_on), Integer).label("dom"),
            func.count().label("n"),
        )
        .where(
            Transaction.amount_cents >= source.min_amount_cents,
            Transaction.is_internal.is_(False),
            Transaction.counter_name.ilike(f"%{source.counterparty.strip()}%"),
            Transaction.booked_on >= cutoff,
        )
        .group_by("dom")
        .order_by(func.count().desc())
        .limit(1)
    ).first()

    if not row or row[0] is None or row[1] < MIN_PAYMENTS_FOR_TYPICAL_DAY:
        return None
    return max(1, min(int(row[0]), MAX_START_DAY))


def salary_dates(db: Session, config: PeriodConfig) -> dict[tuple[int, int], date]:
    """The actual booking date of the salary in each calendar month.

    When a month holds more than one qualifying payment — holiday pay booked
    separately, say — the earliest is used, because that is when the month's
    money arrived.
    """
    if not config.salary.configured:
        return {}

    found: dict[tuple[int, int], date] = {}
    for tx in db.scalars(_salary_query(config).order_by(Transaction.booked_on)):
        key = (tx.booked_on.year, tx.booked_on.month)
        if key not in found:
            found[key] = tx.booked_on
    return found


def _resolve_salary_boundaries(db: Session, config: PeriodConfig) -> dict[tuple[int, int], date]:
    """Actual salary dates, with manual corrections layered on top.

    Only months whose boundary differs from the fixed-day rule are kept — the
    rest need no special handling anywhere downstream.
    """
    resolved: dict[tuple[int, int], date] = {}

    for key, value in salary_dates(db, config).items():
        if value != config.fixed_start(*key):
            resolved[key] = value

    for override in db.scalars(select(PeriodOverride)).all():
        key = (override.year, override.month)
        if override.start_date == config.fixed_start(*key):
            resolved.pop(key, None)
        else:
            resolved[key] = override.start_date

    return resolved


def propose_salary_source(db: Session) -> list[dict]:
    """Suggest who the employer is: recurring large incoming payments from the
    same counterparty, most frequent first."""
    cutoff = date.today() - timedelta(days=1095)
    rows = db.execute(
        select(
            Transaction.counter_name,
            func.count(),
            func.avg(Transaction.amount_cents),
            func.max(Transaction.booked_on),
        )
        .where(
            Transaction.amount_cents >= DEFAULT_SALARY_MIN_CENTS,
            Transaction.is_internal.is_(False),
            Transaction.counter_name != "",
            Transaction.booked_on >= cutoff,
        )
        .group_by(Transaction.counter_name)
        .having(func.count() >= 3)
        .order_by(func.count().desc())
        .limit(5)
    ).all()

    return [
        {
            "counterparty": name,
            "payments": count,
            "average_amount": round((average or 0) / 100, 2),
            "last_seen": last if isinstance(last, str) else last.isoformat(),
        }
        for name, count, average, last in rows
    ]


# ─── boundaries ─────────────────────────────────────────────────────────────

def period_bounds(year: int, month: int, config: PeriodConfig) -> tuple[date, date]:
    """Return `[start, end)` for the given period label.

    The label always names the month the period *starts* in.
    """
    next_year, next_month = shift_period(year, month, 1)
    return config.start_of(year, month), config.start_of(next_year, next_month)


def period_of(value: date, config: PeriodConfig) -> tuple[int, int]:
    """Which period label a date falls into — the inverse of `period_bounds`.

    Starts from the fixed-day answer and steps at most one period either way,
    which is all a shifted boundary can ever move a date.
    """
    if value.day >= config.effective_day:
        candidate = (value.year, value.month)
    else:
        candidate = shift_period(value.year, value.month, -1)

    if not config.overrides:
        return candidate

    for _ in range(2):
        start, end = period_bounds(*candidate, config)
        if value < start:
            candidate = shift_period(*candidate, -1)
        elif value >= end:
            candidate = shift_period(*candidate, 1)
        else:
            break
    return candidate


def shift_period(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def recent_periods(count: int, config: PeriodConfig, today: Optional[date] = None) -> list[tuple[int, int]]:
    """The `count` most recent period labels, oldest first."""
    year, month = period_of(today or date.today(), config)
    return [shift_period(year, month, -offset) for offset in range(count - 1, -1, -1)]


MONTHS_NL = [
    "januari", "februari", "maart", "april", "mei", "juni",
    "juli", "augustus", "september", "oktober", "november", "december",
]


def parse_label(value: str) -> tuple[int, int]:
    """`YYYY-MM` → (year, month). Raises ValueError on anything else."""
    year_text, _, month_text = value.partition("-")
    year, month = int(year_text), int(month_text)
    if not 1 <= month <= 12 or not 1900 <= year <= 2200:
        raise ValueError(value)
    return year, month


def label_of(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def human_label(year: int, month: int) -> str:
    return f"{MONTHS_NL[month - 1]} {year}"


@dataclass(frozen=True)
class PeriodRange:
    """A run of consecutive periods, `first` through `last` inclusive.

    One month is the common case and just a range of length one: every
    endpoint that works on a range works on a month, so a page never needs
    two code paths.
    """

    first: tuple[int, int]
    last: tuple[int, int]
    start: date   # inclusive
    end: date     # exclusive

    @property
    def count(self) -> int:
        (y1, m1), (y2, m2) = self.first, self.last
        return (y2 * 12 + m2) - (y1 * 12 + m1) + 1

    @property
    def single(self) -> bool:
        return self.count == 1

    @property
    def labels(self) -> list[tuple[int, int]]:
        return [shift_period(*self.first, offset) for offset in range(self.count)]

    def previous(self, config: PeriodConfig) -> "PeriodRange":
        """The same number of periods immediately before this range — what a
        "compared to" figure should compare to. A quarter against the previous
        quarter, not against one month."""
        return make_range(
            config,
            shift_period(*self.first, -self.count),
            shift_period(*self.last, -self.count),
        )

    def to_dict(self) -> dict:
        return {
            "from": label_of(*self.first),
            "to": label_of(*self.last),
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "periods": self.count,
            "single": self.single,
            "label": (
                human_label(*self.first) if self.single
                else f"{human_label(*self.first)} t/m {human_label(*self.last)}"
            ),
        }


def make_range(config: PeriodConfig, first: tuple[int, int], last: tuple[int, int]) -> PeriodRange:
    if first > last:
        first, last = last, first
    start, _ = period_bounds(*first, config)
    _, end = period_bounds(*last, config)
    return PeriodRange(first=first, last=last, start=start, end=end)


def resolve_range(
    config: PeriodConfig,
    *,
    from_label: Optional[str] = None,
    to_label: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    months: Optional[int] = None,
    today: Optional[date] = None,
) -> PeriodRange:
    """One resolver for every way a caller can name a range.

    Precedence, most explicit first:
      1. `from`/`to` labels. Both: that range. `from` alone: that one period.
         `to` alone: the `months` periods ending there (one, if unspecified) —
         which is how a chart follows the period you are looking at.
      2. `year`+`month` — that one period, or the `months` periods ending there.
      3. `months` — that many periods ending at the current one.
      4. nothing — the current period.

    Older callers keep working unchanged; new ones say exactly what they mean.
    """
    current = period_of(today or date.today(), config)

    if from_label and to_label:
        return make_range(config, parse_label(from_label), parse_label(to_label))
    if from_label:
        first = parse_label(from_label)
        return make_range(config, first, first)
    if to_label:
        last = parse_label(to_label)
        return make_range(config, shift_period(*last, -((months or 1) - 1)), last)

    if year is not None and month is not None:
        last = (year, month)
    else:
        last = current
    first = shift_period(*last, -((months or 1) - 1))
    return make_range(config, first, last)


def earliest_period(db: Session, config: PeriodConfig) -> Optional[tuple[int, int]]:
    """The period the oldest transaction on record falls in."""
    first = db.scalar(select(func.min(Transaction.booked_on)))
    if first is None:
        return None
    if isinstance(first, str):
        first = date.fromisoformat(first)
    return period_of(first, config)


def boundary_overview(db: Session, config: PeriodConfig, months: int = 12) -> list[dict]:
    """What the boundaries resolve to, and why — the table shown in Settings so
    a wrong month is visible and correctable."""
    detected = salary_dates(db, config)
    manual = {
        (o.year, o.month): o.start_date for o in db.scalars(select(PeriodOverride)).all()
    }

    rows = []
    for year, month in recent_periods(months, config):
        start, end = period_bounds(year, month, config)
        key = (year, month)
        if key in manual:
            origin = "handmatig"
        elif key in detected and detected[key] == start:
            origin = "salarisdatum"
        else:
            origin = "vaste dag"
        rows.append({
            "year": year,
            "month": month,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "origin": origin,
            "salary_date": detected[key].isoformat() if key in detected else None,
            "fixed_date": config.fixed_start(year, month).isoformat(),
        })
    return rows


def next_salary_estimate(db: Session, config: PeriodConfig) -> Optional[dict]:
    """When the next salary is expected.

    Built from what actually happened rather than from a rule alone. The base
    is the usual day of the month, moved back to a working day — that alone
    predicted 36 of 39 real payments here, including the one that shifted for
    Whit Monday.

    The three it missed were all December, where the employer pays before
    Christmas rather than merely avoiding the holiday. That is a policy, not a
    calendar, so it is learned: when a calendar month has been seen at least
    twice, that month's own median day wins over the global one.
    """
    found = salary_dates(db, config)
    if not found:
        return None

    typical = detect_salary_day(db, config.salary) or config.effective_day

    per_month: dict[int, list[int]] = {}
    for (_, month), value in found.items():
        per_month.setdefault(month, []).append(value.day)

    def target_day(month: int) -> tuple[int, bool]:
        """Returns (day, reliable).

        A month's own history only wins when that history agrees with itself.
        December here ran 20th, 21st and 22nd across three years — the employer
        pays "before Christmas", which is a decision, not a date. Averaging
        that produces a confident-looking number that is wrong as often as the
        plain rule, so it is reported as an estimate instead.
        """
        observed = sorted(per_month.get(month, []))
        if len(observed) >= 2 and observed[-1] - observed[0] <= 1:
            return observed[len(observed) // 2], True
        if len(observed) >= 2:
            return typical, False
        return typical, True

    last = max(found.values())
    today = date.today()

    # Walk forward month by month until we find a payment date still ahead.
    year, month = last.year, last.month
    for _ in range(14):
        year, month = shift_period(year, month, 1)
        day, reliable = target_day(month)
        candidate = previous_working_day(date(year, month, min(day, monthrange(year, month)[1])))
        if candidate > today:
            return {
                "date": candidate.isoformat(),
                "days": (candidate - today).days,
                "reliable": reliable,
                "note": None if reliable else
                        "In deze maand wisselt de betaaldag; dit is een schatting.",
                "last_salary": last.isoformat(),
            }
    return None
