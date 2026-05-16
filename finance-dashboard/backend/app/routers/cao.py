from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..models import CAOScale, UserSettings
from ..schemas import CAOScaleCreate, CAOScaleOut

router = APIRouter(prefix="/cao", tags=["cao"])

# VGN CAO 2024–2025 FWG salary scales (monthly gross in EUR)
# Source: VGN CAO loonschalen (approximate per 1-1-2024 with 3% increase)
VGN_SCALES_2024 = {
    10: [1958, 2006, 2057, 2110, 2164, 2220, 2278],
    15: [2060, 2114, 2170, 2228, 2288, 2350, 2414],
    20: [2170, 2228, 2290, 2355, 2422, 2493, 2565],
    25: [2290, 2355, 2424, 2496, 2570, 2648, 2729],
    30: [2424, 2496, 2572, 2651, 2733, 2819, 2908],
    35: [2572, 2651, 2733, 2820, 2911, 3005, 3103],
    40: [2733, 2820, 2911, 3006, 3104, 3207, 3314],
    45: [2911, 3006, 3105, 3208, 3315, 3427, 3544],
    50: [3105, 3208, 3315, 3428, 3546, 3668, 3795],
    55: [3315, 3428, 3547, 3669, 3796, 3929, 4067],
    60: [3547, 3669, 3797, 3930, 4068, 4212, 4362],
    65: [3797, 3930, 4069, 4213, 4364, 4521, 4685],
    70: [4069, 4213, 4364, 4522, 4686, 4857, 5035],
    75: [4364, 4522, 4687, 4858, 5036, 5223, 5418],
    80: [4687, 4858, 5037, 5223, 5419, 5623, 5837],
}


@router.get("/scales", response_model=List[CAOScaleOut])
def get_scales(db: Session = Depends(get_db)):
    scales = db.query(CAOScale).order_by(CAOScale.scale, CAOScale.step).all()
    return scales


@router.post("/scales", response_model=CAOScaleOut)
def upsert_scale(scale: CAOScaleCreate, db: Session = Depends(get_db)):
    existing = db.query(CAOScale).filter(
        CAOScale.scale == scale.scale,
        CAOScale.step == scale.step,
    ).first()
    if existing:
        existing.monthly_gross = scale.monthly_gross
        db.commit()
        db.refresh(existing)
        return existing
    db_scale = CAOScale(**scale.model_dump())
    db.add(db_scale)
    db.commit()
    db.refresh(db_scale)
    return db_scale


@router.get("/projection")
def get_projection(
    fwg_scale: int,
    current_step: int,
    years: int = 10,
    db: Session = Depends(get_db),
):
    scales = (
        db.query(CAOScale)
        .filter(CAOScale.scale == fwg_scale)
        .order_by(CAOScale.step)
        .all()
    )
    if not scales:
        return {"error": "Scale not found"}

    steps = {s.step: s.monthly_gross for s in scales}
    max_step = max(steps.keys())
    projection = []

    for i in range(years + 1):
        step = min(current_step + i, max_step)
        monthly = steps.get(step, steps[max_step])
        projection.append({
            "year": 2024 + i,
            "step": step,
            "monthly_gross": monthly,
            "annual_gross": round(monthly * 12 * 1.08, 2),  # includes ~8% holiday allowance
            "monthly_net_estimate": round(monthly * 0.72, 2),  # rough net estimate
        })

    return {
        "fwg_scale": fwg_scale,
        "projection": projection,
        "max_step": max_step,
    }


@router.get("/settings")
def get_cao_settings(db: Session = Depends(get_db)):
    settings = {s.key: s.value for s in db.query(UserSettings).all()}
    return {
        "fwg_scale": int(settings.get("cao_scale", 30)),
        "current_step": int(settings.get("cao_step", 1)),
    }


@router.post("/settings")
def save_cao_settings(fwg_scale: int, current_step: int, db: Session = Depends(get_db)):
    for key, val in [("cao_scale", str(fwg_scale)), ("cao_step", str(current_step))]:
        setting = db.query(UserSettings).filter(UserSettings.key == key).first()
        if setting:
            setting.value = val
        else:
            db.add(UserSettings(key=key, value=val))
    db.commit()
    return {"ok": True}


def seed_vgn_scales(db: Session):
    if db.query(CAOScale).count() == 0:
        for scale_num, steps in VGN_SCALES_2024.items():
            for step_idx, gross in enumerate(steps, start=1):
                db.add(CAOScale(scale=scale_num, step=step_idx, monthly_gross=gross))
        db.commit()
