"""App settings — currently the month boundary (PLAN decision 4)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import periods

router = APIRouter(prefix="/settings", tags=["settings"])


class PeriodSettings(BaseModel):
    mode: Literal["calendar", "day", "salary"] = "calendar"
    start_day: int = Field(1, ge=1, le=periods.MAX_START_DAY)


@router.get("/period")
def get_period_settings(db: Session = Depends(get_db)):
    config = periods.load_config(db)
    return {
        "mode": config.mode,
        "start_day": config.start_day,
        "effective_day": config.effective_day,
        "detected_salary_day": periods.detect_salary_day(db),
    }


@router.put("/period")
def set_period_settings(payload: PeriodSettings, db: Session = Depends(get_db)):
    """Purely a display setting: no transaction is rewritten, so switching
    re-buckets the full history on the next request."""
    periods.set_setting(db, periods.SETTING_MODE, payload.mode)
    periods.set_setting(db, periods.SETTING_DAY, str(payload.start_day))
    db.commit()
    return get_period_settings(db)
