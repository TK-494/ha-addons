from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..models import CAOScale, UserSettings
from ..schemas import CAOScaleCreate, CAOScaleOut

router = APIRouter(prefix="/cao", tags=["cao"])


# VGN CAO Gehandicaptenzorg — Salarisschalen functiegroepen per 01-12-2024.
# Source: "Salaristabellen CAO Gehandicaptenzorg per 1 juni 2024" PDF in this
# repo (the second table, the 01-12-2024 raise). Values are monthly gross in
# EUR. scale -> {trede: monthly_gross}. Each scale has its own valid trede
# range (FG 35 starts at trede 1, FG 40/45 at trede 2, etc.).
VGN_SCALES_2024_12 = {
    5:  {0: 2010, 1: 2040, 2: 2071, 3: 2137, 4: 2203, 5: 2237, 6: 2290, 7: 2339, 8: 2390, 9: 2448},
    10: {0: 2040, 1: 2071, 2: 2137, 3: 2203, 4: 2237, 5: 2290, 6: 2339, 7: 2390, 8: 2448, 9: 2512, 10: 2578},
    15: {0: 2071, 1: 2137, 2: 2203, 3: 2237, 4: 2290, 5: 2339, 6: 2390, 7: 2448, 8: 2512, 9: 2578, 10: 2651, 11: 2727},
    20: {0: 2137, 1: 2237, 2: 2290, 3: 2339, 4: 2390, 5: 2448, 6: 2512, 7: 2578, 8: 2651, 9: 2727, 10: 2796, 11: 2877},
    25: {0: 2203, 1: 2290, 2: 2390, 3: 2448, 4: 2512, 5: 2578, 6: 2651, 7: 2727, 8: 2796, 9: 2877, 10: 2946, 11: 3028},
    30: {0: 2237, 1: 2339, 2: 2448, 3: 2578, 4: 2651, 5: 2727, 6: 2796, 7: 2877, 8: 2946, 9: 3028, 10: 3107, 11: 3191},
    35: {1: 2448, 2: 2578, 3: 2727, 4: 2796, 5: 2877, 6: 2946, 7: 3028, 8: 3107, 9: 3191, 10: 3269, 11: 3347, 12: 3427},
    40: {2: 2727, 3: 2877, 4: 2946, 5: 3028, 6: 3107, 7: 3191, 8: 3269, 9: 3347, 10: 3427, 11: 3505, 12: 3593, 13: 3678},
    45: {2: 2877, 3: 3028, 4: 3191, 5: 3269, 6: 3347, 7: 3427, 8: 3505, 9: 3593, 10: 3678, 11: 3766, 12: 3843, 13: 3932, 14: 4017},
    50: {1: 3107, 2: 3269, 3: 3427, 4: 3593, 5: 3766, 6: 3843, 7: 3932, 8: 4017, 9: 4098, 10: 4184, 11: 4267, 12: 4354, 13: 4436},
    55: {0: 3347, 1: 3505, 2: 3678, 3: 3843, 4: 4017, 5: 4184, 6: 4354, 7: 4436, 8: 4532, 9: 4629, 10: 4725, 11: 4816, 12: 4902},
    60: {0: 3843, 1: 4017, 2: 4184, 3: 4354, 4: 4532, 5: 4725, 6: 4902, 7: 5085, 8: 5267, 9: 5343, 10: 5424, 11: 5508, 12: 5587},
    65: {0: 4354, 1: 4629, 2: 4902, 3: 5085, 4: 5267, 5: 5424, 6: 5587, 7: 5756, 8: 5920, 9: 6082, 10: 6251, 11: 6329, 12: 6414, 13: 6495, 14: 6575},
    70: {0: 5267, 1: 5508, 2: 5756, 3: 6000, 4: 6251, 5: 6495, 6: 6742, 7: 6908, 8: 7116, 9: 7320, 10: 7526, 11: 7632, 12: 7735, 13: 7837, 14: 7941},
    75: {0: 6251, 1: 6495, 2: 6742, 3: 7013, 4: 7320, 5: 7632, 6: 7941, 7: 8146, 8: 8363, 9: 8592, 10: 8825, 11: 8940, 12: 9057, 13: 9191, 14: 9325, 15: 9461, 16: 9611},
    80: {0: 7320, 1: 7632, 2: 7941, 3: 8247, 4: 8592, 5: 8940, 6: 9325, 7: 9611, 8: 9907, 9: 10211, 10: 10514, 11: 10667, 12: 10818, 13: 10970, 14: 11121, 15: 11276, 16: 11427},
}

# Bump this when the seed values change so existing DBs get the corrected
# numbers on next boot. Earlier installs had a placeholder dataset (rough
# 2024 estimates, no real PDF source) — those are now wiped and replaced.
CAO_SEED_VERSION = "2024-12-01-rev1"
CAO_SEED_VERSION_KEY = "cao_seed_version"


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
    min_step = min(steps.keys())
    max_step = max(steps.keys())
    # Clamp the user's input into the actually-valid range — FG 35 starts at
    # trede 1, FG 40/45 at trede 2, etc. Out-of-range inputs used to silently
    # return the wrong row.
    current_step = max(min(current_step, max_step), min_step)

    start_year = date.today().year
    projection = []
    for i in range(years + 1):
        step = min(current_step + i, max_step)
        monthly = steps[step]
        projection.append({
            "year": start_year + i,
            "step": step,
            "monthly_gross": monthly,
            "annual_gross": round(monthly * 12 * 1.08, 2),  # includes ~8% holiday allowance
            "monthly_net_estimate": round(monthly * 0.72, 2),  # rough net estimate
        })

    return {
        "fwg_scale": fwg_scale,
        "projection": projection,
        "min_step": min_step,
        "max_step": max_step,
        "current_step": current_step,
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
    """Insert the canonical CAO scale data. Reseeds when the seed version
    changes — earlier installs had a placeholder dataset (approximate 2024
    estimates) that didn't match the actual VGN PDF. The version key in
    user_settings lets us replace those without forcing a manual wipe.
    """
    version_row = (
        db.query(UserSettings)
        .filter(UserSettings.key == CAO_SEED_VERSION_KEY)
        .first()
    )
    if version_row and version_row.value == CAO_SEED_VERSION and db.query(CAOScale).count() > 0:
        return

    db.query(CAOScale).delete()
    for scale_num, steps in VGN_SCALES_2024_12.items():
        for step, gross in steps.items():
            db.add(CAOScale(scale=scale_num, step=step, monthly_gross=gross))

    if version_row:
        version_row.value = CAO_SEED_VERSION
    else:
        db.add(UserSettings(key=CAO_SEED_VERSION_KEY, value=CAO_SEED_VERSION))
    db.commit()
