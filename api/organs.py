"""Demo organ rule table. NOT NASA-STD-3001 compliance. See docs/SAFETY_ISSUES.md S6.

The deck's numbers are shown as *the deck's claim*, labelled DEMO THRESHOLD. A stale or
missing input yields UNKNOWN / NOT_AVAILABLE, never NOMINAL. No neural risk head exists.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from .actions import (CHECK_SENSOR, CONTACT_FLIGHT_SURGEON, REPEAT_MEASUREMENT,
                      REST_AND_RECHECK, allowed)
from .models import ManualCheck, OrganReading

# Declared validity windows in hours. Demo values, not clinical intervals.
VALIDITY_HOURS = {
    "bp": 4.0, "glucose": 8.0, "temperature": 4.0, "sleep": 24.0,
    "mood": 24.0, "onsd": 72.0, "pvt": 12.0,
}
STALENESS_LAMBDA = 0.15  # tau = exp(-lambda * age_hours); demo decay constant

SYSTEMS = (
    ("head-eyes", "Head & Eyes", "0g fluid shift + cabin CO2 (SANS)", "onsd", "mm",
     "ONSD >= 5.8 mm (deck claim)", 5.8, "ge"),
    ("heart", "Heart & Vessels", "Gravity shift + radiation (CSA vascular)", "bp", "mmHg",
     "Rest BP >= 140/90 mmHg (deck claim)", 140.0, "ge"),
    ("chest-immune", "Chest & Immune", "Space radiation (CSA dosimetry)", "temperature", "degC",
     "Temp >= 38.0 degC (deck claim)", 38.0, "ge"),
    ("metabolic", "Metabolic & Gut", "0g insulin drift (CSA glycemic)", "glucose", "mg/dL",
     "Fasting glucose >= 126 mg/dL (deck claim)", 126.0, "ge"),
    ("bones", "Bones & Muscles", "0g unloading (CSA osteo/renal)", "sleep", "h",
     "Sleep < 4.5 h (deck claim, proxy indicator)", 4.5, "lt"),
    ("brain", "Brain & Sleep", "Isolation + circadian shift", "pvt", "ms",
     "PVT median > 350 ms (deck claim)", 350.0, "gt"),
)


def tau(age_hours: float) -> float:
    return math.exp(-STALENESS_LAMBDA * max(0.0, age_hours))


def age_hours(check: ManualCheck, now: datetime | None = None) -> float | None:
    if not check.recorded_at:
        return None
    try:
        recorded = datetime.fromisoformat(check.recorded_at)
    except ValueError:
        return None
    if recorded.tzinfo is None:
        recorded = recorded.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return max(0.0, (now - recorded).total_seconds() / 3600.0)


def latest_by_kind(checks: list[ManualCheck]) -> dict[str, ManualCheck]:
    out: dict[str, ManualCheck] = {}
    for check in sorted(checks, key=lambda c: c.recorded_at):
        out[check.kind] = check
    return out


def _value_of(check: ManualCheck) -> float | None:
    if check.kind == "bp":
        return check.systolic
    return check.value


def organ_readings(checks: list[ManualCheck], now: datetime | None = None) -> list[OrganReading]:
    latest = latest_by_kind(checks)
    readings: list[OrganReading] = []
    for system, label, hazard, kind, unit, threshold_text, limit, op in SYSTEMS:
        check = latest.get(kind)
        if check is None:
            readings.append(OrganReading(
                system=system, label=label, status="NOT_AVAILABLE",
                indicator=f"No {kind} check logged", unit=unit, demo_threshold=threshold_text,
                hazard=hazard, action=allowed(REPEAT_MEASUREMENT),
                evidence="Not available — no crew entry for this indicator.",
            ))
            continue
        age = age_hours(check, now)
        value = _value_of(check)
        t = tau(age) if age is not None else None
        validity = VALIDITY_HOURS.get(kind, 4.0)
        if value is None or age is None:
            readings.append(OrganReading(
                system=system, label=label, status="UNKNOWN", indicator="Incomplete entry",
                unit=unit, demo_threshold=threshold_text, hazard=hazard, staleness_tau=t,
                age_hours=age, action=allowed(REPEAT_MEASUREMENT),
                evidence="Entry missing a value or a timestamp; not scored.",
            ))
            continue
        if age > validity:
            readings.append(OrganReading(
                system=system, label=label, status="UNKNOWN",
                indicator=f"{kind} is stale", value=value, unit=unit,
                demo_threshold=threshold_text, hazard=hazard, staleness_tau=t, age_hours=age,
                action=allowed(REPEAT_MEASUREMENT),
                evidence=(f"Last {kind} is {age:.1f} h old (validity {validity:g} h). "
                          "Stale input is UNKNOWN, never nominal."),
            ))
            continue
        breached = (value >= limit) if op == "ge" else (value > limit if op == "gt" else value < limit)
        near = (value >= 0.9 * limit) if op in {"ge", "gt"} else (value <= 1.1 * limit)
        status = "ALERT" if breached else ("WATCH" if near else "NOMINAL")
        action = (CONTACT_FLIGHT_SURGEON if breached
                  else REST_AND_RECHECK if near else REPEAT_MEASUREMENT)
        shown = f"{check.systolic:.0f}/{check.diastolic:.0f}" if check.kind == "bp" and check.diastolic else f"{value:g}"
        readings.append(OrganReading(
            system=system, label=label, status=status, indicator=f"{kind} = {shown} {unit}",
            value=value, unit=unit, demo_threshold=threshold_text, hazard=hazard,
            staleness_tau=t, age_hours=age, action=allowed(action),
            evidence=(f"Crew-entered {kind}, {age:.1f} h old, tau={t:.2f}. "
                      "Compared with a DEMO threshold, not a validated limit."),
        ))
    return readings


def min_tau(checks: list[ManualCheck], now: datetime | None = None) -> float | None:
    ages = [age_hours(c, now) for c in latest_by_kind(checks).values()]
    known = [a for a in ages if a is not None]
    return min(tau(a) for a in known) if known else None


def any_stale(checks: list[ManualCheck], now: datetime | None = None) -> bool:
    for check in latest_by_kind(checks).values():
        age = age_hours(check, now)
        if age is None or age > VALIDITY_HOURS.get(check.kind, 4.0):
            return True
    return False


def readiness_streak(checks: list[ManualCheck], now: datetime | None = None) -> dict:
    """Gamified check streak. No clinical meaning whatsoever."""
    now = now or datetime.now(timezone.utc)
    days = set()
    for check in checks:
        age = age_hours(check, now)
        if age is not None:
            days.add((now - timedelta(hours=age)).date().isoformat())
    ordered = sorted(days, reverse=True)
    streak = 0
    cursor = now.date()
    for _ in range(365):
        if cursor.isoformat() in days:
            streak += 1
            cursor = cursor - timedelta(days=1)
        else:
            break
    return {"streak_days": streak, "days_logged": len(ordered),
            "note": "Engagement counter only. No clinical or readiness meaning."}
