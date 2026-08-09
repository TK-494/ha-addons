"""App settings — the month boundary and how the salary is recognised."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Account, PeriodOverride
from ..services import periods

router = APIRouter(prefix="/settings", tags=["settings"])


class PeriodSettings(BaseModel):
    mode: Literal["calendar", "day", "salary"] = "calendar"
    start_day: int = Field(1, ge=1, le=periods.MAX_START_DAY)


class SalarySourceIn(BaseModel):
    counterparty: str = Field("", max_length=200)
    account_id: Optional[int] = None
    min_amount: float = Field(500.0, ge=0)


class OverrideIn(BaseModel):
    year: int = Field(..., ge=2000, le=2100)
    month: int = Field(..., ge=1, le=12)
    start_date: date
    note: Optional[str] = Field(None, max_length=200)


def _payload(db: Session) -> dict:
    config = periods.load_config(db)
    return {
        "mode": config.mode,
        "start_day": config.start_day,
        "effective_day": config.effective_day,
        "salary": {
            "counterparty": config.salary.counterparty,
            "account_id": config.salary.account_id,
            "min_amount": config.salary.min_amount_cents / 100,
            "configured": config.salary.configured,
        },
        "detected_salary_day": periods.detect_salary_day(db, config.salary),
        "suggestions": periods.propose_salary_source(db),
        "shifted_months": len(config.overrides),
        "boundaries": periods.boundary_overview(db, config, months=14),
    }


@router.get("/period")
def get_period_settings(db: Session = Depends(get_db)):
    return _payload(db)


@router.put("/period")
def set_period_settings(payload: PeriodSettings, db: Session = Depends(get_db)):
    """Purely a display setting: no transaction is rewritten, so switching
    re-buckets the full history on the next request."""
    periods.set_setting(db, periods.SETTING_MODE, payload.mode)
    periods.set_setting(db, periods.SETTING_DAY, str(payload.start_day))
    db.commit()
    return _payload(db)


@router.put("/salary-source")
def set_salary_source(payload: SalarySourceIn, db: Session = Depends(get_db)):
    """Who pays the salary.

    Matching on the payer beats "income above some amount": that threshold also
    catches loan payouts, which land on unrelated dates and would drag the
    month boundary around with them.
    """
    if payload.account_id is not None and db.get(Account, payload.account_id) is None:
        raise HTTPException(422, "Rekening bestaat niet.")

    periods.set_setting(db, periods.SETTING_SALARY_MATCH, payload.counterparty.strip())
    periods.set_setting(
        db, periods.SETTING_SALARY_ACCOUNT,
        "" if payload.account_id is None else str(payload.account_id),
    )
    periods.set_setting(
        db, periods.SETTING_SALARY_MIN, str(int(round(payload.min_amount * 100)))
    )
    db.commit()
    return _payload(db)


@router.get("/salary-dates")
def salary_dates(db: Session = Depends(get_db), months: int = Query(24, ge=1, le=120)):
    """Every salary payment found, so you can see what the boundaries are
    built on before trusting them."""
    config = periods.load_config(db)
    found = periods.salary_dates(db, config)
    return [
        {
            "year": year,
            "month": month,
            "date": value.isoformat(),
            "weekday": ["ma", "di", "wo", "do", "vr", "za", "zo"][value.weekday()],
            "fixed_date": config.fixed_start(year, month).isoformat(),
            "shifted": value != config.fixed_start(year, month),
        }
        for (year, month), value in sorted(found.items(), reverse=True)[:months]
    ]


@router.put("/period-override")
def set_override(payload: OverrideIn, db: Session = Depends(get_db)):
    """Correct one month by hand. Wins over the detected salary date."""
    if payload.start_date.year not in (payload.year, payload.year + (1 if payload.month == 12 else 0)):
        # A boundary belongs in or adjacent to its own month; anything else is
        # almost certainly a typo, and a silently accepted one would quietly
        # scramble two periods.
        raise HTTPException(422, "De datum hoort niet bij deze maand.")

    existing = db.scalar(
        select(PeriodOverride).where(
            PeriodOverride.year == payload.year, PeriodOverride.month == payload.month
        )
    )
    if existing is None:
        db.add(PeriodOverride(**payload.model_dump()))
    else:
        existing.start_date = payload.start_date
        existing.note = payload.note
    db.commit()
    return _payload(db)


@router.delete("/period-override/{year}/{month}")
def delete_override(year: int, month: int, db: Session = Depends(get_db)):
    """Drop the correction and fall back to the detected salary date."""
    existing = db.scalar(
        select(PeriodOverride).where(PeriodOverride.year == year, PeriodOverride.month == month)
    )
    if existing is None:
        raise HTTPException(404, "Geen correctie voor deze maand.")
    db.delete(existing)
    db.commit()
    return _payload(db)
