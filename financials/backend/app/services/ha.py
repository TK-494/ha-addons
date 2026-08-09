"""Publish a handful of figures to Home Assistant as sensors.

Uses the Supervisor proxy with the add-on's own token, so there is nothing for
the user to configure — no long-lived token, no URL. When the add-on runs
outside Home Assistant (plain Docker) the token is absent and this module
quietly does nothing.

Failures here never propagate: an unreachable Supervisor must not make an
import fail. Every call is best-effort and logged at warning level.

States pushed through the REST API do not survive a Home Assistant restart, so
they are republished on startup and on a timer as well as after each import.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import date
from typing import Optional

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..models import Account, Transaction
from . import periods, recurring

log = logging.getLogger("financials.ha")

SUPERVISOR_URL = "http://supervisor/core/api"
TIMEOUT_SECONDS = 10


def token() -> Optional[str]:
    return os.getenv("SUPERVISOR_TOKEN") or os.getenv("HASSIO_TOKEN")


def available() -> bool:
    return bool(token())


def _push(entity_id: str, state, attributes: dict) -> bool:
    auth = token()
    if not auth:
        return False

    payload = json.dumps({"state": state, "attributes": attributes}).encode()
    request = urllib.request.Request(
        f"{SUPERVISOR_URL}/states/{entity_id}",
        data=payload,
        method="POST",
        headers={"Authorization": f"Bearer {auth}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status in (200, 201)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        log.warning("Sensor %s niet bijgewerkt: %s", entity_id, exc)
        return False


def _slug(text: str) -> str:
    cleaned = "".join(c if c.isalnum() else "_" for c in text.lower())
    return "_".join(part for part in cleaned.split("_") if part)[:40]


EURO = {
    "unit_of_measurement": "EUR",
    "device_class": "monetary",
    "state_class": "total",
    "attribution": "Financials add-on",
}


def publish(db: Session) -> int:
    """Push the current figures. Returns how many sensors were updated."""
    if not available():
        return 0

    config = periods.load_config(db)
    year, month = periods.period_of(date.today(), config)
    start, end = periods.period_bounds(year, month, config)
    period_attrs = {"periode": f"{month:02d}-{year}", "van": start.isoformat(), "tot": end.isoformat()}

    positive = case((Transaction.amount_cents > 0, Transaction.amount_cents), else_=0)
    negative = case((Transaction.amount_cents < 0, Transaction.amount_cents), else_=0)
    income, expenses = db.execute(
        select(
            func.coalesce(func.sum(positive), 0),
            func.coalesce(func.sum(negative), 0),
        ).where(
            Transaction.is_internal.is_(False),
            Transaction.booked_on >= start,
            Transaction.booked_on < end,
        )
    ).one()

    updated = 0
    updated += _push(
        "sensor.financials_uitgaven_deze_maand",
        round(abs(expenses or 0) / 100, 2),
        {**EURO, **period_attrs, "friendly_name": "Uitgaven deze maand", "icon": "mdi:cash-minus"},
    )
    updated += _push(
        "sensor.financials_inkomsten_deze_maand",
        round((income or 0) / 100, 2),
        {**EURO, **period_attrs, "friendly_name": "Inkomsten deze maand", "icon": "mdi:cash-plus"},
    )

    accounts = db.scalars(select(Account).where(Account.archived.is_(False))).all()
    total = 0
    for account in accounts:
        latest = db.scalars(
            select(Transaction)
            .where(Transaction.account_id == account.id, Transaction.balance_after_cents.isnot(None))
            .order_by(Transaction.booked_on.desc(), Transaction.id.desc())
            .limit(1)
        ).first()
        if latest is None:
            continue
        balance = latest.balance_after_cents
        if account.include_in_networth:
            total += balance
        updated += _push(
            f"sensor.financials_saldo_{_slug(account.label)}",
            round(balance / 100, 2),
            {
                **EURO,
                "friendly_name": f"Saldo {account.label}",
                "icon": "mdi:bank",
                "soort": account.kind,
                "laatste_transactie": latest.booked_on.isoformat(),
            },
        )

    updated += _push(
        "sensor.financials_saldo_totaal",
        round(total / 100, 2),
        {**EURO, "friendly_name": "Totaal saldo", "icon": "mdi:cash-multiple",
         "rekeningen": len(accounts)},
    )

    groups = [g for g in recurring.detect(db, config) if g.is_active]
    updated += _push(
        "sensor.financials_vaste_lasten",
        round(sum(abs(g.monthly_equivalent_cents) for g in groups) / 100, 2),
        {**EURO, "friendly_name": "Vaste lasten per maand", "icon": "mdi:repeat",
         "aantal": len(groups)},
    )

    uncategorised = db.scalar(
        select(func.count()).select_from(Transaction)
        .where(Transaction.category_id.is_(None), Transaction.is_internal.is_(False))
    ) or 0
    updated += _push(
        "sensor.financials_ongecategoriseerd",
        uncategorised,
        {"friendly_name": "Ongecategoriseerde transacties", "icon": "mdi:help-circle-outline",
         "unit_of_measurement": "transacties", "state_class": "measurement"},
    )

    log.info("%s sensoren bijgewerkt in Home Assistant", updated)
    return updated
